from typing import Optional

from sqlalchemy import URL

import hanyuu.helpers.engine as engine
from hanyuu.config import get_settings
from hanyuu.helpers.engine import LazyEngine

from .models import Base

url: Optional[str] = None


async def get_engine(echo: bool = False) -> LazyEngine:
    global url
    if url is None:
        settings = get_settings()
        url = URL.create(
            drivername="postgresql+asyncpg",
            database=settings.db_name,
            username=settings.db_username,
            password=settings.db_password,
            host=settings.db_host,
            port=settings.db_port,
        )
    return await engine.get_engine(url, Base, echo=echo)
