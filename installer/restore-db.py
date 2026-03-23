"""Restore Q2H database from a backup.

Lists available backups and restores the selected one.
Can also restore application files (config, app, python, etc.)

Usage:
    python restore-db.py
    python restore-db.py --install-dir C:\Q2H
    python restore-db.py --install-dir C:\Q2H --backup 20260315_213047
    python restore-db.py --install-dir C:\Q2H --backup 20260315_213047 --with-files
"""

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


def load_config(config_path: Path) -> dict:
    """Minimal YAML parser (no PyYAML dependency)."""
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


def find_install_dir(args_install_dir=None) -> Path:
    """Auto-detect Q2H install directory."""
    if args_install_dir:
        return Path(args_install_dir).resolve()
    if os.environ.get("Q2H_CONFIG"):
        return Path(os.environ["Q2H_CONFIG"]).parent.resolve()

    # Search common locations on C: D: E: F:
    for drive in ["C:", "D:", "E:", "F:"]:
        for name in ["Q2H", "Qualys2Human"]:
            candidate = Path(drive) / name
            if (candidate / "config.yaml").exists():
                return candidate.resolve()

    if Path("config.yaml").exists():
        return Path(".").resolve()

    print("ERROR: Cannot find Q2H install directory.")
    print("  Run from the install dir, or use --install-dir C:\\Q2H")
    sys.exit(1)


def list_backups(install_dir: Path) -> list[tuple[str, Path]]:
    """List available backups with their SQL dump status."""
    backups_dir = install_dir / "backups"
    if not backups_dir.exists():
        return []

    result = []
    for entry in sorted(backups_dir.iterdir(), reverse=True):
        if entry.is_dir():
            sql_file = entry / "qualys2human.sql"
            result.append((entry.name, entry, sql_file.exists()))
    return result


def format_backup_name(name: str) -> str:
    """Format '20260315_213047' as '2026-03-15 21:30:47'."""
    try:
        return f"{name[:4]}-{name[4:6]}-{name[6:8]} {name[9:11]}:{name[11:13]}:{name[13:15]}"
    except (IndexError, ValueError):
        return name


