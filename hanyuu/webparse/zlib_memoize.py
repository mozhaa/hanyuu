import zlib
from datetime import datetime
from functools import wraps
from typing import *

from sqlalchemy import LargeBinary, func, null, select
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(AsyncAttrs, DeclarativeBase):
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class Item(Base):
    __tablename__ = "page"

    key: Mapped[str] = mapped_column(nullable=False)
    value: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)


def zlib_memoize(filename: str, key_creator: Callable[..., str], encoding: str = "utf-8") -> Callable:
    """Cache with unbounded storage and zlib compression"""

    def wrapper(user_function: Callable[..., Awaitable[Optional[str]]]) -> Callable[..., Awaitable[Optional[str]]]:
        engine: AsyncEngine = None
        async_session: async_sessionmaker[AsyncSession] = None

        @wraps(user_function)
        async def wrapped(*args, **kwargs) -> Optional[str]:
            nonlocal engine, async_session
            if engine is None:
                engine = create_async_engine(f"sqlite+aiosqlite:///{filename}")
                async_session = async_sessionmaker(engine, class_=AsyncSession)
                async with engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)

            key = key_creator(*args, **kwargs)
            async with async_session() as session:
                item = await session.scalar(select(Item).where(Item.key == key))
                if item is not None:
                    return zlib.decompress(item.value).decode(encoding=encoding) if item.value is not None else None
            value = await user_function(*args, **kwargs)
            async with async_session() as session:
                c_value = zlib.compress(value.encode(encoding=encoding)) if value is not None else null()
                session.add(Item(key=key, value=c_value))
                await session.commit()
            return value

        return wrapped

    return wrapper
