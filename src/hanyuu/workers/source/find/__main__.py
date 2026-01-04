import argparse
import asyncio
import logging
import time
import random
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import aliased

from hanyuu.config import getenv
from hanyuu.database.main.connection import get_engine
from hanyuu.database.main.models import QItem, QItemSource
from hanyuu.workers.utils import FiledList, worker_log_config, delayed

from .strategies import SourceFindStrategy, strategies

logger = logging.getLogger(__name__)
worker_dir = Path(getenv("resources_dir")) / "workers" / "source" / "find"


async def job(strategy: SourceFindStrategy, wait: float, max_no_fetch: float) -> None:
    engine = await get_engine()
    async with engine.async_session() as session:
        # soures, added by this strategy
        sources = aliased(QItemSource, select(QItemSource).where(QItemSource.added_by == strategy.name).subquery())

        # qitems without any sources by this strategy
        ids_without = (
            await session.scalars(select(QItem.id).outerjoin(sources, QItem.sources).where(sources.id.is_(None)))
        ).all()

    starting_time = time.time()

    processed_fp = worker_dir / f"processed_{strategy.name}.txt"
    for _ in (True,):
        async with FiledList(str(processed_fp)) as processed_ids:
            # qitems without any sources by this or better strategies, and not processed by this strategy
            ids_to_process = list(set(ids_without) - set(processed_ids))
            if len(ids_to_process) == 0:
                break

            random.shuffle(ids_to_process)
            for id_ in ids_to_process:
                logger.info(f'Running strategy "{strategy.name}" on qitem_id={id_}')
                await strategy.run(id_)
                processed_ids.append(id_)
                if time.time() - starting_time >= max_no_fetch:
                    return
            return
    await asyncio.sleep(wait)


async def run_loop(strategy: SourceFindStrategy, max_no_fetch: float, wait: float) -> None:
    logger.info(f"Starting strategy {strategy.name}")
    while True:
        await job(strategy, wait, max_no_fetch)


async def main(max_no_fetch: float, wait: float, delay: float) -> None:
    await asyncio.gather(*[delayed(delay, run_loop, strategy, max_no_fetch, wait) for strategy in strategies])


if __name__ == "__main__":
    worker_log_config(str((worker_dir / ".log").resolve()))
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--max-no-fetch", type=float, default=20, help="maximum time without db fetches")
    parser.add_argument("-w", "--wait", type=float, default=10, help="waiting time, if no jobs were found")
    parser.add_argument("-d", "--delay", type=float, default=0.5, help="delay between workers starting times")
    args = parser.parse_args()
    asyncio.run(main(args.max_no_fetch, args.wait, args.delay))
