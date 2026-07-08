"""
LumaFlow portable package build script.
Builds a one-file executable and bundles it into a distributable zip archive.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import platform
import zipfile
from pathlib import Path

from core.metadata import APP_METADATA


BASE_DIR = Path(__file__).resolve().parent
BUILD_DIR = BASE_DIR / "build"
DIST_DIR = BASE_DIR / "dist"
SPEC_PATH = BASE_DIR / "LumaFlow.spec"
README_PATH = DIST_DIR / "README.txt"
PYINSTALLER_EXE_PATH = DIST_DIR / "LumaFlow.exe"


def get_platform_tag():
    """Return a short platform tag suitable for release filenames."""
    system = platform.system() or sys.platform
    machine = platform.machine().lower()

    system_tag = {
        "Windows": "Windows",
        "Darwin": "macOS",
        "Linux": "Linux",
    }.get(system, system.replace(" ", ""))

    arch_tag = {
        "amd64": "x64",
        "x86_64": "x64",
        "arm64": "arm64",
        "aarch64": "arm64",
        "i386": "x86",
        "i686": "x86",
        "x86": "x86",
    }.get(machine, machine.replace(" ", "") or "unknown")

    return f"{system_tag}_{arch_tag}"


APP_VERSION = APP_METADATA["version"]
PLATFORM_TAG = get_platform_tag()
RELEASE_BASENAME = f"LumaFlow_v{APP_VERSION}_{PLATFORM_TAG}"
EXE_NAME = f"{RELEASE_BASENAME}.exe"
EXE_PATH = DIST_DIR / EXE_NAME
ZIP_PATH = BASE_DIR / f"{RELEASE_BASENAME}_Portable.zip"


def clean_build():
    """Remove previous build outputs."""
    for path in (BUILD_DIR, DIST_DIR):
        if path.exists():
            print(f"Cleaning {path}...")
            shutil.rmtree(path)


def build_exe():
    """Build the executable via the project spec file."""
    print("Building executable...")
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        str(SPEC_PATH),
    ]
    subprocess.run(cmd, check=True, cwd=BASE_DIR)
    rename_exe()


def rename_exe():
    """Rename the PyInstaller output to the release filename."""
    if not PYINSTALLER_EXE_PATH.exists():
        raise FileNotFoundError(f"Expected build output not found: {PYINSTALLER_EXE_PATH}")

    if EXE_PATH.exists():
        EXE_PATH.unlink()
    PYINSTALLER_EXE_PATH.rename(EXE_PATH)


def create_readme():
    """Create the portable package README."""
    readme = f"""LumaFlow Portable

Usage:
1. Extract this archive to any folder.
2. Double-click {EXE_NAME} to run.

System requirements:
- Windows 10/11 64-bit
- VLC Media Player installed and available on PATH
- FFmpeg installed and available on PATH

Notes:
- First launch may take a few seconds.
- Some antivirus tools may raise false positives for one-file bundles.

Version: {APP_METADATA['version']}
Platform: {PLATFORM_TAG}
Author: {APP_METADATA['author']}
"""
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    README_PATH.write_text(readme, encoding="utf-8")


def create_zip():
    """Create the final portable archive."""
    print("Creating zip archive...")

    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zipf:
        if EXE_PATH.exists():
            zipf.write(EXE_PATH, EXE_NAME)
        if README_PATH.exists():
            zipf.write(README_PATH, "README.txt")

    print(f"Created archive: {ZIP_PATH.name}")
    print(f"Size: {ZIP_PATH.stat().st_size / 1024 / 1024:.1f} MB")


def main():
    print("LumaFlow portable build tool")
    print("=" * 50)
    print(f"Version: {APP_VERSION}")
    print(f"Platform: {PLATFORM_TAG}")
    print(f"Executable: {EXE_NAME}")
    print(f"Archive: {ZIP_PATH.name}")
    print("=" * 50)

    try:
        subprocess.run(
            [sys.executable, "-m", "PyInstaller", "--version"],
            check=True,
            capture_output=True,
            cwd=BASE_DIR,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: PyInstaller is not installed.")
        print("Please run: pip install pyinstaller")
        return 1

    clean_build()
    build_exe()
    create_readme()
    create_zip()

    print("\nBuild complete.")
    print(f"Executable: {EXE_PATH.relative_to(BASE_DIR)}")
    print(f"Archive: {ZIP_PATH.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
