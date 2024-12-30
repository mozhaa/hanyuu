import logging
from pathlib import Path
from typing import Awaitable, Optional

from sqlalchemy import select

from hanyuu.config import getenv
from hanyuu.database.main.connection import get_engine
from hanyuu.database.main.models import QItem, QItemSource
from hanyuu.workers.utils import FiledList, StrategyRunner

from .strategies import SourceFindStrategy, strategies

logger = logging.getLogger(__name__)


async def select_job() -> Optional[Awaitable[None]]:
    worker_dir = Path(getenv("resources_dir")) / "workers" / "source_finding"

    async def select_strategy(qitem_id: int) -> Optional[SourceFindStrategy]:
        for strategy in strategies:
            processed_fp = worker_dir / f"processed_{strategy.name}.txt"
            async with FiledList(str(processed_fp)) as processed:
                if qitem_id not in processed:
                    processed.append(qitem_id)
                    return strategy

    queue_fp = worker_dir / "queue.txt"
    async with FiledList(str(queue_fp)) as queue:
        while len(queue) > 0:
            qitem_id = queue[0]
            queue = queue[1:]
            strategy = await select_strategy(qitem_id)
            if strategy is not None:
                logger.info(f'Running strategy "{strategy.name}" on qitem_id={qitem_id}')
                return strategy.run(qitem_id)

    engine = await get_engine()
    async with engine.async_session() as session:
        qitem_ids = (
            await session.scalars(select(QItem.id).outerjoin(QItem.sources).where(QItemSource.id.is_(None)))
        ).all()

    for qitem_id in qitem_ids:
        strategy = await select_strategy(qitem_id)
        if strategy is not None:
            logger.info(f'Running strategy "{strategy.name}" on qitem_id={qitem_id}')
            return strategy.run(qitem_id)
    logger.debug("No jobs were found")


if __name__ == "__main__":
    logging.basicConfig(level=logging.NOTSET)
    StrategyRunner(select_job, False).start()
