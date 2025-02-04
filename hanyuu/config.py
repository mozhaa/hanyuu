from functools import lru_cache
from typing import Any

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

    resources_dir: str
    templates_dir: str
    static_dir: str
    src_dir: str

    model_config = SettingsConfigDict(env_file=".env")

    ytdlp_cookiesfrombrowser: str


@lru_cache
def get_settings() -> Settings:
    return Settings()


def getenv(key: str) -> Any:
    return get_settings().__getattribute__(key)
