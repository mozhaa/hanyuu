import argparse
import asyncio
import logging
from pathlib import Path

from sqlalchemy import Integer, func, select, update
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import aliased

from hanyuu.config import getenv
from hanyuu.database.main.connection import get_engine
from hanyuu.database.main.models import QItem, QItemSource
from hanyuu.workers.source.find.strategies import strategies as finding_strategies
from hanyuu.workers.utils import restrict_callrate, worker_log_config

from .strategies import strategies as downloading_strategies

logger = logging.getLogger(__name__)
worker_dir = Path(getenv("resources_dir")) / "workers" / "source" / "download"
root_dir = Path(getenv("resources_dir")) / "videos" / "sources"


async def run_job(k: bool) -> None:
    """
    For each QItem we find best not downloaded source
    (in order of source finding strategies priorities) and download it
    """

    engine = await get_engine()
    ids_to_skip = set()
    better_strategies = set()
    ordered_finding_strategies = ["manual"] + [s.name for s in finding_strategies]
    for strategy_name in ordered_finding_strategies:
        better_strategies.add(strategy_name)
        async with engine.async_session() as session:
            downloaded_sources = aliased(
                QItemSource,
                select(QItemSource)
                .where(QItemSource.added_by == strategy_name)
                .where(QItemSource.local_fp.isnot(None))
                .subquery(),
            )
            sources_to_download = aliased(
                QItemSource,
                select(QItemSource)
                .where(QItemSource.added_by == strategy_name)
                .where(QItemSource.local_fp.is_(None))
                .subquery(),
            )

            p1 = dict(
                (
                    await session.execute(
                        select(QItem.id, func.array_agg(sources_to_download.id, type_=ARRAY(Integer)))
                        .join(sources_to_download)
                        .group_by(QItem.id)
                    )
                ).all()
            )

            p2 = dict(
                (
                    await session.execute(
                        select(QItem.id, func.array_agg(downloaded_sources.id, type_=ARRAY(Integer)))
                        .join(downloaded_sources)
                        .group_by(QItem.id)
                    )
                ).all()
            )

            potential_qitem_ids = set(p1.keys())
            done_qitem_ids = set(p2.keys())
            qitem_ids_to_download = potential_qitem_ids - ids_to_skip
            ids_to_skip |= done_qitem_ids

            if len(qitem_ids_to_download) > 0:
                qitem_id = min(qitem_ids_to_download)
                source_id = p1[qitem_id][0]

                for downloading_strategy in downloading_strategies:
                    download_dir = root_dir / downloading_strategy.name
                    suitable, run = await downloading_strategy.check(source_id, str(download_dir.resolve()))
                    if suitable:
                        logger.info(f'Running strategy "{downloading_strategy.name}" on source_id={source_id}')
                        await run()
                        if not k:
                            logger.info(f"Clearing sources for qitem_id={qitem_id}, worse than {strategy_name}")
                            await session.execute(
                                update(QItemSource)
                                .where(QItemSource.qitem_id == qitem_id)
                                .where(QItemSource.added_by.not_in(better_strategies))
                                .values(local_fp=None)
                            )
                        return


async def main(interval: float, k: bool) -> None:
    rate_limited_run_job = restrict_callrate(interval)(run_job)
    while True:
        await rate_limited_run_job(k)


if __name__ == "__main__":
    worker_log_config(str((worker_dir / ".log").resolve()))
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", type=float, default=5, help="interval in seconds between job starts")
    parser.add_argument("-k", action="store_true", help="keep downloaded sources, even if better source is downloaded")
    args = parser.parse_args()
    asyncio.run(main(args.t, args.k))
