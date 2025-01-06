import logging
import argparse
import asyncio
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import aliased

from hanyuu.config import getenv
from hanyuu.database.main.connection import get_engine
from hanyuu.database.main.models import QItem, QItemSource
from hanyuu.workers.utils import FiledList, restrict_callrate, worker_log_config

from .strategies import strategies

logger = logging.getLogger(__name__)
worker_dir = Path(getenv("resources_dir")) / "workers" / "source" / "find"


async def run_job() -> None:
    engine = await get_engine()
    ids1 = None
    for strategy in strategies:
        async with engine.async_session() as session:
            # soures, added by this strategy
            sources = aliased(QItemSource, select(QItemSource).where(QItemSource.added_by == strategy.name).subquery())

            # qitems without any sources by this strategy
            ids2 = (
                await session.scalars(select(QItem.id).outerjoin(sources, QItem.sources).where(sources.id.is_(None)))
            ).all()

        # qitems without any sources by this or better strategies
        ids1 = set(ids2) if ids1 is None else ids1 & set(ids2)

        processed_fp = worker_dir / f"processed_{strategy.name}.txt"
        async with FiledList(str(processed_fp)) as processed:
            processed_ids = set(processed)

            # qitems without any sources by this or better strategies, and not processed by this strategy
            ids3 = ids1 - processed_ids

            if len(ids3) > 0:
                id_ = min(ids3)
                logger.info(f'Running strategy "{strategy.name}" on qitem_id={id_}')
                await strategy.run(id_)
                processed.append(id_)
                return

    logger.debug("No jobs were found")


async def main(interval: float) -> None:
    rate_limited_run_job = restrict_callrate(interval)(run_job)
    while True:
        await rate_limited_run_job()


if __name__ == "__main__":
    worker_log_config(str((worker_dir / ".log").resolve()))
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", type=float, default=5, help="interval in seconds between job starts")
    args = parser.parse_args()
    asyncio.run(main(args.t))
