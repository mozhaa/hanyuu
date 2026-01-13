import asyncio
import logging

import yt_dlp
from yt_dlp.utils import DownloadError, UnsupportedError

from hanyuu.config import getenv
from hanyuu.database.main.connection import get_engine
from hanyuu.database.main.models import QItemSource

from .base import InvalidSource, SourceDownloadStrategy, TemporaryFailure

logger = logging.getLogger(__name__)

_yt_dlp_logger = logging.getLogger("yt_dlp")
_yt_dlp_logger.setLevel(logging.INFO)


class YtDlpStrategy(SourceDownloadStrategy):
    async def run(self, qitem_source: QItemSource) -> None:
        download_dir = getenv("resources_dir") / "videos" / "sources" / self.name
        download_dir.parent.mkdir(parents=True, exist_ok=True)
        yt_dlp_error_code = None

        params = {
            "logger": _yt_dlp_logger,
            "outtmpl": f"{download_dir}/{qitem_source.id}.%(ext)s",
            "format": "bv*[height=720]+ba/b[height=720]/"
            "bv*[height>720][height<=1080]+ba/b[height>720][height<=1080]/bv*+ba/b",
            "abort_on_unavailable_fragments": True,
            "retries": 5,
            "fragment_retries": 5,
        }

        # set cookies from browser option for age restricted videos
        if getenv("ytdlp_cookiesfrombrowser") is not None:
            params["cookiesfrombrowser"] = (getenv("ytdlp_cookiesfrombrowser"),)

        try:
            with yt_dlp.YoutubeDL(params=params) as ydl:
                yt_dlp_error_code = await asyncio.to_thread(ydl.download, [qitem_source.path])
        except DownloadError as e:
            self._handle_download_error(e)
        except Exception as e:
            # other unexpected errors (e.g. file system permissions)
            raise TemporaryFailure(f"Unexpected error during yt-dlp execution: {e}") from e

        if yt_dlp_error_code == 0:
            local_fp = next(download_dir.glob(f"{qitem_source.id}.*"), None)
            if local_fp is not None:
                async with get_engine().async_session() as session:
                    session.add(qitem_source)
                    await session.refresh(qitem_source)
                    qitem_source.local_fp = str(local_fp)
                    await session.commit()
            else:
                logger.warning(f"yt-dlp returned 0, but video was not found ({qitem_source.id=})")
                raise TemporaryFailure(f"yt-dlp success but file missing for {qitem_source.id}")
        else:
            raise TemporaryFailure(f"yt-dlp terminated with non-zero error_code={yt_dlp_error_code}")

    def _handle_download_error(self, e: DownloadError) -> None:
        msg = str(e)

        if e.exc_info:
            orig_exc_type = e.exc_info[0]
            if issubclass(orig_exc_type, UnsupportedError):
                raise InvalidSource(f"URL is unsupported: {msg}") from e

        invalid_source_patterns = [
            "Private video",
            "Video unavailable",
            "This video has been removed",
            "account associated with this video has been terminated",
            "uploader has closed their YouTube account",
            "This video is available to this channel's members",
            "copyright grounds",
            "Incomplete YouTube ID",
            "Unsupported URL",
        ]

        for pattern in invalid_source_patterns:
            if pattern.lower() in msg.lower():
                raise InvalidSource(f"Permanent error detected: {msg}") from e

        temporary_failure_patterns = [
            "HTTP Error 429",  # rate limiting
            "HTTP Error 5",  # 500, 502, 503, 504 server errors
            "The read operation timed out",
            "Connection refused",
            "Network is unreachable",
            "timed out",
            "host could not be resolved",
            "Sign in to confirm your age",
            "Failed to extract any player response",
            "cookies database",
            "unable to download video data",
            "not available in your country",
            "This video is available to this channel's members",
        ]

        for pattern in temporary_failure_patterns:
            if pattern.lower() in msg.lower():
                raise TemporaryFailure(f"Temporary error detected: {msg}") from e

        raise TemporaryFailure(f"Unknown yt-dlp error (assuming temporary): {msg}") from e
