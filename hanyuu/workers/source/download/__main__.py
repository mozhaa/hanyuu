import logging
from pathlib import Path
from typing import Awaitable, Optional

from sqlalchemy import select

from hanyuu.config import getenv
from hanyuu.database.main.connection import get_engine
from hanyuu.database.main.models import QItemSource
from hanyuu.workers.utils import StrategyRunner

from .strategies import strategies

logger = logging.getLogger(__name__)


async def select_job() -> Optional[Awaitable[None]]:
    root_dir = Path(getenv("resources_dir")) / "videos" / "sources"
    engine = await get_engine()
    async with engine.async_session() as session:
        source_ids = (await session.scalars(select(QItemSource.id).where(QItemSource.local_fp.is_(None)))).all()
    for source_id in source_ids:
        for strategy in strategies:
            download_dir = root_dir / strategy.name
            suitable, run = await strategy.check(source_id, str(download_dir.resolve()))
            if suitable:
                logger.info(f'Running strategy "{strategy.name}" on source_id={source_id}')
                return run()
    logger.debug("No jobs were found")


if __name__ == "__main__":
    logging.basicConfig(level=logging.NOTSET)
    StrategyRunner(select_job, False).start()
