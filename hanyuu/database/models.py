import enum
from datetime import datetime
from typing import *

import sqlalchemy.types as types
from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint, func
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def keyvalgen(obj):
    """Generate attr name/val pairs, filtering out SQLA attrs."""
    excl = ("_sa_adapter", "_sa_instance_state")
    for k, v in vars(obj).items():
        if not k.startswith("_") and not any(hasattr(v, a) for a in excl):
            yield k, v


class Base(AsyncAttrs, DeclarativeBase):
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self):
        params = ", ".join(f"{k}={v}" for k, v in keyvalgen(self))
        return f"{self.__class__.__name__}({params})"


class BaseWithID(Base):
    __abstract__ = True

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)


class Anime(Base):
    __tablename__ = "anime"

    id: Mapped[int] = mapped_column(primary_key=True)
    mal_id: Mapped[int] = mapped_column(nullable=False, unique=True)
    title_ro: Mapped[str] = mapped_column(nullable=False)
    title_en: Mapped[str]
    poster_thumb_url: Mapped[str]
    poster_url: Mapped[str]

    qitems: Mapped[List["QItem"]] = relationship(
        back_populates="anime", cascade="all, delete"
    )


class Category(enum.Enum):
    Opening = enum.auto()
    Ending = enum.auto()


class QItem(BaseWithID):
    __tablename__ = "qitem"

    anime_id: Mapped[int] = mapped_column(ForeignKey("anime.id"))
    category: Mapped[Category] = mapped_column(types.Enum(Category))
    number: Mapped[int]
    song_artist: Mapped[Optional[str]]
    song_name: Mapped[Optional[str]]
    song_anidb_id: Mapped[Optional[int]]

    anime: Mapped["Anime"] = relationship(back_populates="qitems")
    sources: Mapped[List["QItemSource"]] = relationship(cascade="all, delete")
    difficulties: Mapped[List["QItemDifficulty"]] = relationship(cascade="all, delete")

    __table_args__ = (
        UniqueConstraint("anime_id", "category", "number", name="_category_number_uc"),
    )


class QItemSource(BaseWithID):
    __tablename__ = "qitem_source"

    qitem_id: Mapped[int] = mapped_column(ForeignKey("qitem.id"))
    platform: Mapped[str]
    path: Mapped[str]
    added_by: Mapped[str]

    qitem: Mapped["QItem"] = relationship(back_populates="sources")
    timings: Mapped[List["QItemSourceTiming"]] = relationship(cascade="all, delete")


class QItemSourceTiming(BaseWithID):
    __tablename__ = "qitem_source_timing"

    qitem_source_id: Mapped[int] = mapped_column(ForeignKey("qitem_source.id"))
    guess_start: Mapped[datetime]
    reveal_start: Mapped[datetime]
    added_by: Mapped[str]

    qitem_source: Mapped["QItemSource"] = relationship(back_populates="timings")


class QItemDifficulty(BaseWithID):
    __tablename__ = "qitem_difficulty"

    qitem_id: Mapped[int] = mapped_column(ForeignKey("qitem.id"))
    value: Mapped[int]  # 0 - 100
    added_by: Mapped[str]  # manual (user_id from bot), auto (script name)

    qitem: Mapped["QItem"] = relationship(back_populates="difficulties")

    __table_args__ = (
        CheckConstraint("value >= 0 AND value <= 100", name="_value_range"),
    )
