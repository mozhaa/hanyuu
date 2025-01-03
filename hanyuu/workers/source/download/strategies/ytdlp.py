import logging
from pathlib import Path
from typing import Awaitable, Callable, Optional, Tuple

import yt_dlp

from hanyuu.database.main.connection import get_engine
from hanyuu.database.main.models import QItemSource

from .base import SourceDownloadStrategy

logger = logging.getLogger(__name__)


class YtDlpStrategy(SourceDownloadStrategy):
    async def check(
        self, qitem_source_id: int, download_dir: str
    ) -> Tuple[bool, Optional[Callable[[], Awaitable[None]]]]:
        engine = await get_engine(True)
        async with engine.async_session() as session:
            qitem_source = await session.get(QItemSource, qitem_source_id)
            session.expunge(qitem_source)

        if qitem_source.platform not in ["youtube", "yt-dlp"]:
            return False, None

        async def run() -> None:
            params = {
                "outtmpl": f"{download_dir}/{qitem_source_id}.%(ext)s",
                "format": "bv*[height=720]+ba/b[height=720]/"
                "bv*[height>720][height<=1080]+ba/b[height>720][height<=1080]/bv*+ba/b",
            }

            with yt_dlp.YoutubeDL(params=params) as ydl:
                ret_code = ydl.download(qitem_source.path)

            if ret_code == 0:
                local_fp = str(next(Path(download_dir).glob(f"{qitem_source_id}.*")).resolve())
                logger.info(f"Download successed, filepath = {local_fp}")
                async with engine.async_session() as session:
                    session.add(qitem_source)
                    qitem_source.local_fp = local_fp
                    await session.commit()
            else:
                logger.warning(f"Download failed, return code = {ret_code}")

        return True, run
