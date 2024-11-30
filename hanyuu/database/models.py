import enum
from datetime import datetime, time
from typing import List

import sqlalchemy.types as types
from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects import postgresql
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


class IncompleteDate(types.TypeDecorator):
    impl = String
    cache_ok = True
    keys = ["day", "month", "year"]

    def process_bind_param(self, value, dialect):
        return ",".join(map(str, [value[key] or "" for key in IncompleteDate.keys]))

    def process_result_value(self, value, dialect):
        return dict(
            zip(
                IncompleteDate.keys,
                [int(x) if x != "" else None for x in value.split(",")],
            )
        )


class Anime(Base):
    __tablename__ = "anime"

    mal_id: Mapped[int] = mapped_column(primary_key=True)
    anidb_id: Mapped[int] = mapped_column(nullable=False, unique=True, index=True)
    alias: Mapped[str] = mapped_column(nullable=True)

    shiki_title_ro: Mapped[str] = mapped_column(nullable=False)
    shiki_title_ru: Mapped[str] = mapped_column(nullable=True)
    shiki_title_en: Mapped[str] = mapped_column(nullable=True)
    shiki_title_jp: Mapped[str] = mapped_column(nullable=True)
    shiki_url: Mapped[str] = mapped_column(nullable=False)
    shiki_status: Mapped[str] = mapped_column(nullable=True)
    shiki_poster_url: Mapped[str] = mapped_column(nullable=False)
    shiki_poster_thumb_url: Mapped[str] = mapped_column(nullable=False)
    shiki_episodes: Mapped[int] = mapped_column(nullable=False)
    shiki_duration: Mapped[int] = mapped_column(nullable=True)
    shiki_rating: Mapped[float] = mapped_column(nullable=True)
    shiki_ratings_count: Mapped[int] = mapped_column(default=0)
    shiki_planned: Mapped[int] = mapped_column(default=0)
    shiki_completed: Mapped[int] = mapped_column(default=0)
    shiki_watching: Mapped[int] = mapped_column(default=0)
    shiki_dropped: Mapped[int] = mapped_column(default=0)
    shiki_on_hold: Mapped[int] = mapped_column(default=0)
    shiki_age_rating: Mapped[str] = mapped_column(nullable=True)
    shiki_aired_on: Mapped[IncompleteDate] = mapped_column(
        IncompleteDate, nullable=True
    )
    shiki_released_on: Mapped[IncompleteDate] = mapped_column(
        IncompleteDate, nullable=True
    )
    shiki_videos: Mapped[List[List[str]]] = mapped_column(
        postgresql.ARRAY(String, dimensions=2, zero_indexes=True), nullable=False
    )
    shiki_synonyms: Mapped[List[str]] = mapped_column(
        postgresql.ARRAY(String, dimensions=1, zero_indexes=True), nullable=False
    )
    shiki_genres: Mapped[List[str]] = mapped_column(
        postgresql.ARRAY(String, dimensions=1, zero_indexes=True), nullable=False
    )

    qitems: Mapped[List["QItem"]] = relationship(
        back_populates="anime", cascade="all, delete"
    )


class Category(enum.Enum):
    Opening = enum.auto()
    Ending = enum.auto()


class QItem(BaseWithID):
    __tablename__ = "qitem"

    anime_id: Mapped[int] = mapped_column(ForeignKey("anime.mal_id"))
    category: Mapped[Category] = mapped_column(types.Enum(Category), nullable=False)
    number: Mapped[int] = mapped_column(nullable=False)
    song_artist: Mapped[str] = mapped_column(default="")
    song_name: Mapped[str] = mapped_column(default="")

    anime: Mapped["Anime"] = relationship(back_populates="qitems")
    sources: Mapped[List["QItemSource"]] = relationship(cascade="all, delete")
    difficulties: Mapped[List["QItemDifficulty"]] = relationship(cascade="all, delete")

    __table_args__ = (
        UniqueConstraint("anime_id", "category", "number", name="_category_number_uc"),
    )