def restore_database(install_dir: Path, backup_dir: Path, config: dict):
    """Restore database from SQL dump."""
    dump_file = backup_dir / "qualys2human.sql"
    if not dump_file.exists():
        print("  ERROR: No SQL dump found in this backup!")
        return False

    dump_size_mb = dump_file.stat().st_size / (1024 * 1024)
    print(f"  SQL dump: {dump_file.name} ({dump_size_mb:.1f} MB)")

    db = config.get("database", {})
    db_host = str(db.get("host", "localhost"))
    db_port = str(db.get("port", "5432"))
    db_name = str(db.get("name", "qualys2human"))
    db_user = str(db.get("user", "q2h"))
    db_password = str(db.get("password", ""))

    psql = install_dir / "pgsql" / "bin" / "psql.exe"
    if not psql.exists():
        psql = "psql"

    env = {**os.environ, "PGPASSWORD": db_password}
    psql_args = [str(psql), "-h", db_host, "-p", db_port, "-U", db_user, "-d", db_name]

    # Step 1: Drop and recreate schema
    print("  Dropping existing schema...")
    result = subprocess.run(
        psql_args + ["-c", "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"],
        env=env, capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        print(f"  WARNING: Drop schema returned errors: {result.stderr.strip()[:200]}")

    # Step 2: Restore dump
    print(f"  Restoring database (this may take a while for large databases)...")
    try:
        result = subprocess.run(
            psql_args + ["-f", str(dump_file)],
            env=env, capture_output=True, text=True, timeout=7200,
        )
    except subprocess.TimeoutExpired:
        print("  ERROR: Database restore timed out after 2 hours!")
        return False

    if result.returncode == 0:
        print("  Database restored successfully.")
        return True
    else:
        stderr = (result.stderr or "").strip()
        if stderr:
            print(f"  WARNING: Restore completed with warnings: {stderr[:300]}")
        print("  Database restore completed (check warnings above).")
        return True


def restore_files(install_dir: Path, backup_dir: Path):
    """Restore application files from backup."""
    restored = []

    # Single files
    for name in ["config.yaml", ".env"]:
        src = backup_dir / name
        if src.exists():
            shutil.copy2(str(src), str(install_dir / name))
            restored.append(name)

    # Directories
    for dirname in ["certs", "keys", "data", "updater", "app", "python"]:
        src = backup_dir / dirname
        dst = install_dir / dirname
        if src.exists():
            if dst.exists():
                shutil.rmtree(str(dst))
            shutil.copytree(str(src), str(dst))
            restored.append(f"{dirname}/")

    # Re-patch ._pth after restoring python/
    python_dir = install_dir / "python"
    if python_dir.exists():
        pth_files = list(python_dir.glob("python*._pth"))
        if pth_files:
            pth = pth_files[0]
            content = pth.read_text(encoding="utf-8")
            src_rel = "..\\app\\backend\\src"
            if src_rel not in content:
                content = src_rel + "\n" + content
                pth.write_text(content, encoding="utf-8")
                restored.append("python._pth (patched)")

    return restored


def refresh_matview(install_dir: Path, config: dict):
    """Refresh materialized view after database restore."""
    db = config.get("database", {})
    db_host = str(db.get("host", "localhost"))
    db_port = str(db.get("port", "5432"))
    db_name = str(db.get("name", "qualys2human"))
    db_user = str(db.get("user", "q2h"))
    db_password = str(db.get("password", ""))

    psql = install_dir / "pgsql" / "bin" / "psql.exe"
    if not psql.exists():
        psql = "psql"

    env = {**os.environ, "PGPASSWORD": db_password}
    psql_args = [str(psql), "-h", db_host, "-p", db_port, "-U", db_user, "-d", db_name]

    print("  Refreshing materialized view...")
    result = subprocess.run(
        psql_args + ["-c", "REFRESH MATERIALIZED VIEW latest_vulns;"],
        env=env, capture_output=True, text=True, timeout=3600,
    )
    if result.returncode == 0:
        print("  Materialized view refreshed.")
    else:
        print(f"  WARNING: Matview refresh: {(result.stderr or '').strip()[:200]}")


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Restore Q2H database (and optionally files) from a backup",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n"
               "  python restore-db.py\n"
               "  python restore-db.py --install-dir C:\\Q2H\n"
               "  python restore-db.py --backup 20260315_213047\n"
               "  python restore-db.py --backup 20260315_213047 --with-files\n"
    )
    parser.add_argument("--install-dir", default=None, help="Q2H install directory")
    parser.add_argument("--backup", default=None, help="Backup name (e.g. 20260315_213047)")
    parser.add_argument("--with-files", action="store_true",
                        help="Also restore application files (app/, python/, config, etc.)")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()

    install_dir = find_install_dir(args.install_dir)
    config_path = install_dir / "config.yaml"

    if not config_path.exists():
        print(f"ERROR: config.yaml not found at {config_path}")
        sys.exit(1)

    print("=" * 60)
    print("  Q2H — Database Restore")
    print("=" * 60)
    print(f"  Install dir: {install_dir}")
    print()

    # List backups
    backups = list_backups(install_dir)
    if not backups:
        print("ERROR: No backups found in", install_dir / "backups")
        sys.exit(1)

    # Select backup
    backup_dir = None
    if args.backup:
        for name, path, has_sql in backups:
            if name == args.backup:
                backup_dir = path
                break
        if not backup_dir:
            print(f"ERROR: Backup '{args.backup}' not found.")
            print("Available backups:")
            for name, _, has_sql in backups:
                sql_status = "OK" if has_sql else "NO SQL"
                print(f"  {name} ({format_backup_name(name)}) [{sql_status}]")
            sys.exit(1)
    else:
        print("Available backups:")
        print()
        for i, (name, path, has_sql) in enumerate(backups, 1):
            sql_status = "SQL dump available" if has_sql else "NO SQL DUMP"
            size_info = ""
            sql_file = path / "qualys2human.sql"
            if sql_file.exists():
                size_mb = sql_file.stat().st_size / (1024 * 1024)
                size_info = f" ({size_mb:.1f} MB)"
            print(f"  [{i}] {format_backup_name(name)}  —  {sql_status}{size_info}")
        print()

        try:
            choice = input(f"Select backup to restore [1-{len(backups)}]: ").strip()
            idx = int(choice) - 1
            if idx < 0 or idx >= len(backups):
                raise ValueError
        except (ValueError, EOFError, KeyboardInterrupt):
            print("\nAborted.")
            sys.exit(0)

        _, backup_dir, _ = backups[idx]

    print()
    print(f"  Selected: {backup_dir.name} ({format_backup_name(backup_dir.name)})")

    # Show what will be restored
    sql_exists = (backup_dir / "qualys2human.sql").exists()
    print(f"  Database:  {'YES' if sql_exists else 'NO (no SQL dump!)'}")
    print(f"  Files:     {'YES' if args.with_files else 'NO (use --with-files to include)'}")
    print()

    if not sql_exists and not args.with_files:
        print("ERROR: No SQL dump in this backup and --with-files not specified. Nothing to restore.")
        sys.exit(1)

    # Confirmation
    if not args.yes:
        print("  WARNING: This will OVERWRITE the current database!")
        if args.with_files:
            print("  WARNING: This will also OVERWRITE application files!")
        print()
        try:
            confirm = input("  Are you sure? (type 'yes' to confirm): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            sys.exit(0)
        if confirm.lower() != "yes":
            print("Aborted.")
            sys.exit(0)

    config = load_config(config_path)
    print()

    # Stop Q2H
    print("[1/5] Stopping services...")
    subprocess.run(["sc", "stop", "Qualys2Human-Updater"],
                   capture_output=True, text=True, timeout=15)
    subprocess.run(["sc", "stop", "Qualys2Human"],
                   capture_output=True, text=True, timeout=15)
    time.sleep(3)
    print("      Done.")

    # Restore files (if requested)
    if args.with_files:
        print("[2/5] Restoring application files...")
        restored = restore_files(install_dir, backup_dir)
        for name in restored:
            print(f"      Restored {name}")
        print("      Done.")
    else:
        print("[2/5] Skipping file restore (use --with-files to include)")

    # Restore database
    if sql_exists:
        print("[3/5] Restoring database...")
        success = restore_database(install_dir, backup_dir, config)
        if not success:
            print("  ERROR: Database restore failed! Service not restarted.")
            sys.exit(1)
    else:
        print("[3/5] Skipping database restore (no SQL dump)")

    # Refresh matview
    if sql_exists:
        print("[4/5] Refreshing materialized view...")
        refresh_matview(install_dir, config)
    else:
        print("[4/5] Skipping matview refresh")

    # Restart Q2H
    print("[5/5] Restarting Q2H service...")
    subprocess.run(["sc", "start", "Qualys2Human"],
                   capture_output=True, text=True, timeout=15)
    print("      Done.")

    print()
    print("=" * 60)
    print("  Restore complete!")
    if sql_exists:
        print(f"  Database restored from: {backup_dir.name}")
    if args.with_files:
        print(f"  Files restored from: {backup_dir.name}")
    print("=" * 60)


if __name__ == "__main__":
    main()
