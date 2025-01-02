import logging
import random
from typing import Awaitable, Optional

from sqlalchemy import select
from sqlalchemy.orm import aliased

from hanyuu.database.main.connection import get_engine
from hanyuu.database.main.models import QItemSource, QItemSourceTiming
from hanyuu.workers.utils import StrategyRunner

from .strategies import strategies

logger = logging.getLogger(__name__)


async def select_job() -> Optional[Awaitable[None]]:
    engine = await get_engine()
    for strategy in random.sample(strategies, len(strategies)):
        async with engine.async_session() as session:
            timings_by_s = aliased(
                QItemSourceTiming,
                select(QItemSourceTiming).where(QItemSourceTiming.added_by == strategy.name).subquery(),
            )

            sources_without_s = (
                await session.scalars(
                    select(QItemSource.id).outerjoin(timings_by_s, QItemSource.timings).where(timings_by_s.id.is_(None))
                )
            ).all()

        if len(sources_without_s) > 0:
            source_id = sources_without_s[0]
            logger.info(f'Running strategy "{strategy.name}" on source_id={source_id}')
            return strategy.run(source_id)

    logger.debug("No jobs were found")


if __name__ == "__main__":
    logging.basicConfig(level=logging.NOTSET)
    StrategyRunner(select_job, False).start()
