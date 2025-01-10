import asyncio
import logging
from pathlib import Path
from typing import List, Tuple, Type

from sqlalchemy import case, delete, update, label, literal_column, select
from sqlalchemy.orm import aliased

from hanyuu.config import getenv
from hanyuu.database.main.connection import get_engine
from hanyuu.database.main.models import *
from hanyuu.workers.source.find.strategies import strategies as finding_strategies

logger = logging.getLogger(__name__)


def delete_unused_files(directory: Path, used_files: List[str]) -> None:
    used_files_set = set([str(Path(fp).resolve()) for fp in used_files])
    n_removed_files = 0
    for file in directory.rglob("*"):
        if file.is_file() and str(file.resolve()) not in used_files_set:
            logger.info(f"Removing {file.resolve()}")
            n_removed_files += 1
            file.unlink()
    logger.info(f"Total files removed: {n_removed_files}")


async def delete_invalid_records(records: List[Tuple[int, str]], entity: Type[Base]) -> None:
    engine = await get_engine()
    n_deleted_records = 0
    async with engine.async_session() as session:
        for id_, fp in records:
            if not Path(fp).exists():
                n_deleted_records += 1
                obj = await session.get(entity, id_)
                logger.info(f"Deleting ({obj}) from database")
                await session.delete(obj)
        await session.commit()
    logger.info(f"Total records deleted: {n_deleted_records}")


async def delete_duplicated_quizparts() -> None:
    engine = await get_engine()
    async with engine.async_session() as session:
        keep_qparts = (
            select(
                label("d_id", QItemDifficulty.id),
                label("t_id", QItemSourceTiming.id),
                label("qp_s", QuizPart.style),
                func.count(),
                label("qp_id", func.max(QuizPart.id)),
            )
            .join(QuizPart.difficulty)
            .join(QuizPart.timing)
            .group_by(QItemDifficulty.id, QItemSourceTiming.id, QuizPart.style)
            .having(func.count() > 1)
            .subquery()
        )

        delete_qparts = (
            await session.scalars(
                select(QuizPart.id).join(
                    keep_qparts,
                    (keep_qparts.c.d_id == QuizPart.difficulty_id)
                    & (keep_qparts.c.t_id == QuizPart.timing_id)
                    & (keep_qparts.c.qp_s == QuizPart.style)
                    & (keep_qparts.c.qp_id != QuizPart.id),
                )
            )
        ).all()

        if len(delete_qparts) > 0:
            logger.info(f"Deleting quizparts as duplicates, ids={delete_qparts}")
            await session.execute(delete(QuizPart).where(QuizPart.id.in_(delete_qparts)))
            await session.commit()


async def clear_worse_sources() -> None:
    engine = await get_engine()
    f_strategies = ["manual"] + [s.name for s in finding_strategies]
    async with engine.async_session() as session:
        best_sources = aliased(
            QItemSource,
            select(
                QItemSource,
                label(
                    "prio",
                    case(
                        *[(QItemSource.added_by == sname, i) for i, sname in enumerate(f_strategies)],
                        else_=len(f_strategies),
                    ),
                ),
            )
            .distinct(QItemSource.qitem_id)
            .where(QItemSource.invalid.is_(False))
            .order_by(
                QItemSource.qitem_id,
                literal_column("prio"),
                QItemSource.updated_at.desc(),
            )
            .subquery(),
        )

        ids_to_clear = (
            await session.scalars(
                select(QItemSource.id)
                .join(best_sources, best_sources.qitem_id == QItemSource.qitem_id)
                .where(QItemSource.id != best_sources.id)
                .where(QItemSource.local_fp.isnot(None))
            )
        ).all()

        await session.execute(update(QItemSource).where(QItemSource.id.in_(ids_to_clear)).values(local_fp=None))
        await session.commit()

    logger.info(f"Cleared videos for sources with ids={ids_to_clear}")


async def cleanup() -> None:
    await delete_duplicated_quizparts()

    engine = await get_engine()
    async with engine.async_session() as session:
        quizpart_files = (await session.execute(select(QuizPart.id, QuizPart.local_fp))).all()
        source_files = (
            await session.execute(select(QItemSource.id, QItemSource.local_fp).where(QItemSource.local_fp.isnot(None)))
        ).all()

    await clear_worse_sources()

    videos_dir = Path(getenv("resources_dir")) / "videos"
    await delete_invalid_records(source_files, QItemSource)
    delete_unused_files(videos_dir / "sources", [x[1] for x in source_files])
    await delete_invalid_records(quizpart_files, QuizPart)
    delete_unused_files(videos_dir / "quizparts", [x[1] for x in quizpart_files])


if __name__ == "__main__":
    logging.basicConfig(level=logging.NOTSET)
    asyncio.run(cleanup())
