import logging
import random
from typing import Awaitable, Optional

from sqlalchemy import select

from hanyuu.database.main.connection import get_engine
from hanyuu.database.main.models import QItem, QItemDifficulty
from hanyuu.workers.utils import StrategyRunner

from .strategies import strategies

logger = logging.getLogger(__name__)


async def select_job() -> Optional[Awaitable[None]]:
    for strategy in random.sample(strategies, len(strategies)):
        engine = await get_engine()
        async with engine.async_session() as session:
            qitem_ids = (
                await session.scalars(
                    select(QItem.id).outerjoin(QItem.difficulties).where(QItemDifficulty.id.is_(None))
                )
            ).all()
            if len(qitem_ids) > 0:
                logger.info(f'Running strategy "{strategy.name}" on qitem_id={qitem_ids[0]}')
                return strategy.run(qitem_ids[0])
    logger.debug("No jobs were found")


if __name__ == "__main__":
    logging.basicConfig(level=logging.NOTSET)
    StrategyRunner(select_job, False).start()
