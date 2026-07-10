# -*- mode: python ; coding: utf-8 -*-
# PyInstaller build spec for AnimeRS.
# Build with:  pyinstaller AnimeRS.spec
#
# collect_all is needed because these packages load things dynamically that
# PyInstaller's static analysis can't see:
#   - imageio_ffmpeg ships the actual ffmpeg.exe binary inside the package
#   - imageio loads its format plugins at runtime
#   - uvicorn imports its loop/protocol/logging classes by string name
from PyInstaller.utils.hooks import collect_all

datas = [('ui/assets', 'ui/assets')]  # app icon + any other bundled images
binaries = []
hiddenimports = []
for _pkg in ('imageio', 'imageio_ffmpeg', 'uvicorn', 'PyQt6.QtMultimedia', 'PyQt6.QtMultimediaWidgets'):
    _d, _b, _h = collect_all(_pkg)
    datas += _d
    binaries += _b
    hiddenimports += _h

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='AnimeRS',
    debug=False,
    strip=False,
    upx=False,
    console=False,   # no black console window. Flip to True to debug a broken build.
    icon='app_icon.ico',
)
