# -*- mode: python ; coding: utf-8 -*-
# PyInstaller build spec for AnimeRS.
# Build with:  pyinstaller AnimeRS.spec
#
# collect_all is needed because these packages load things dynamically that
# PyInstaller's static analysis can't see:
#   - imageio_ffmpeg ships the actual ffmpeg binary inside the package
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

# Packages that get dragged in but are never used at runtime. The Qt entries
# are the Python bindings only - the Qt libraries themselves still ship if
# something we do use links against them.
excludes = [
    'tkinter', 'unittest', 'doctest', 'pydoc', 'pydoc_data', 'lib2to3',
    'test', 'distutils', 'setuptools', 'pip', 'wheel',
    'matplotlib', 'scipy', 'pandas', 'IPython',
    'PyQt5', 'PySide2', 'PySide6',
    'PyQt6.QtQml', 'PyQt6.QtQuick', 'PyQt6.QtQuickWidgets', 'PyQt6.QtPdf',
    'PyQt6.QtPdfWidgets', 'PyQt6.QtWebEngineCore', 'PyQt6.QtWebEngineWidgets',
    'PyQt6.QtWebChannel', 'PyQt6.QtBluetooth', 'PyQt6.QtNfc', 'PyQt6.QtSerialPort',
    'PyQt6.QtPositioning', 'PyQt6.QtSensors', 'PyQt6.QtCharts', 'PyQt6.QtDesigner',
    'PyQt6.QtHelp', 'PyQt6.QtSql', 'PyQt6.QtTest', 'PyQt6.QtTextToSpeech',
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

# Qt files that survive the excludes above because collect_all grabbed whole
# package trees. Matched on the bundled path, so the same patterns catch the
# .so / .dll / .dylib naming on all three platforms.
#
# Careful: Qt's ffmpeg media plugin links Qt6Quick and Qt6Qml, so those stay
# even though the app never touches QML - dropping them kills preview playback.
_PRUNE = (
    'Qt6/translations',   # the UI is English-only
    'Qt6/qml',            # QML modules - only the C++ libs are needed
    'Qt6Pdf',
    'Qt6Quick3D',
    'Qt6Charts',
    'Qt6DataVisualization',
    'Qt6WebEngine',
    'Qt6Designer',
    'Qt6Bluetooth',
    'Qt6Nfc',
    'Qt6SerialPort',
    'Qt6Sensors',
    'Qt6TextToSpeech',
    'plugins/sqldrivers',
    'plugins/assetimporters',
    'plugins/geometryloaders',
    'plugins/sceneparsers',
    'plugins/renderers',
    'plugins/qmllint',
    'plugins/qmlls',
    'plugins/help',
    'plugins/webview',
)


def _keep(entry) -> bool:
    bundled_path = entry[0].replace('\\', '/')
    return not any(pattern in bundled_path for pattern in _PRUNE)


a.binaries = [entry for entry in a.binaries if _keep(entry)]
a.datas = [entry for entry in a.datas if _keep(entry)]

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
    icon='ui/assets/app_icon.png',
)
