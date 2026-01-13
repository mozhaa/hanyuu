import os
import platform
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    db_name: str
    db_username: str
    db_password: str
    db_host: str
    db_port: int

    qbt_host: str
    qbt_port: int
    qbt_username: str
    qbt_password: str

    resources_dir: Optional[str | Path] = None
    logs_dir: Optional[str | Path] = None

    model_config = SettingsConfigDict(env_file=".env")

    ytdlp_cookiesfrombrowser: str

    @model_validator(mode="after")
    def set_default_paths(self) -> "Settings":
        sys_name = platform.system()

        resources_dir_defaults = {
            "Linux": "~/.local/share/hanyuu",
            "Windows": str(Path(os.getenv("LOCALAPPDATA", "~/AppData/Local")) / "hanyuu" / "resources"),
            "Darwin": "~/Library/Application Support/hanyuu",
        }
        if self.resources_dir is None:
            if sys_name in resources_dir_defaults:
                self.resources_dir = resources_dir_defaults[sys_name]
            else:
                raise ValueError(
                    f"RESOURCES_DIR is not provided and OS does not match any of {resources_dir_defaults.keys()}"
                )
        self.resources_dir = Path(self.resources_dir).expanduser().resolve()
        self.resources_dir.mkdir(parents=True, exist_ok=True)

        logs_dir_defaults = {
            "Linux": "~/.local/state/hanyuu",
            "Windows": str(Path(os.getenv("LOCALAPPDATA", "~/AppData/Local")) / "hanyuu" / "logs"),
            "Darwin": "~/Library/Logs/hanyuu",
        }
        if self.logs_dir is None:
            if sys_name in logs_dir_defaults:
                self.logs_dir = logs_dir_defaults[sys_name]
            else:
                raise ValueError(f"LOGS_DIR is not provided and OS does not match any of {logs_dir_defaults.keys()}")
        self.logs_dir = Path(self.logs_dir).expanduser().resolve()
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore


def getenv(key: str) -> Any:
    return get_settings().__getattribute__(key)
