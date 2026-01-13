import argparse
import asyncio
import logging

from sqlalchemy import select

from hanyuu.config import getenv
from hanyuu.database.main.connection import get_engine
from hanyuu.database.main.models import QItemSource, QItemSourceTiming
from hanyuu.workers.utils import restrict_callrate, worker_log_config

from .strategies import strategies

logger = logging.getLogger(__name__)


async def run_job() -> None:
    """
    Every source will get timings by all possible strategies, in order of strategies priority
    """

    engine = get_engine()
    for strategy in strategies:
        async with engine.async_session() as session:
            # sources without timings by this strategy
            source_ids = (
                await session.scalars(
                    select(QItemSource.id)
                    .outerjoin(QItemSource.timings.and_(QItemSourceTiming.added_by == strategy.name))
                    .where(QItemSourceTiming.id.is_(None))
                )
            ).all()

        if len(source_ids) > 0:
            source_id = source_ids[0]
            logger.info(f'Running strategy "{strategy.name}" on source_id={source_id}')
            await strategy.run(source_id)
            return


async def main(interval: float) -> None:
    rate_limited_run_job = restrict_callrate(interval)(run_job)
    while True:
        await rate_limited_run_job()


if __name__ == "__main__":
    worker_log_config(str(getenv("logs_dir") / "worker" / "timing.log"))
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", type=float, default=0, help="interval in seconds between job starts")
    args = parser.parse_args()
    asyncio.run(main(args.t))
