import argparse
import asyncio
from pathlib import Path
from typing import Optional, Tuple

from sqlalchemy import select

from hanyuu.config import getenv
from hanyuu.database.main.connection import get_engine
from hanyuu.database.main.models import QItem, QItemSource
from hanyuu.workers.utils import FiledList

from .strategies import SourceFindingStrategy, strategies


async def select_job() -> Optional[Tuple[int, SourceFindingStrategy]]:
    global worker_dir

    async def select_strategy(qitem_id: int) -> Optional[SourceFindingStrategy]:
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
                return qitem_id, strategy

    engine = await get_engine()
    async with engine.async_session() as session:
        qitem_ids = (
            await session.scalars(select(QItem.id).outerjoin(QItem.sources).where(QItemSource.id.is_(None)))
        ).all()

    for qitem_id in qitem_ids:
        strategy = await select_strategy(qitem_id)
        if strategy is not None:
            return qitem_id, strategy


async def start(interval: int) -> None:
    global worker_dir
    worker_dir = Path(f"{getenv("resources_dir")}/workers/source_finder")
    while True:
        print("Iteration")
        result = await select_job()
        if result is not None:
            qitem_id, strategy = result
            print(f"Selected {qitem_id}, {strategy.name}")
            # source = await strategy.find_source(qitem_id)
            # source.added_by = strategy.name
            # print(f"Found source: {source}")
        print("Selected nothing")
        await asyncio.sleep(interval)


async def main() -> None:
    parser = argparse.ArgumentParser(
        "Source Finding Worker",
        "Find sources for QItems from database, using some strategy",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=10,
        help="interval time between strategy runs in seconds",
    )
    args = parser.parse_args()
    await start(args.interval)


if __name__ == "__main__":
    asyncio.run(main())
