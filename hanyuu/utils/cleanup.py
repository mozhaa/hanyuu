import asyncio
import logging
from pathlib import Path
from typing import List, Tuple, Type

from sqlalchemy import select

from hanyuu.config import getenv
from hanyuu.database.main.connection import get_engine
from hanyuu.database.main.models import *

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


async def cleanup() -> None:
    engine = await get_engine()
    async with engine.async_session() as session:
        quizpart_files = (await session.execute(select(QuizPart.id, QuizPart.local_fp))).all()
        source_files = (
            await session.execute(select(QItemSource.id, QItemSource.local_fp).where(QItemSource.local_fp.isnot(None)))
        ).all()

    videos_dir = Path(getenv("resources_dir")) / "videos"
    await delete_invalid_records(source_files, QItemSource)
    delete_unused_files(videos_dir / "sources", [x[1] for x in source_files])
    await delete_invalid_records(quizpart_files, QuizPart)
    delete_unused_files(videos_dir / "quizparts", [x[1] for x in quizpart_files])


if __name__ == "__main__":
    logging.basicConfig(level=logging.NOTSET)
    asyncio.run(cleanup())
