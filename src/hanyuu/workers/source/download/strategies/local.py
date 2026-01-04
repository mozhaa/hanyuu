from pathlib import Path
import ffmpeg

from hanyuu.database.main.connection import get_engine
from hanyuu.database.main.models import QItemSource
from hanyuu.workers.utils import try_make_path_relative

from .base import InvalidSource, SourceDownloadStrategy


class LocalFileStrategy(SourceDownloadStrategy):
    async def run(self, qitem_source: QItemSource) -> None:
        if qitem_source.path is None:
            raise InvalidSource("Path can't be NULL")
        if not Path(qitem_source.path).exists():
            raise InvalidSource(f'File "{qitem_source.path}" does not exist')
        if not is_video_with_audio(qitem_source.path):
            raise InvalidSource(f'File "{qitem_source.path}" is not a video or video without audio')

        engine = await get_engine()
        async with engine.async_session() as session:
            session.add(qitem_source)
            qitem_source.local_fp = str(try_make_path_relative(qitem_source.path))
            await session.commit()


def is_video_with_audio(path: str) -> bool:
    try:
        probe_result = ffmpeg.probe(path, show_entries="stream=codec_type")
        next(filter(lambda s: s["codec_type"] == "video", probe_result["streams"]))
        next(filter(lambda s: s["codec_type"] == "audio", probe_result["streams"]))
        return True
    except (KeyError, StopIteration, ffmpeg.Error):
        return False
