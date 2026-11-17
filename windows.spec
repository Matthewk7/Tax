# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for a Windows onedir build. Run this spec on Windows."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata

project = Path(SPECPATH)


def tesseract_home() -> Path:
    env = os.environ.get("TESSERACT_HOME")
    if env:
        path = Path(env)
        if path.is_dir():
            return path
    which = shutil.which("tesseract")
    if which:
        return Path(which).resolve().parent
    for candidate in (
        Path(r"C:\Program Files\Tesseract-OCR"),
        Path(r"C:\Program Files (x86)\Tesseract-OCR"),
    ):
        if candidate.is_dir():
            return candidate
    raise SystemExit(
        "Tesseract OCR was not found. Install it on this Windows machine "
        "and/or set TESSERACT_HOME to the Tesseract-OCR folder."
    )


datas: list = []
binaries: list = []
hiddenimports: list = []

for pkg in ("streamlit", "pymupdf", "PIL", "pillow_heif", "pytesseract"):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

datas += copy_metadata("streamlit")
datas += [
    (str(project / "app.py"), "."),
    (str(project / "tax_inventory"), "tax_inventory"),
    (str(project / ".streamlit"), ".streamlit"),
]
hiddenimports += collect_submodules("tax_inventory")

tesseract_dir = tesseract_home()
datas.append((str(tesseract_dir), "tesseract"))

a = Analysis(
    ["run_app.py"],
    pathex=[str(project)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="TaxDocInventory",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="TaxDocInventory",
)
