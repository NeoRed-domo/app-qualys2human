"""Build script — compiles frontend, prepares embedded Python with deps, collects backend.

Usage:
    python scripts/build.py [--output-dir dist]

Produces a `dist/` folder with:
    dist/
    ├── python/          (embedded Python 3.12 + all backend dependencies)
    ├── app/
    │   ├── backend/     (Python source + alembic)
    │   └── frontend/    (Vite production build → static files)
    ├── updater/         (Q2H-Updater service source)
    └── data/            (branding assets)
"""

import argparse
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).absolute().parent.parent
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"
UPDATER_DIR = ROOT / "updater"
DATA_DIR = ROOT / "data"
PREREQS_DIR = ROOT / "prerequisites"


def run(cmd: list[str], cwd: Path | None = None, env=None):
    """Run a subprocess, printing output live."""
    print(f"  > {' '.join(cmd)}")
    # shell=True needed on Windows for commands like npm, npx (they are .cmd scripts)
    result = subprocess.run(cmd, cwd=cwd, env=env, shell=(os.name == "nt"))
    if result.returncode != 0:
        print(f"  ERROR: Command failed with exit code {result.returncode}")
        sys.exit(1)


def build_frontend(output: Path):
    """Build React frontend with Vite."""
    print("\n=== Building frontend ===")
    run(["npm", "install"], cwd=FRONTEND_DIR)
    run(["npx", "vite", "build"], cwd=FRONTEND_DIR)

    src = FRONTEND_DIR / "dist"
    dst = output / "app" / "frontend"
    if dst.exists():
        shutil.rmtree(dst, onexc=_force_remove_readonly)
    shutil.copytree(src, dst)
    print(f"  Frontend build copied to {dst}")


def _force_remove_readonly(func, path, exc_info):
    """Handle Windows errors during rmtree (read-only files, locked __pycache__)."""
    import stat
    os.chmod(path, stat.S_IWRITE)
    func(path)


def prepare_python(output: Path):
    """Prepare embedded Python with all backend dependencies pre-installed."""
    print("\n=== Preparing embedded Python ===")
    dst = output / "python"
    if dst.exists():
        shutil.rmtree(dst, onexc=_force_remove_readonly)

    # Find the embedded Python — either a .zip or an already-extracted directory
    embed_dir = None
    embed_zip = None

    # Option 1: already-extracted directory (e.g. prerequisites/python-3.12-embed-amd64/)
    for candidate in sorted(PREREQS_DIR.glob("python-*-embed-*")):
        if candidate.is_dir() and (candidate / "python.exe").exists():
            embed_dir = candidate
            break

    # Option 2: zip file in prerequisites/python-embed/
    if not embed_dir:
        zip_dir = PREREQS_DIR / "python-embed"
        if zip_dir.exists():
            zips = list(zip_dir.glob("python-*.zip"))
            if zips:
                embed_zip = zips[0]

    if not embed_dir and not embed_zip:
        print("  WARNING: No embedded Python found in prerequisites/")
        print("  Either place the extracted folder (python-3.12-embed-amd64/)")
        print("  or a .zip in prerequisites/python-embed/")
        print("  Falling back to venv-based build...")
        _fallback_venv(output)
        return

    if embed_dir:
        print(f"  Copying {embed_dir.name}...")
        shutil.copytree(embed_dir, dst)
    else:
        print(f"  Extracting {embed_zip.name}...")
        with zipfile.ZipFile(embed_zip, "r") as zf:
            zf.extractall(dst)

    # Enable pip in embedded Python by editing python312._pth
    pth_files = list(dst.glob("python*._pth"))
    if pth_files:
        pth = pth_files[0]
        content = pth.read_text()
        # Uncomment "import site" line
        content = content.replace("#import site", "import site")
        pth.write_text(content)
        print(f"  Enabled site-packages in {pth.name}")

    # Install pip into embedded Python
    python_exe = dst / "python.exe"
    if not python_exe.exists():
        print("  ERROR: python.exe not found in embedded Python")
        sys.exit(1)

    # Download and run get-pip.py
    get_pip = dst / "get-pip.py"
    if not get_pip.exists():
        import urllib.request
        print("  Downloading get-pip.py...")
        urllib.request.urlretrieve("https://bootstrap.pypa.io/get-pip.py", get_pip)

    run([str(python_exe), str(get_pip), "--no-warn-script-location"], cwd=dst)

    # Install setuptools (needed to build backend from pyproject.toml)
    print("  Installing setuptools...")
    run([str(python_exe), "-m", "pip", "install", "setuptools", "--no-warn-script-location"])

    # Install backend dependencies into the embedded Python
    site_packages = dst / "Lib" / "site-packages"
    site_packages.mkdir(parents=True, exist_ok=True)

    print("  Installing backend dependencies...")
    run([
        str(python_exe), "-m", "pip", "install",
        "--target", str(site_packages),
        "--no-warn-script-location",
        str(BACKEND_DIR),
    ])

    # Cleanup get-pip
    if get_pip.exists():
        get_pip.unlink()

    print(f"  Embedded Python ready at {dst}")


