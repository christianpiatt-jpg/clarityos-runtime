"""
SOS Runtime — operator-facing reasoning service that sits behind a
WordPress connector plugin. Standalone Cloud Run service; independent
of the V47-V82 ClarityOS infrastructure. See ``README.md``.
"""
from pathlib import Path

VERSION = (Path(__file__).resolve().parent / "VERSION").read_text(
    encoding="utf-8",
).strip()
SERVICE_NAME = "os-runtime"

__all__ = ["VERSION", "SERVICE_NAME"]
