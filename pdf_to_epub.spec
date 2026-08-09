# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

project_root = Path(SPECPATH).resolve()

a = Analysis(
    [str(project_root / "run.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[],
    hiddenimports=["pytesseract"],
    hookspath=[],
    excludes=[
        "IPython",
        "jupyter",
        "matplotlib",
        "numpy",
        "pandas",
        "pyarrow",
        "pytest",
        "scipy",
        "tkinter",
    ],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name="PDFtoEPUB",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name="PDFtoEPUB",
)
