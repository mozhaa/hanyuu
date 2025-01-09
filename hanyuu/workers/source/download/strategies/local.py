from pathlib import Path
from typing import Awaitable, Callable, Optional, Tuple

from hanyuu.database.main.connection import get_engine
from hanyuu.database.main.models import QItemSource

from .base import InvalidSource, SourceDownloadStrategy


class LocalFileStrategy(SourceDownloadStrategy):
    async def check(
        self, qitem_source_id: int, download_dir: str
    ) -> Tuple[bool, Optional[Callable[[], Awaitable[None]]]]:
        engine = await get_engine()
        async with engine.async_session() as session:
            qitem_source = await session.get(QItemSource, qitem_source_id)

        if qitem_source.platform != "local":
            return False, None

        if qitem_source.path is None or not Path(qitem_source.path).exists():
            raise InvalidSource("Invalid path")

        async def run() -> None:
            async with engine.async_session() as session:
                qitem_source = await session.get(QItemSource, qitem_source_id)
                qitem_source.local_fp = qitem_source.path
                await session.commit()

        return True, run