def _fallback_venv(output: Path):
    """Fallback: create a venv if no embedded Python available."""
    dst = output / "python"
    print("  Creating virtual environment (fallback)...")
    run([sys.executable, "-m", "venv", str(dst)])

    if os.name == "nt":
        pip = str(dst / "Scripts" / "pip.exe")
    else:
        pip = str(dst / "bin" / "pip")

    run([pip, "install", "--no-cache-dir", str(BACKEND_DIR)])


def collect_backend(output: Path):
    """Copy backend source (without creating a venv — deps are in embedded Python)."""
    print("\n=== Collecting backend source ===")
    dst = output / "app" / "backend"
    if dst.exists():
        shutil.rmtree(dst, onexc=_force_remove_readonly)

    # Copy source
    src_dir = BACKEND_DIR / "src"
    shutil.copytree(src_dir, dst / "src")

    # Copy pyproject.toml
    shutil.copy2(BACKEND_DIR / "pyproject.toml", dst / "pyproject.toml")

    # Copy alembic config and migrations
    alembic_ini = BACKEND_DIR / "alembic.ini"
    if alembic_ini.exists():
        shutil.copy2(alembic_ini, dst / "alembic.ini")
    alembic_dir = BACKEND_DIR / "alembic"
    if alembic_dir.exists():
        shutil.copytree(alembic_dir, dst / "alembic")

    print(f"  Backend source collected to {dst}")


def collect_data(output: Path):
    """Copy data assets (branding, etc.)."""
    print("\n=== Collecting data assets ===")
    dst = output / "data"
    if dst.exists():
        shutil.rmtree(dst, onexc=_force_remove_readonly)
    if DATA_DIR.exists():
        shutil.copytree(DATA_DIR, dst)
        print(f"  Data copied to {dst}")
    else:
        print("  No data directory found, skipping")


def collect_updater(output: Path):
    """Copy updater service source (excluding tests)."""
    print("\n=== Collecting updater source ===")
    dst = output / "updater"
    if dst.exists():
        shutil.rmtree(dst, onexc=_force_remove_readonly)

    if UPDATER_DIR.exists():
        shutil.copytree(
            UPDATER_DIR, dst,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "tests", "test_*"),
        )
        print(f"  Updater source copied to {dst}")
    else:
        print("  No updater directory found, skipping")


def main():
    parser = argparse.ArgumentParser(description="Build Qualys2Human for deployment")
    parser.add_argument("--output-dir", default="dist", help="Output directory (default: dist)")
    parser.add_argument("--skip-frontend", action="store_true", help="Skip frontend build")
    parser.add_argument("--skip-backend", action="store_true", help="Skip backend collection")
    parser.add_argument("--skip-python", action="store_true", help="Skip Python preparation")
    args = parser.parse_args()

    output = ROOT / args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    print(f"Build output: {output}")

    if not args.skip_frontend:
        build_frontend(output)
    if not args.skip_python:
        prepare_python(output)
    if not args.skip_backend:
        collect_backend(output)
    collect_data(output)
    collect_updater(output)

    print(f"\n=== Build complete: {output} ===")


if __name__ == "__main__":
    main()
