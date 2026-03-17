import os
from pathlib import Path

from pydantic_settings import BaseSettings
import yaml


class DatabaseConfig(BaseSettings):
    host: str = "localhost"
    port: int = 5432
    name: str = "qualys2human"
    user: str = "q2h"
    password: str = "changeme"
    encryption_key_file: str = "./keys/master.key"


class ServerConfig(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8443
    tls_cert: str = "./certs/server.crt"
    tls_key: str = "./certs/server.key"


class WatcherConfig(BaseSettings):
    enabled: bool = False
    paths: list[str] = []
    poll_interval: int = 10  # seconds between poll cycles
    stable_seconds: int = 5  # wait for file to stop growing


class Settings(BaseSettings):
    server: ServerConfig = ServerConfig()
    database: DatabaseConfig = DatabaseConfig()
    watcher: WatcherConfig = WatcherConfig()

    @classmethod
    def from_yaml(cls, path: Path) -> "Settings":
        if path.exists():
            with open(path) as f:
                data = yaml.safe_load(f) or {}
            return cls(**data)
        return cls()


settings: Settings | None = None


def get_settings() -> Settings:
    global settings
    if settings is None:
        env_path = os.environ.get("Q2H_CONFIG")
        if env_path:
            config_path = Path(env_path)
        else:
            config_path = Path(__file__).parent.parent.parent / "config.yaml"
        settings = Settings.from_yaml(config_path)
    return settings
