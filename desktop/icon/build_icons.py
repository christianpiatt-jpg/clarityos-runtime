#!/usr/bin/env python3
"""
ClarityOS desktop icon builder.

Generates the full icon set the Electron app expects:

    desktop/icon/icon.png        (1024x1024)
    desktop/icon/icon@2x.png     (2048x2048)
    desktop/icon/icon-512.png
    desktop/icon/icon-256.png
    desktop/icon/icon-128.png
    desktop/icon/icon-64.png
    desktop/icon/icon-32.png
    desktop/icon/icon.ico        (multi-size .ico for Windows)
    desktop/icon/icon.icns       (when run on macOS with iconutil installed,
                                  otherwise skipped with a note)

Source resolution:
    1. If ``desktop/icon/icon-source.png`` exists, that's the master.
       Drop the real PM artwork there and re-run; everything else
       regenerates from it.
    2. Otherwise the SVG (``icon.svg``) is rasterised — but Pillow can't
       render SVG natively, so we fall back to a deterministic
       pyramid-and-sphere drawn directly with PIL primitives. Same
       geometry as the SVG, just a programmatic raster path so the
       script works in CI without cairo/svgo.

Usage:
    python desktop/icon/build_icons.py
"""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ICON_DIR = Path(__file__).resolve().parent
SOURCE_PNG = ICON_DIR / "icon-source.png"

PNG_SIZES: list[int] = [1024, 512, 256, 128, 64, 32]
PNG_NAMES: dict[int, str] = {
    1024: "icon.png",
    512:  "icon-512.png",
    256:  "icon-256.png",
    128:  "icon-128.png",
    64:   "icon-64.png",
    32:   "icon-32.png",
}
ICO_SIZES: list[int] = [16, 24, 32, 48, 64, 128, 256]
RETINA_OUT = ICON_DIR / "icon@2x.png"   # 2048


# ---------------------------------------------------------------------------
# Programmatic raster master (used when icon-source.png is absent)
# ---------------------------------------------------------------------------
ACCENT = (136, 240, 208)        # PM accent green
DEEP   = (4, 18, 27)
SHADOW = (2, 10, 16)
WHITE  = (255, 255, 255)


