"""
LumaFlow portable package build script.
Builds a one-file executable and bundles it into a distributable zip archive.
"""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import platform
import zipfile
from pathlib import Path

from core.metadata import APP_METADATA


BASE_DIR = Path(__file__).resolve().parent
LOCAL_ENV_PYTHON = BASE_DIR / "env" / "Scripts" / "python.exe"
SPEC_PATH = BASE_DIR / "LumaFlow.spec"


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
BUILD_DIR = BASE_DIR / "build" / RELEASE_BASENAME
DIST_DIR = BASE_DIR / "dist" / RELEASE_BASENAME
README_PATH = DIST_DIR / "README.txt"
PYINSTALLER_EXE_PATH = DIST_DIR / "LumaFlow.exe"
EXE_PATH = DIST_DIR / EXE_NAME
ZIP_PATH = BASE_DIR / f"{RELEASE_BASENAME}_Portable.zip"
CHECKSUM_PATH = BASE_DIR / f"{RELEASE_BASENAME}_Portable.zip.sha256"
CHANGELOG_PATH = BASE_DIR / "CHANGELOG.md"


def relaunch_in_local_environment():
    """Use the project environment so optional transports are packaged."""
    if not LOCAL_ENV_PYTHON.exists():
        return None
    if Path(sys.executable).resolve() == LOCAL_ENV_PYTHON.resolve():
        return None

    print(f"Restarting build with project Python: {LOCAL_ENV_PYTHON}")
    return subprocess.call([str(LOCAL_ENV_PYTHON), str(Path(__file__).resolve())], cwd=BASE_DIR)


def check_build_dependencies():
    missing = []
    for module_name, package_name in (
        ("PyInstaller", "pyinstaller"),
        ("bleak", "bleak"),
        ("serial", "pyserial"),
    ):
        try:
            __import__(module_name)
        except ImportError:
            missing.append(package_name)

    if not missing:
        return True

    packages = " ".join(missing)
    print(f"Error: missing build dependencies: {packages}")
    print(f'Run: "{sys.executable}" -m pip install {packages}')
    return False


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
        "--workpath",
        str(BUILD_DIR),
        "--distpath",
        str(DIST_DIR),
        str(SPEC_PATH),
    ]
    subprocess.run(cmd, check=True, cwd=BASE_DIR)
    rename_exe()
    verify_executable_archive()


def rename_exe():
    """Rename the PyInstaller output to the release filename."""
    if not PYINSTALLER_EXE_PATH.exists():
        raise FileNotFoundError(f"Expected build output not found: {PYINSTALLER_EXE_PATH}")

    if EXE_PATH.exists():
        EXE_PATH.unlink()
    PYINSTALLER_EXE_PATH.rename(EXE_PATH)


def verify_executable_archive():
    """Reject incomplete one-file builds before creating a release archive."""
    from PyInstaller.archive.readers import CArchiveReader

    try:
        toc = CArchiveReader(str(EXE_PATH)).toc
    except Exception as exc:
        raise RuntimeError(f"Built executable has an invalid PyInstaller archive: {exc}") from exc

    python_dll = f"python{sys.version_info.major}{sys.version_info.minor}.dll"
    required_entries = {python_dll, "PYZ.pyz"}
    missing = sorted(required_entries.difference(toc))
    if missing:
        raise RuntimeError(
            "Built executable is missing required archive entries: "
            + ", ".join(missing)
        )
    print(f"Verified executable archive: {python_dll}, PYZ.pyz")


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
- BLE support is included in this portable build.
- Device output supports Serial, BLE, and UDP (fixed port 32712).
- VLC Media Player and FFmpeg are external system dependencies.
- Check the version in Help > About before field use.

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
        if CHANGELOG_PATH.exists():
            zipf.write(CHANGELOG_PATH, "CHANGELOG.md")

    print(f"Created archive: {ZIP_PATH.name}")
    print(f"Size: {ZIP_PATH.stat().st_size / 1024 / 1024:.1f} MB")


def create_checksum():
    """Write a SHA-256 checksum next to the portable archive."""
    digest = hashlib.sha256()
    with ZIP_PATH.open("rb") as archive:
        for chunk in iter(lambda: archive.read(1024 * 1024), b""):
            digest.update(chunk)
    CHECKSUM_PATH.write_text(
        f"{digest.hexdigest()}  {ZIP_PATH.name}\n",
        encoding="ascii",
    )
    print(f"Created checksum: {CHECKSUM_PATH.name}")


def main():
    relaunched_result = relaunch_in_local_environment()
    if relaunched_result is not None:
        return relaunched_result

    print("LumaFlow portable build tool")
    print("=" * 50)
    print(f"Version: {APP_VERSION}")
    print(f"Platform: {PLATFORM_TAG}")
    print(f"Executable: {EXE_NAME}")
    print(f"Archive: {ZIP_PATH.name}")
    print("=" * 50)

    if not check_build_dependencies():
        return 1

    clean_build()
    build_exe()
    create_readme()
    create_zip()
    create_checksum()

    print("\nBuild complete.")
    print(f"Executable: {EXE_PATH.relative_to(BASE_DIR)}")
    print(f"Archive: {ZIP_PATH.name}")
    print(f"Checksum: {CHECKSUM_PATH.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
