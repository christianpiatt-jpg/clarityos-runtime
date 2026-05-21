#!/usr/bin/env python3
"""
ClarityOS emblem -> desktop icon set  (Option A, founder-locked).

The source emblem is a ~2:1 landscape render with a baked dark
background, a floor reflection, and an AI-generator watermark in the
lower-right corner. App icons are square. Option A resolves that with
the only path that keeps the emblem itself perfectly faithful:

    a CENTERED SQUARE CROP (minimal crop to square), keeping the
    emblem's own dark backdrop.

The watermark sits in the cropped-out right margin, so it is removed
for free with no pixel editing. Geometry / colour / glow / lighting
are never touched. This script does exactly three things: crop ->
resize -> pack. No reinterpretation, no generation.

Outputs (all written into desktop/icon/):

    icon-master.png            1024x1024  square master
    icon-1024/512/256/128/64/32/16.png    requested PNG set
    icon.ico                   multi-size  256/128/64/48/32/16
    icon.icns                  macOS bundle (Pillow writer, cross-platform)
    icon.png                   build alias  (electron-builder, 1024)
    icon@2x.png                build alias  (electron-builder, 2048)

Run:  py -3.12 desktop/icon/build_emblem_icons.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

ICON_DIR = Path(__file__).resolve().parent

# Source = the emblem the founder placed in desktop/icon/.
SRC = ICON_DIR / "Gemini_Generated_Image_hubnu7hubnu7hubn.png"
if not SRC.exists():                       # allow a clean rename later
    SRC = ICON_DIR / "emblem-source.png"

PNG_SIZES = [1024, 512, 256, 128, 64, 32, 16]
ICO_SIZES = [256, 128, 64, 48, 32, 16]
RESAMPLE = Image.LANCZOS


def main() -> int:
    src = Image.open(SRC).convert("RGB")   # RGB = opaque, no transparency
    w, h = src.size
    print(f"source : {SRC.name}  {w}x{h}  mode=RGB")

    # --- centered square crop: minimal crop to a perfect square --------
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    box = (left, top, left + side, top + side)
    crop = src.crop(box)
    print(f"crop   : box={box}  -> {crop.width}x{crop.height} square")
    print(f"         trimmed {left}px left / {w - left - side}px right "
          f"(watermark lives in the cropped-out right margin)")

    # Every output is resampled in ONE LANCZOS step directly from the
    # full-resolution crop -- no chaining through a smaller master.
    def emit(size: int, name: str) -> None:
        img = crop.resize((size, size), RESAMPLE)
        img.save(ICON_DIR / name, "PNG", optimize=True)
        print(f"wrote  : {name:<18} {size}x{size}")

    # --- master + requested PNG set -----------------------------------
    emit(1024, "icon-master.png")
    for sz in PNG_SIZES:
        emit(sz, f"icon-{sz}.png")

    # --- Windows .ico --------------------------------------------------
    crop.save(ICON_DIR / "icon.ico", format="ICO",
              sizes=[(s, s) for s in ICO_SIZES])
    print(f"wrote  : {'icon.ico':<18} {'/'.join(map(str, ICO_SIZES))}")

    # --- macOS .icns (Pillow's writer works on any host) --------------
    crop.resize((1024, 1024), RESAMPLE).convert("RGBA").save(
        ICON_DIR / "icon.icns", format="ICNS")
    print(f"wrote  : {'icon.icns':<18} up to 1024")

    # --- build-wired aliases electron-builder expects ------------------
    emit(1024, "icon.png")
    emit(2048, "icon@2x.png")

    # --- drop the now-false sentinel ----------------------------------
    sentinel = ICON_DIR / "ICNS_NOT_BUILT.txt"
    if sentinel.exists():
        sentinel.unlink()
        print("removed: ICNS_NOT_BUILT.txt  (stale -- icon.icns now exists)")

    print("done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
