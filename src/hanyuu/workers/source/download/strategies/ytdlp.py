import logging
from pathlib import Path

import yt_dlp

from hanyuu.config import getenv
from hanyuu.database.main.connection import get_engine
from hanyuu.database.main.models import QItemSource

from .base import InvalidSource, SourceDownloadStrategy, TemporaryFailure

logger = logging.getLogger(__name__)


class YtDlpStrategy(SourceDownloadStrategy):
    async def run(self, qitem_source: QItemSource) -> None:
        download_dir = Path(getenv("resources_dir")) / "videos" / "sources" / self.name
        engine = await get_engine(True)
        async with engine.async_session() as session:
            session.add(qitem_source)
            qitem_source.downloading = True
            await session.commit()

        yt_dlp_error_code = None

        try:
            params = {
                "logger": logger,
                "outtmpl": f"{download_dir}/{qitem_source.id}.%(ext)s",
                "format": "bv*[height=720]+ba/b[height=720]/"
                "bv*[height>720][height<=1080]+ba/b[height>720][height<=1080]/bv*+ba/b",
            }

            # set cookies from browser option for age restricted videos
            if getenv("ytdlp_cookiesfrombrowser") is not None:
                params["cookiesfrombrowser"] = (getenv("ytdlp_cookiesfrombrowser"),)

            with yt_dlp.YoutubeDL(params=params) as ydl:
                yt_dlp_error_code = ydl.download(qitem_source.path)
        except yt_dlp.utils.DownloadError as e:
            if "Failed to extract any player response" in e.msg:
                # probably internet connection error
                exc_type = TemporaryFailure
            elif "Sign in to confirm your age" in e.msg:
                # need to pass cookies, because video is age restriced
                exc_type = TemporaryFailure
            elif "https://github.com/yt-dlp/yt-dlp/issues/7271" in e.msg:
                # failed to extract cookies from browser, use firefox
                exc_type = TemporaryFailure
            else:
                # probably video is unavailable or invalid url
                exc_type = InvalidSource
            raise exc_type("yt-dlp failed with exception: " + e.msg)
        finally:
            # set downloading = False
            engine = await get_engine(True)
            async with engine.async_session() as session:
                session.add(qitem_source)
                await session.refresh(qitem_source)
                qitem_source.downloading = False
                if yt_dlp_error_code == 0:
                    # download was successful, find downloaded video file
                    local_fp = next(download_dir.glob(f"{qitem_source.id}.*"), None)
                    if local_fp is not None:
                        qitem_source.local_fp = str(local_fp)
                await session.commit()

        if yt_dlp_error_code != 0:
            raise TemporaryFailure(f"yt-dlp terminated with non-zero error_code={yt_dlp_error_code}")
