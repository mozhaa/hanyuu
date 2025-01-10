from typing import Dict

from .base import SourceDownloadStrategy, InvalidSource, TemporaryFailure
from .local import LocalFileStrategy
from .torrent import TorrentDownloadingStrategy
from .ytdlp import YtDlpStrategy

strategies: Dict[str, SourceDownloadStrategy] = {
    "local": LocalFileStrategy("strategy_local"),
    "torrent": TorrentDownloadingStrategy("strategy_torrent"),
    "yt-dlp": YtDlpStrategy("strategy_ytdlp"),
}
