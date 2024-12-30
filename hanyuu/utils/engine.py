from typing import Dict, Type

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class LazyEngine:
    def __init__(self, url: str, base: Type[DeclarativeBase]) -> None:
        self.connected = False
        self.url = url
        self.base = base

    def connect(self, echo: bool = False) -> None:
        self._engine = create_async_engine(url=self.url, echo=echo)
        self._async_session = async_sessionmaker(self._engine, class_=AsyncSession)
        self.connected = True

    @property
    def async_session(self) -> async_sessionmaker[AsyncSession]:
        return self._async_session

    async def create_tables(self) -> None:
        async with self._engine.begin() as conn:
            await conn.run_sync(self.base.metadata.create_all)

    async def drop_tables(self) -> None:
        async with self._engine.begin() as conn:
            await conn.run_sync(self.base.metadata.drop_all)

    async def recreate_tables(self) -> None:
        await self.drop_tables()
        await self.create_tables()


engines: Dict[str, LazyEngine] = {}


async def get_engine(url: str, base: Type[DeclarativeBase], echo: bool = False) -> None:
    global engines
    if url not in engines:
        engine = LazyEngine(url, base)
        engine.connect(echo=echo)
        await engine.create_tables()
        engines[url] = engine
    return engines[url]
