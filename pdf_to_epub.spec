# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files

datas = collect_data_files("PySide6")

a = Analysis(["run.py"], pathex=[], binaries=[], datas=datas, hiddenimports=[], hookspath=[])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.zipfiles, a.datas, name="PDFtoEPUB", console=False)
