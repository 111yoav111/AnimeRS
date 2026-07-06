"""
AnimeRS build script - packs the app into a single .exe (or binary on other OSes).

Usage (from the folder containing main.py):
    python build.py

All build configuration (bundled packages, assets, icon, windowed mode) lives
in AnimeRS.spec - this script only automates the chores around it:
    1. make sure in the right folder
    2. make sure PyInstaller is installed
    3. generate app_icon.ico from ui/assets/app_icon.png if missing
    4. run the spec build
The result lands in dist/AnimeRS.exe 
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
SPEC = HERE / "AnimeRS.spec"
PNG_ICON = HERE / "ui" / "assets" / "app_icon.png"
ICO_ICON = HERE / "app_icon.ico"


def check_location() -> None:
    """
    Refuse to run from the wrong folder - relative paths in the spec depend on it.
    """
    missing = [p.name for p in (HERE / "main.py", SPEC) if not p.exists()]
    if missing:
        sys.exit(f"Missing {', '.join(missing)} - run build.py from the folder containing main.py.")


def check_pyinstaller() -> None:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        sys.exit("PyInstaller is not installed. Run: pip install pyinstaller")


def make_icon() -> None:
    """
    Generate the multi-size .ico Windows needs, from the app's PNG logo.
    """
    if ICO_ICON.exists():
        print(f"Icon already exists: {ICO_ICON.name}")
        return
    if not PNG_ICON.exists():
        sys.exit(f"Logo not found at {PNG_ICON} - cannot create the exe icon.")
    from PIL import Image
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    Image.open(PNG_ICON).save(ICO_ICON, sizes=sizes)
    print(f"Created {ICO_ICON.name}")


def run_build() -> None:
    print("Building with PyInstaller (this takes a few minutes)...")
    subprocess.check_call([sys.executable, "-m", "PyInstaller", str(SPEC)], cwd=HERE)
    exe = HERE / "dist" / ("AnimeRS.exe" if sys.platform == "win32" else "AnimeRS")
    print(f"\nBuild successful -> {exe}")
    print("Test it by copying it somewhere else (e.g. Desktop) and double clicking. Have fun! 😎")


if __name__ == "__main__":
    check_location()
    check_pyinstaller()
    make_icon()
    run_build()
