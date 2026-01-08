"""initial migration

Revision ID: 9350dda64626
Revises:
Create Date: 2026-01-08 19:59:45.224631

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9350dda64626"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "anime",
        sa.Column("mal_id", sa.Integer(), nullable=False),
        sa.Column("anidb_id", sa.Integer(), nullable=False),
        sa.Column("alias", sa.String(), nullable=True),
        sa.Column("shiki_title_ro", sa.String(), nullable=False),
        sa.Column("shiki_title_ru", sa.String(), nullable=True),
        sa.Column("shiki_title_en", sa.String(), nullable=True),
        sa.Column("shiki_title_jp", sa.String(), nullable=True),
        sa.Column("shiki_url", sa.String(), nullable=False),
        sa.Column("shiki_status", sa.String(), nullable=True),
        sa.Column("shiki_poster_url", sa.String(), nullable=False),
        sa.Column("shiki_poster_thumb_url", sa.String(), nullable=False),
        sa.Column("shiki_episodes", sa.Integer(), nullable=False),
        sa.Column("shiki_duration", sa.Integer(), nullable=True),
        sa.Column("shiki_rating", sa.Float(), nullable=True),
        sa.Column("shiki_ratings_count", sa.Integer(), nullable=False),
        sa.Column("shiki_planned", sa.Integer(), nullable=False),
        sa.Column("shiki_completed", sa.Integer(), nullable=False),
        sa.Column("shiki_watching", sa.Integer(), nullable=False),
        sa.Column("shiki_dropped", sa.Integer(), nullable=False),
        sa.Column("shiki_on_hold", sa.Integer(), nullable=False),
        sa.Column("shiki_age_rating", sa.String(), nullable=True),
        sa.Column("shiki_aired_on", sa.String(), nullable=True),
        sa.Column("shiki_released_on", sa.String(), nullable=True),
        sa.Column("shiki_videos", postgresql.ARRAY(sa.String(), dimensions=2, zero_indexes=True), nullable=False),
        sa.Column("shiki_synonyms", postgresql.ARRAY(sa.String(), dimensions=1, zero_indexes=True), nullable=False),
        sa.Column("shiki_genres", postgresql.ARRAY(sa.String(), dimensions=1, zero_indexes=True), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("mal_id"),
    )
    op.create_index(op.f("ix_anime_anidb_id"), "anime", ["anidb_id"], unique=True)
    op.create_table(
        "aod_anime",
        sa.Column("mal_id", sa.Integer(), nullable=False),
        sa.Column("anidb_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("poster_url", sa.String(), nullable=False),
        sa.Column("poster_thumb_url", sa.String(), nullable=False),
        sa.Column("episodes", sa.Integer(), nullable=False),
        sa.Column("duration", sa.Integer(), nullable=True),
        sa.Column("release_year", sa.Integer(), nullable=True),
        sa.Column(
            "release_season",
            sa.Enum("WINTER", "SPRING", "SUMMER", "FALL", "UNDEFINED", name="releaseseason"),
            nullable=False,
        ),
        sa.Column("status", sa.Enum("FINISHED", "ONGOING", "UPCOMING", "UNKNOWN", name="status"), nullable=False),
        sa.Column(
            "anime_type", sa.Enum("TV", "OVA", "ONA", "SPECIAL", "MOVIE", "UNKNOWN", name="animetype"), nullable=False
        ),
        sa.Column("sources", postgresql.ARRAY(sa.String(), dimensions=1, zero_indexes=True), nullable=False),
        sa.Column("tags", postgresql.ARRAY(sa.String(), dimensions=1, zero_indexes=True), nullable=False),
        sa.Column("synonyms", postgresql.ARRAY(sa.String(), dimensions=1, zero_indexes=True), nullable=False),
        sa.Column("related_animes", postgresql.ARRAY(sa.String(), dimensions=1, zero_indexes=True), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("mal_id"),
    )
    op.create_index(op.f("ix_aod_anime_anidb_id"), "aod_anime", ["anidb_id"], unique=True)
    op.create_table(
        "qitem",
        sa.Column("anime_id", sa.Integer(), nullable=False),
        sa.Column("category", sa.Enum("Opening", "Ending", name="category"), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("song_artist", sa.String(), nullable=False),
        sa.Column("song_name", sa.String(), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["anime_id"],
            ["anime.mal_id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("anime_id", "category", "number", name="_category_number_uc"),
    )
    op.create_table(
        "qitem_difficulty",
        sa.Column("qitem_id", sa.Integer(), nullable=False),
        sa.Column("value", sa.Integer(), nullable=False),
        sa.Column("added_by", sa.String(), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("value >= 0 AND value <= 100", name="_value_range"),
        sa.ForeignKeyConstraint(
            ["qitem_id"],
            ["qitem.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "qitem_source",
        sa.Column("qitem_id", sa.Integer(), nullable=False),
        sa.Column("platform", sa.String(), nullable=False),
        sa.Column("path", sa.String(), nullable=False),
        sa.Column("additional_path", sa.String(), nullable=True),
        sa.Column("added_by", sa.String(), nullable=False),
        sa.Column("local_fp", sa.String(), nullable=True),
        sa.Column("downloading", sa.Boolean(), nullable=False),
        sa.Column("invalid", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["qitem_id"],
            ["qitem.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "qitem_source_timing",
        sa.Column("qitem_source_id", sa.Integer(), nullable=False),
        sa.Column("guess_start", sa.Time(), nullable=False),
        sa.Column("reveal_start", sa.Time(), nullable=False),
        sa.Column("added_by", sa.String(), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["qitem_source_id"],
            ["qitem_source.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "quiz_part",
        sa.Column("timing_id", sa.Integer(), nullable=False),
        sa.Column("difficulty_id", sa.Integer(), nullable=False),
        sa.Column("style", sa.String(), nullable=False),
        sa.Column("local_fp", sa.String(), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["difficulty_id"],
            ["qitem_difficulty.id"],
        ),
        sa.ForeignKeyConstraint(
            ["timing_id"],
            ["qitem_source_timing.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("quiz_part")
    op.drop_table("qitem_source_timing")
    op.drop_table("qitem_source")
    op.drop_table("qitem_difficulty")
    op.drop_table("qitem")
    op.drop_index(op.f("ix_aod_anime_anidb_id"), table_name="aod_anime")
    op.drop_table("aod_anime")
    op.drop_index(op.f("ix_anime_anidb_id"), table_name="anime")
    op.drop_table("anime")
    op.execute("DROP TYPE IF EXISTS category")
    op.execute("DROP TYPE IF EXISTS releaseseason")
    op.execute("DROP TYPE IF EXISTS status")
    op.execute("DROP TYPE IF EXISTS animetype")
