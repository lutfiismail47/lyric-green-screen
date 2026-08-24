# -*- mode: python ; coding: utf-8 -*-

import os
import sys
import platform
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None
project_root = Path.cwd()

# 1. Pilih subfolder FFmpeg sesuai sistem operasi
is_windows = platform.system() == "Windows"
ffmpeg_subfolder = 'ffmpeg_windows' if is_windows else 'ffmpeg_linux'

# 2. Bundling Data Assets & Binaries
datas = [
    (str(project_root / 'assets' / 'fonts'), 'assets/fonts'),
    (str(project_root / 'assets' / 'models'), 'assets/models'),
    (str(project_root / 'bin' / ffmpeg_subfolder), f'bin/{ffmpeg_subfolder}'),
]

# Tambahkan data internal dependencies faster-whisper
datas += collect_data_files('faster_whisper')

# 3. Hidden Imports (CTranslate2, Whisper, PIL, PyQt6)
hiddenimports = [
    'faster_whisper',
    'ctranslate2',
    'PIL',
    'PIL.Image',
    'PIL.ImageDraw',
    'PIL.ImageFont',
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'PyQt6.QtMultimedia',
]
hiddenimports += collect_submodules('faster_whisper')

a = Analysis(
    ['main.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'unittest'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='lyric-green-screen',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='lyric-green-screen',
)