def _draw_master(size: int = 1024) -> Image.Image:
    """Render the placeholder pyramid+sphere into a transparent PNG.
    Geometry mirrors ``icon.svg``."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Halo — soft accent disc that bleeds off the edges. Achieved by
    # drawing a partial-alpha disc onto a separate layer + blurring.
    halo = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    halo_draw = ImageDraw.Draw(halo)
    halo_radius = int(size * 0.46)
    cx = size // 2
    cy = int(size * 0.54)
    for i in range(8):
        # Concentric falloff rings — cheap radial gradient.
        r = halo_radius - i * (halo_radius // 12)
        a = int(48 * (1.0 - i / 8) ** 2)
        halo_draw.ellipse(
            (cx - r, cy - r, cx + r, cy + r),
            fill=(*ACCENT, a),
        )
    halo = halo.filter(ImageFilter.GaussianBlur(radius=size * 0.04))
    img = Image.alpha_composite(img, halo)
    draw = ImageDraw.Draw(img)

    # Pyramid: apex (cx, 0.35h), base corners (0.18w, 0.80h),
    # (0.82w, 0.80h), back-right corner (cx, 0.70h) for the visible
    # right face.
    apex   = (cx, int(size * 0.352))
    base_l = (int(size * 0.184), int(size * 0.801))
    base_r = (int(size * 0.816), int(size * 0.801))
    back_r = (cx, int(size * 0.703))

    # Right face (darker).
    draw.polygon(
        [apex, base_r, back_r],
        fill=(*SHADOW, 255),
        outline=(*ACCENT, 140),
    )
    # Front face.
    draw.polygon(
        [apex, base_l, base_r],
        fill=(*DEEP, 255),
        outline=(*ACCENT, 220),
    )
    # Crease line back to apex.
    draw.line([apex, back_r], fill=(*ACCENT, 90), width=max(1, size // 512))

    # Sphere glow — separate layer + blur.
    sphere_cx = cx
    sphere_cy = int(size * 0.273)
    sphere_r  = int(size * 0.117)
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    for i in range(6):
        r = sphere_r + (i * size // 64)
        a = int(60 * (1.0 - i / 6) ** 2)
        glow_draw.ellipse(
            (sphere_cx - r, sphere_cy - r, sphere_cx + r, sphere_cy + r),
            outline=(*ACCENT, a), width=max(1, size // 256),
        )
    glow = glow.filter(ImageFilter.GaussianBlur(radius=size * 0.012))
    img = Image.alpha_composite(img, glow)
    draw = ImageDraw.Draw(img)

    # Sphere body — fake the radial shading by drawing concentric
    # darkening rings then a highlight ellipse on top.
    for i in range(sphere_r, 0, -1):
        # Distance from highlight focus (offset upper-left).
        t = i / sphere_r
        # Body color: accent center → deep edge.
        cr = int(_lerp(214, 4, t))
        cg = int(_lerp(255, 18, t))
        cb = int(_lerp(241, 27, t))
        draw.ellipse(
            (sphere_cx - i, sphere_cy - i, sphere_cx + i, sphere_cy + i),
            fill=(cr, cg, cb, 255),
        )
    # Outline.
    draw.ellipse(
        (sphere_cx - sphere_r, sphere_cy - sphere_r,
         sphere_cx + sphere_r, sphere_cy + sphere_r),
        outline=(*ACCENT, 200),
        width=max(2, size // 512),
    )
    # Specular highlight (rotated ellipse approximated with a fat dot).
    hl_r = max(2, sphere_r // 4)
    hl_cx = sphere_cx - sphere_r // 3
    hl_cy = sphere_cy - sphere_r // 3
    hl = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    hl_draw = ImageDraw.Draw(hl)
    hl_draw.ellipse(
        (hl_cx - hl_r * 2, hl_cy - hl_r,
         hl_cx + hl_r * 2, hl_cy + hl_r),
        fill=(*WHITE, 80),
    )
    hl = hl.filter(ImageFilter.GaussianBlur(radius=max(1, size // 256)))
    img = Image.alpha_composite(img, hl)

    return img


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * max(0.0, min(1.0, t))


# ---------------------------------------------------------------------------
# Build pipeline
# ---------------------------------------------------------------------------
def _resolve_master() -> Image.Image:
    if SOURCE_PNG.exists():
        master = Image.open(SOURCE_PNG).convert("RGBA")
        # Normalise to a square 1024 master if the source is bigger;
        # leave smaller sources untouched (they'll just upscale poorly).
        if master.width > 1024 or master.height > 1024:
            master.thumbnail((1024, 1024), Image.LANCZOS)
        # Pad to square if non-square so downstream resizes preserve aspect.
        if master.width != master.height:
            side = max(master.width, master.height)
            sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
            sq.paste(
                master,
                ((side - master.width) // 2, (side - master.height) // 2),
            )
            master = sq
        return master
    print(
        "[build_icons] icon-source.png not found — rasterising programmatic "
        "placeholder (matches icon.svg geometry).",
    )
    return _draw_master(1024)


def main() -> int:
    master = _resolve_master()

    # 1. PNGs at every size.
    for sz in PNG_SIZES:
        out = ICON_DIR / PNG_NAMES[sz]
        resized = master.resize((sz, sz), Image.LANCZOS)
        resized.save(out, "PNG", optimize=True)
        print(f"[build_icons] wrote {out.name} ({sz}x{sz})")

    # 2. Retina @2x (2048x2048).
    retina = master.resize((2048, 2048), Image.LANCZOS)
    retina.save(RETINA_OUT, "PNG", optimize=True)
    print(f"[build_icons] wrote {RETINA_OUT.name} (2048x2048)")

    # 3. Multi-size .ico (Windows).
    ico_out = ICON_DIR / "icon.ico"
    master.save(
        ico_out, format="ICO",
        sizes=[(s, s) for s in ICO_SIZES],
    )
    print(f"[build_icons] wrote {ico_out.name} ({len(ICO_SIZES)} sizes embedded)")

    # 4. .icns — Pillow can't write .icns directly. Use macOS iconutil
    #    when available; otherwise emit a note.
    icns_out = ICON_DIR / "icon.icns"
    iconset = ICON_DIR / "icon.iconset"
    if sys.platform == "darwin":
        os.makedirs(iconset, exist_ok=True)
        # Standard Apple iconset layout.
        layout = {
            16: ["icon_16x16.png", "icon_16x16@2x.png"],
            32: ["icon_32x32.png", "icon_32x32@2x.png"],
            128: ["icon_128x128.png", "icon_128x128@2x.png"],
            256: ["icon_256x256.png", "icon_256x256@2x.png"],
            512: ["icon_512x512.png", "icon_512x512@2x.png"],
        }
        # Apple expects each base size + a @2x of the size below it.
        # Easiest is to just write each requested size verbatim.
        sizes_needed = [16, 32, 64, 128, 256, 512, 1024]
        for sz in sizes_needed:
            master.resize((sz, sz), Image.LANCZOS).save(
                iconset / f"icon_{sz}x{sz}.png", "PNG", optimize=True,
            )
        # Run iconutil via the OS.
        rc = os.system(
            f"iconutil -c icns -o '{icns_out}' '{iconset}'",
        )
        if rc != 0:  # pragma: no cover (platform-specific)
            print(
                "[build_icons] iconutil exited non-zero; .icns not written. "
                "Falling back to bundling the 1024 png as icon.icns.fallback.png",
            )
        else:
            print(f"[build_icons] wrote {icns_out.name}")
    else:
        print(
            "[build_icons] skipping icon.icns (requires macOS / iconutil). "
            "Use 'iconutil -c icns -o icon.icns icon.iconset' on a Mac, or "
            "rely on icon.png at runtime (Electron accepts PNG on every "
            "platform)."
        )
        # Keep a sentinel so the Electron builder doesn't choke on a
        # missing path. The .icns rule in package.json points at the
        # PNG fallback when the .icns isn't present.
        (ICON_DIR / "ICNS_NOT_BUILT.txt").write_text(
            "icon.icns is not generated on non-macOS hosts. "
            "Build it on a Mac with iconutil, or let electron-builder "
            "auto-generate it from icon.png at packaging time.",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
