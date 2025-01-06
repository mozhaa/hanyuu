import argparse
import asyncio
import logging
from pathlib import Path

from sqlalchemy import select

from hanyuu.config import getenv
from hanyuu.database.main.connection import get_engine
from hanyuu.database.main.models import QItem, QItemDifficulty
from hanyuu.workers.utils import restrict_callrate, worker_log_config

from .strategies import strategies

logger = logging.getLogger(__name__)
worker_dir = Path(getenv("resources_dir")) / "workers" / "difficulty"


async def run_job() -> None:
    """
    Every qitem will get difficulties by all possible strategies, in order of strategies priority
    """

    engine = await get_engine()
    for strategy in strategies:
        async with engine.async_session() as session:
            # qitems without difficulty by this strategy
            qitem_ids = (
                await session.scalars(
                    select(QItem.id)
                    .outerjoin(QItem.difficulties.and_(QItemDifficulty.added_by == strategy.name))
                    .where(QItemDifficulty.id.is_(None))
                )
            ).all()

        if len(qitem_ids) > 0:
            logger.info(f'Running strategy "{strategy.name}" on qitem_id={qitem_ids[0]}')
            await strategy.run(qitem_ids[0])
            return


async def main(interval: float) -> None:
    rate_limited_run_job = restrict_callrate(interval)(run_job)
    while True:
        await rate_limited_run_job()


if __name__ == "__main__":
    worker_log_config(str((worker_dir / ".log").resolve()))
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", type=float, default=1, help="interval in seconds between job starts")
    args = parser.parse_args()
    asyncio.run(main(args.t))
