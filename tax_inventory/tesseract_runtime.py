"""Locate the Tesseract binary, including a copy bundled inside a frozen app."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def resource_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def configure_tesseract() -> None:
    import pytesseract

    root = resource_root()
    exe_name = "tesseract.exe" if os.name == "nt" else "tesseract"
    bundled = root / "tesseract" / exe_name
    override = os.environ.get("TESSERACT_CMD")

    if override:
        pytesseract.pytesseract.tesseract_cmd = override
        bin_dir = str(Path(override).parent)
    elif bundled.exists():
        pytesseract.pytesseract.tesseract_cmd = str(bundled)
        bin_dir = str(bundled.parent)
    else:
        return

    os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
    tessdata = Path(bin_dir) / "tessdata"
    if tessdata.is_dir():
        os.environ.setdefault("TESSDATA_PREFIX", str(tessdata))
