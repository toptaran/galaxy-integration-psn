import json
import os
import platform
import shutil
import subprocess
import sys
import zipfile
from glob import glob
from pathlib import Path

from invoke import task
from invoke.exceptions import Exit

BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR / "src"
GUID = "38087aea-3c30-439f-867d-ddf9fae8fe6f"
LEGACY_GUID = "e4b92a16-7f3c-4d8a-9e1b-2c6f8a3d5e7b"
SYSTEM = platform.system()


def load_version() -> str:
    version_file = SRC_DIR / "version.py"
    version = {}
    exec(version_file.read_text(encoding="utf-8"), version)
    return version["__version__"]


def uv_platform() -> str:
    if SYSTEM == "Windows":
        return "x86_64-pc-windows-msvc"
    if SYSTEM == "Darwin":
        return "aarch64-apple-darwin"
    raise Exit(f"Unsupported system: {SYSTEM}")


def release_zip_name() -> str:
    if SYSTEM == "Windows":
        return "windows.zip"
    if SYSTEM == "Darwin":
        return "macos.zip"
    raise Exit(f"Unsupported system: {SYSTEM}")


def uv_executable() -> str:
    uv = shutil.which("uv")
    if not uv:
        raise Exit("uv is required. Install from https://docs.astral.sh/uv/getting-started/installation/")
    return uv


def plugins_dir() -> Path:
    if SYSTEM == "Windows":
        return Path(os.path.expandvars(r"%LOCALAPPDATA%\GOG.com\Galaxy\plugins\installed"))
    if SYSTEM == "Darwin":
        return Path.home() / "Library/Application Support/GOG.com/Galaxy/plugins/installed"
    raise Exit(f"Unsupported system: {SYSTEM}")


def clean_output(output: Path):
    if output.exists():
        print(f"--> Removing {output}")
        shutil.rmtree(output)


def strip_build_artifacts(output: Path):
    for pattern in ("**/test_*.py", "**/*_test.py", "**/__pycache__"):
        for path in glob(str(output / pattern), recursive=True):
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
            else:
                os.remove(path)


def sync_manifest_version(output: Path):
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["version"] = load_version()
    manifest_path.write_text(json.dumps(manifest, indent=4), encoding="utf-8")


def install_dependencies(output_path: Path):
    uv_cmd = [
        uv_executable(),
        "pip",
        "install",
        "-r",
        str(BASE_DIR / "requirements" / "app.txt"),
        "--target",
        str(output_path),
        "--python-version",
        "3.13",
        "--python-platform",
        uv_platform(),
        "--only-binary",
        ":all:",
        "--upgrade",
    ]
    print("--> Installing dependencies with uv")
    subprocess.run(uv_cmd, check=True)


def copy_source_files(output_path: Path):
    print("--> Copying source files")
    for item in SRC_DIR.iterdir():
        dest = output_path / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)


def make_release_zip(build_dir: Path, zip_path: Path):
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(build_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(build_dir).as_posix())
    print(f"--> Release zip: {zip_path}")


@task
def requirements(c):
    """Install development dependencies."""
    c.run(f"{uv_executable()} pip install -r requirements/dev.txt")


@task(optional=["output"])
def build(c, output="build"):
    """Build plugin package for local GOG Galaxy."""
    output_path = BASE_DIR / output
    clean_output(output_path)
    output_path.mkdir(parents=True)

    install_dependencies(output_path)
    copy_source_files(output_path)
    strip_build_artifacts(output_path)
    sync_manifest_version(output_path)
    print(f"--> Build complete: {output_path}")


@task(optional=["output", "dist"])
def release(c, output="build", dist="dist"):
    """Build plugin and create a GOG-compatible release zip (windows.zip or macos.zip)."""
    build(c, output=output)
    build_dir = BASE_DIR / output
    zip_path = BASE_DIR / dist / release_zip_name()
    make_release_zip(build_dir, zip_path)


def install_plugin(output_path: Path, dst: Path):
    if dst.exists():
        try:
            shutil.rmtree(dst)
            shutil.copytree(output_path, dst)
            return
        except PermissionError:
            print("--> Galaxy is running; overlaying plugin files in place")
            shutil.copytree(output_path, dst, dirs_exist_ok=True)
            return
    shutil.copytree(output_path, dst)


def verify_install(dst: Path):
    helpers = dst / "aiohttp" / "_websocket" / "helpers.py"
    if not helpers.is_file():
        raise Exit(
            f"Incomplete install: missing {helpers}. "
            "Fully quit GOG Galaxy and run `invoke install` again."
        )


@task(optional=["output"])
def install(c, output="build"):
    """Install built plugin into local GOG Galaxy."""
    output_path = BASE_DIR / output
    build(c, output=output)

    dst = plugins_dir() / f"psn_{GUID}"
    legacy_dst = plugins_dir() / f"psn_{LEGACY_GUID}"
    if legacy_dst.exists() and legacy_dst != dst:
        print(f"--> Removing legacy plugin folder {legacy_dst}")
        try:
            shutil.rmtree(legacy_dst)
        except PermissionError:
            print("--> Could not remove legacy folder; quit Galaxy and delete it manually")
    install_plugin(output_path, dst)
    verify_install(dst)
    print(f"--> Installed to {dst}")


@task
def test(c):
    """Run unit tests."""
    c.run(f"{sys.executable} -m pytest")
