"""Reset stuck upgrade state.

Reads config.yaml to get DB credentials, cleans up files and database.
Run from the install directory (or pass --install-dir):

    python reset-upgrade.py
    python reset-upgrade.py --install-dir C:\Q2H
"""

import os
import subprocess
import sys
from pathlib import Path


def load_config(config_path: Path) -> dict:
    """Minimal YAML parser (no PyYAML dependency needed)."""
    result = {}
    current_section = None
    for line in config_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not line.startswith(" ") and stripped.endswith(":"):
            current_section = stripped[:-1].strip().strip('"')
            result[current_section] = {}
        elif current_section and ":" in stripped:
            key, _, val = stripped.partition(":")
            key = key.strip().strip('"')
            val = val.strip().strip('"').strip("'")
            result[current_section][key] = val
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Reset stuck Q2H upgrade state")
    parser.add_argument("--install-dir", default=None, help="Q2H install directory")
    args = parser.parse_args()

    # Determine install dir
    if args.install_dir:
        install_dir = Path(args.install_dir)
    elif os.environ.get("Q2H_CONFIG"):
        install_dir = Path(os.environ["Q2H_CONFIG"]).parent
    elif Path("config.yaml").exists():
        install_dir = Path(".")
    elif Path("C:/Q2H/config.yaml").exists():
        install_dir = Path("C:/Q2H")
    else:
        print("ERROR: Cannot find Q2H install directory.")
        print("  Run from the install dir, or use --install-dir C:\\Q2H")
        sys.exit(1)

    install_dir = install_dir.resolve()
    config_path = install_dir / "config.yaml"

    if not config_path.exists():
        print(f"ERROR: config.yaml not found at {config_path}")
        sys.exit(1)

    print(f"=== Q2H Reset Upgrade State ===")
    print(f"Install dir: {install_dir}")
    print()

    # 1. Stop Updater service
    print("[1/4] Stopping Updater service...")
    subprocess.run(["sc", "stop", "Qualys2Human-Updater"],
                   capture_output=True, timeout=15)
    print("      Done.")

    # 2. Clean up files
    print("[2/4] Removing upgrade files...")
    for name in ("upgrade-request.json", "upgrade-status.json"):
        f = install_dir / name
        if f.exists():
            f.unlink()
            print(f"      Deleted {name}")
    print("      Done.")

    # 3. Read config and fix DB
    print("[3/4] Resetting upgrade schedules in database...")
    config = load_config(config_path)
    db = config.get("database", {})
    db_host = db.get("host", "localhost")
    db_port = db.get("port", "5432")
    db_name = db.get("name", "qualys2human")
    db_user = db.get("user", "q2h")
    db_password = db.get("password", "")

    psql = install_dir / "pgsql" / "bin" / "psql.exe"
    if not psql.exists():
        print(f"      WARNING: psql not found at {psql}, trying system PATH...")
        psql = "psql"

    sql = (
        "UPDATE upgrade_schedules "
        "SET status='cancelled', completed_at=NOW(), "
        "error_message='Manual reset via reset-upgrade script' "
        "WHERE status IN ('running', 'pending');"
    )

    env = {**os.environ, "PGPASSWORD": db_password}
    result = subprocess.run(
        [str(psql), "-h", db_host, "-p", str(db_port),
         "-U", db_user, "-d", db_name, "-c", sql],
        capture_output=True, text=True, timeout=30, env=env,
    )

    if result.returncode == 0:
        print(f"      {result.stdout.strip()}")
    else:
        print(f"      ERROR: {result.stderr.strip()}")

    # 4. Restart Q2H
    print("[4/4] Restarting Q2H service...")
    subprocess.run(["sc", "stop", "Qualys2Human"],
                   capture_output=True, timeout=15)
    import time
    time.sleep(3)
    subprocess.run(["sc", "start", "Qualys2Human"],
                   capture_output=True, timeout=15)
    print("      Done.")

    print()
    print("=== Reset complete ===")


if __name__ == "__main__":
    main()
