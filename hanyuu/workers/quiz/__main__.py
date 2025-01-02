import argparse
import asyncio
import logging
import random
from pathlib import Path

from sqlalchemy import select

from hanyuu.config import getenv
from hanyuu.database.main.connection import get_engine
from hanyuu.database.main.models import Category, QItem, QItemDifficulty, QuizPart
from hanyuu.video.videocat import cat

logger = logging.getLogger(__name__)

root_dir = Path(getenv("resources_dir")) / "videos" / "quiz"


async def run(output_fp: str) -> None:
    engine = await get_engine()
    async with engine.async_session() as session:
        quizparts = (
            await session.scalars(
                select(QuizPart.local_fp)
                .join(QuizPart.difficulty)
                .join(QItemDifficulty.qitem)
                .where(QItem.category == Category.Opening)
            )
        ).all()

    random.shuffle(quizparts)
    root_dir.mkdir(parents=True, exist_ok=True)
    cat(quizparts, str((root_dir / output_fp).resolve()))


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-o", type=str)
    args = parser.parse_args()
    await run(args.o)


if __name__ == "__main__":
    logging.basicConfig(level=logging.NOTSET)
    asyncio.run(main())
