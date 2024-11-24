from typing import AsyncIterator

from sqlalchemy import URL
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ..config import get_settings
from .models import Base


class Database:
    def __init__(self) -> None:
        self.connected = False

    def _get_database_url() -> str:
        settings = get_settings()
        return URL.create(
            drivername="postgresql+asyncpg",
            database=settings.db_name,
            username=settings.db_username,
            password=settings.db_password,
            host=settings.db_host,
            port=settings.db_port,
        )

    def connect(self, echo: bool = False) -> None:
        self._engine = create_async_engine(url=Database._get_database_url(), echo=echo)
        self._async_session = async_sessionmaker(self._engine, class_=AsyncSession)
        self.connected = True

    @property
    def async_session(self) -> AsyncSession:
        return self._async_session

    async def create_tables(self) -> None:
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def drop_tables(self) -> None:
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    async def recreate_tables(self) -> None:
        await self.drop_tables()
        await self.create_tables()


db = Database()


async def get_session() -> AsyncIterator[AsyncSession]:
    if not db.connected:
        db.connect()
        await db.create_tables()
    async with db.async_session() as session:
        yield session
