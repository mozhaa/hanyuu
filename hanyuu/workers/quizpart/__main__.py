import logging
from pathlib import Path
from typing import Awaitable, Optional

from sqlalchemy import select, and_
from sqlalchemy.orm import aliased

from hanyuu.config import getenv
from hanyuu.database.main.connection import get_engine
from hanyuu.database.main.models import (
    QItem,
    QItemDifficulty,
    QItemSource,
    QItemSourceTiming,
    QuizPart,
)
from hanyuu.video import VideoMaker
from hanyuu.workers.utils import StrategyRunner

difficulty_strategies = ["manual", "strategy_random"]
timing_strategies = ["manual", "strategy_default"]
countdowns_dir = Path(getenv("static_dir")) / "video" / "countdowns"
root_dir = Path(getenv("resources_dir")) / "videos" / "quizparts"


def difficulty_func(value: int) -> str:
    return ["very easy.mkv", "easy.mkv", "medium.mkv", "hard.mkv", "very hard.mkv"][min(value // 20, 4)]


logger = logging.getLogger(__name__)


async def run_videomaker(timing_id: int, difficulty_id: int) -> None:
    engine = await get_engine()
    async with engine.async_session() as session:
        quiz_part = QuizPart(timing_id=timing_id, difficulty_id=difficulty_id, style="classic", local_fp="")
        session.add(quiz_part)
        await session.flush()
        await session.refresh(quiz_part)
        output_fp = root_dir / f"{quiz_part.id}.mkv"
        quiz_part.local_fp = str(output_fp.resolve())
        try:
            logger.debug("Running video making...")
            await VideoMaker(
                countdowns_dir=str(countdowns_dir.resolve()), difficulty_func=difficulty_func
            ).create_video(timing_id, difficulty_id, str(output_fp.resolve()))
            logger.info(f"Created quiz part on {output_fp}")
        except Exception as e:
            logger.warning("Video making failed!")
            await session.delete(quiz_part)
            raise e
        finally:
            await session.commit()


async def select_job() -> Optional[Awaitable[None]]:
    engine = await get_engine()
    async with engine.async_session() as session:
        possible_timings = aliased(
            QItemSourceTiming,
            select(QItemSourceTiming)
            .join(QItemSourceTiming.qitem_source)
            .where(QItemSourceTiming.added_by.in_(timing_strategies))
            .where(QItemSource.local_fp.isnot(None))
            .subquery(),
        )

        possible_difficulties = aliased(
            QItemDifficulty,
            select(QItemDifficulty).where(QItemDifficulty.added_by.in_(difficulty_strategies)).subquery(),
        )

        result = (
            await session.execute(
                select(QItem.id, possible_difficulties.id, possible_timings.id)
                .join(possible_difficulties, QItem.difficulties)
                .join(QItem.sources)
                .join(possible_timings, QItemSource.timings)
                .outerjoin(
                    QuizPart,
                    and_(QuizPart.difficulty_id == possible_difficulties.id, QuizPart.timing_id == possible_timings.id),
                )
                .where(QuizPart.id.is_(None))
            )
        ).first()

    if result is not None:
        qitem_id, difficulty_id, timing_id = result
        logger.info(f"Running on qitem_id={qitem_id}, difficulty_id={difficulty_id}, timing_id={timing_id}")
        return run_videomaker(timing_id, difficulty_id)

    logger.debug("No jobs were found")


if __name__ == "__main__":
    logging.basicConfig(level=logging.NOTSET)
    StrategyRunner(select_job, False).start()