class QItemSource(BaseWithID):
    __tablename__ = "qitem_source"

    qitem_id: Mapped[int] = mapped_column(ForeignKey("qitem.id"))
    platform: Mapped[str] = mapped_column(nullable=False)
    path: Mapped[str] = mapped_column(nullable=False)
    added_by: Mapped[str] = mapped_column(nullable=False)
    verified: Mapped[bool] = mapped_column(default=False)

    qitem: Mapped["QItem"] = relationship(back_populates="sources")
    timings: Mapped[List["QItemSourceTiming"]] = relationship(cascade="all, delete")


class QItemSourceTiming(BaseWithID):
    __tablename__ = "qitem_source_timing"

    qitem_source_id: Mapped[int] = mapped_column(ForeignKey("qitem_source.id"))
    guess_start: Mapped[time] = mapped_column(default=time.min)
    reveal_start: Mapped[time] = mapped_column(default=time.min)
    added_by: Mapped[str] = mapped_column(nullable=False)

    qitem_source: Mapped["QItemSource"] = relationship(back_populates="timings")


class QItemDifficulty(BaseWithID):
    __tablename__ = "qitem_difficulty"

    qitem_id: Mapped[int] = mapped_column(ForeignKey("qitem.id"))
    value: Mapped[int] = mapped_column(nullable=False)
    added_by: Mapped[str] = mapped_column(nullable=False)

    qitem: Mapped["QItem"] = relationship(back_populates="difficulties")

    __table_args__ = (
        CheckConstraint("value >= 0 AND value <= 100", name="_value_range"),
    )


class AnimeType(enum.Enum):
    TV = enum.auto()
    OVA = enum.auto()
    ONA = enum.auto()
    SPECIAL = enum.auto()
    MOVIE = enum.auto()
    UNKNOWN = enum.auto()


class Status(enum.Enum):
    FINISHED = enum.auto()
    ONGOING = enum.auto()
    UPCOMING = enum.auto()
    UNKNOWN = enum.auto()


class ReleaseSeason(enum.Enum):
    WINTER = enum.auto()
    SPRING = enum.auto()
    SUMMER = enum.auto()
    FALL = enum.auto()
    UNDEFINED = enum.auto()


class AODAnime(Base):
    __tablename__ = "aod_anime"

    mal_id: Mapped[int] = mapped_column(primary_key=True)
    anidb_id: Mapped[int] = mapped_column(nullable=False, unique=True, index=True)
    sources: Mapped[List[str]] = mapped_column(
        postgresql.ARRAY(String, dimensions=1, zero_indexes=True), nullable=False
    )
    poster_url: Mapped[str] = mapped_column(nullable=False)
    poster_thumb_url: Mapped[str] = mapped_column(nullable=False)
    title: Mapped[str] = mapped_column(nullable=False)
    anime_type: Mapped[AnimeType] = mapped_column(default=AnimeType.UNKNOWN)
    status: Mapped[Status] = mapped_column(default=Status.UNKNOWN)
    episodes: Mapped[int] = mapped_column(nullable=False)
    duration: Mapped[int] = mapped_column(nullable=True)
    tags: Mapped[List[str]] = mapped_column(
        postgresql.ARRAY(String, dimensions=1, zero_indexes=True), nullable=False
    )
    synonyms: Mapped[List[str]] = mapped_column(
        postgresql.ARRAY(String, dimensions=1, zero_indexes=True), nullable=False
    )
    related_animes: Mapped[List[str]] = mapped_column(
        postgresql.ARRAY(String, dimensions=1, zero_indexes=True), nullable=False
    )
    release_year: Mapped[int] = mapped_column(nullable=True)
    release_season: Mapped[ReleaseSeason] = mapped_column(
        default=ReleaseSeason.UNDEFINED
    )
