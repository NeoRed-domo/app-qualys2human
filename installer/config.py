"""Configuration generation — config.yaml, JWT secret, master key."""

import os

from pathlib import Path

from utils import generate_password, generate_secret


def generate_config(
    install_dir: Path,
    *,
    server_host: str = "0.0.0.0",
    server_port: int = 8443,
    db_host: str = "localhost",
    db_port: int = 5432,
    db_name: str = "qualys2human",
    db_user: str = "q2h",
    db_password: str = "",
    logger=None,
) -> Path:
    """Generate config.yaml from parameters."""
    config = {
        "server": {
            "host": server_host,
            "port": server_port,
            "tls_cert": "./certs/server.crt",
            "tls_key": "./certs/server.key",
        },
        "database": {
            "host": db_host,
            "port": db_port,
            "name": db_name,
            "user": db_user,
            "password": db_password,
            "encryption_key_file": "./keys/master.key",
        },
        "watcher": {
            "enabled": False,
            "paths": [],
            "poll_interval": 10,
            "stable_seconds": 5,
        },
    }

    config_path = install_dir / "config.yaml"
    # Write YAML manually to avoid PyYAML dependency in installer
    lines = []
    for section, values in config.items():
        if isinstance(values, dict):
            lines.append(f"{section}:")
            for k, v in values.items():
                if isinstance(v, bool):
                    lines.append(f"  {k}: {'true' if v else 'false'}")
                elif isinstance(v, list):
                    lines.append(f"  {k}: []")
                else:
                    lines.append(f"  {k}: {v}")
        else:
            lines.append(f"{section}: {values}")
    config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("[OK] config.yaml genere: %s", config_path)
    return config_path


def generate_jwt_secret(install_dir: Path, logger=None) -> str:
    """Generate and save a random JWT secret."""
    secret = generate_secret(64)
    env_file = install_dir / ".env"
    lines = []
    if env_file.exists():
        lines = env_file.read_text(encoding="utf-8").splitlines()
        lines = [l for l in lines if not l.startswith("JWT_SECRET=")]
    lines.append(f"JWT_SECRET={secret}")
    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("[OK] JWT secret genere")
    return secret


def create_master_key(install_dir: Path, logger=None) -> bool:
    """Create encryption master key (DPAPI-protected on Windows)."""
    keys_dir = install_dir / "keys"
    keys_dir.mkdir(parents=True, exist_ok=True)
    key_file = keys_dir / "master.key"

    if key_file.exists():
        logger.info("[OK] Master key existante conservee")
        return True

    raw_key = os.urandom(32)  # AES-256

    if os.name == "nt":
        try:
            import ctypes
            import ctypes.wintypes

            class DATA_BLOB(ctypes.Structure):
                _fields_ = [
                    ("cbData", ctypes.wintypes.DWORD),
                    ("pbData", ctypes.c_void_p),
                ]

            _CryptProtectData = ctypes.windll.crypt32.CryptProtectData
            _CryptProtectData.argtypes = [
                ctypes.POINTER(DATA_BLOB),  # pDataIn
                ctypes.c_wchar_p,           # szDataDescr
                ctypes.POINTER(DATA_BLOB),  # pOptionalEntropy
                ctypes.c_void_p,            # pvReserved
                ctypes.c_void_p,            # pPromptStruct
                ctypes.wintypes.DWORD,      # dwFlags
                ctypes.POINTER(DATA_BLOB),  # pDataOut
            ]
            _CryptProtectData.restype = ctypes.wintypes.BOOL

            buf = (ctypes.c_ubyte * len(raw_key))(*raw_key)
            input_blob = DATA_BLOB(len(raw_key), ctypes.cast(buf, ctypes.c_void_p))
            output_blob = DATA_BLOB()

            if _CryptProtectData(
                ctypes.byref(input_blob), "Q2H Master Key",
                None, None, None, 0, ctypes.byref(output_blob),
            ):
                protected = (ctypes.c_ubyte * output_blob.cbData).from_address(
                    output_blob.pbData
                )
                key_file.write_bytes(bytes(protected))
                ctypes.windll.kernel32.LocalFree(output_blob.pbData)
                logger.info("[OK] Master key generee (DPAPI protegee)")
                return True
        except Exception as e:
            logger.warning("DPAPI non disponible: %s. Sauvegarde en clair.", e)

    key_file.write_bytes(raw_key)
    logger.info("[OK] Master key generee (attention: non chiffree)")
    return True


def run_all(install_dir: Path, *, db_password: str, server_port: int = 8443,
            logger=None) -> bool:
    """Generate all configuration files."""
    generate_config(
        install_dir,
        server_port=server_port,
        db_password=db_password,
        logger=logger,
    )
    generate_jwt_secret(install_dir, logger=logger)
    create_master_key(install_dir, logger=logger)
    return True
