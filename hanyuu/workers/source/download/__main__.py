import argparse
import asyncio
import logging
import time
from pathlib import Path

from sqlalchemy import case, label, literal_column, select
from sqlalchemy.orm import aliased

from hanyuu.config import getenv
from hanyuu.database.main.connection import get_engine
from hanyuu.database.main.models import QItemSource
from hanyuu.workers.source.find.strategies import strategies as finding_strategies
from hanyuu.workers.utils import worker_log_config

from .strategies import InvalidSource, SourceDownloadStrategy, TemporaryFailure
from .strategies import strategies as downloading_strategies

logger = logging.getLogger(__name__)
worker_dir = Path(getenv("resources_dir")) / "workers" / "source" / "download"


async def run_loop(platform: str, strategy: SourceDownloadStrategy, wait_duration: float, ban_duration: float) -> None:
    engine = await get_engine()
    f_strategies = ["manual"] + [s.name for s in finding_strategies]
    temporary_failed_sources = dict()
    while True:
        # update list of temporary failed sources
        for source_id, failed_on in temporary_failed_sources.items():
            if time.time() - failed_on >= ban_duration:
                temporary_failed_sources.pop(source_id)

        async with engine.async_session() as session:
            best_sources = aliased(
                QItemSource,
                select(
                    QItemSource,
                    label(
                        "prio",
                        case(
                            *[(QItemSource.added_by == sname, i) for i, sname in enumerate(f_strategies)],
                            else_=len(f_strategies),
                        ),
                    ),
                )
                .distinct(QItemSource.qitem_id)
                .where(QItemSource.invalid.is_(False))
                .order_by(
                    QItemSource.qitem_id,
                    literal_column("prio"),
                    QItemSource.updated_at.desc(),
                )
                .subquery(),
            )

            sources = (
                await session.scalars(
                    select(best_sources)
                    .where(best_sources.local_fp.is_(None))
                    .where(best_sources.downloading.is_(False))
                    .where(best_sources.id.not_in(temporary_failed_sources.keys()))
                    .where(best_sources.platform == platform)
                )
            ).all()

        if len(sources) == 0:
            await asyncio.sleep(wait_duration)
            continue

        for source in sources:
            try:
                logger.info(f"Running strategy {strategy.name} on {source}")
                await strategy.run(source)
                logger.info(f"Strategy {strategy.name} ended with success (source_id={source.id})")
            except InvalidSource as e:
                logger.warning(f"Source marked as invalid: {source}\n\tMessage: {e}")
                async with engine.async_session() as session:
                    session.add(source)
                    source.invalid = True
                    await session.commit()
            except TemporaryFailure as e:
                logger.warning(f"Temporary failure occured during strategy {strategy.name}\n\tMessage: {e}")
                temporary_failed_sources[source.id] = time.time()


async def main(wait: float, ban_duration: float, delay: float) -> None:
    async with asyncio.TaskGroup() as tg:
        for platform, strategy in downloading_strategies.items():
            tg.create_task(run_loop(platform, strategy, wait, ban_duration))
            await asyncio.sleep(delay)


if __name__ == "__main__":
    worker_log_config(str((worker_dir / ".log").resolve()))
    parser = argparse.ArgumentParser()
    parser.add_argument("-w", "--wait", type=float, default=10, help="waiting time, if no jobs were found")
    parser.add_argument(
        "-b",
        "--ban",
        type=float,
        default=120,
        help="if source in temporary failed to download, ban it for this amount of seconds",
    )
    parser.add_argument("-d", "--delay", type=float, default=1, help="delay between workers starting times")
    args = parser.parse_args()
    asyncio.run(main(args.wait, args.ban, args.delay))
