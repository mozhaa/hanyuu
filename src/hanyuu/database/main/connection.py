from dataclasses import dataclass
from typing import Any, Optional

from cachetools import cached
from sqlalchemy import URL
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from hanyuu.config import get_settings


@dataclass
class Engine:
    engine: AsyncEngine
    async_session: async_sessionmaker[AsyncSession]


@cached(cache={}, key=lambda *args, **kwargs: ())
def get_url() -> URL:
    settings = get_settings()
    return URL.create(
        drivername="postgresql+asyncpg",
        database=settings.db_name,
        username=settings.db_username,
        password=settings.db_password,
        host=settings.db_host,
        port=settings.db_port,
    )


@cached(cache={}, key=lambda *args, **kwargs: ())
def get_engine(
    engine_kwargs: Optional[dict[str, Any]] = None, session_kwargs: Optional[dict[str, Any]] = None
) -> Engine:
    engine = create_async_engine(get_url(), **(engine_kwargs or {}))
    async_session = async_sessionmaker(bind=engine, **(session_kwargs or {}))
    return Engine(engine, async_session)
