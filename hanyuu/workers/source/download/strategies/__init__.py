from .base import SourceDownloadStrategy
from .ytdlp import YtDlpStrategy
from .torrent import TorrentDownloadingStrategy
from typing import List

strategies: List[SourceDownloadStrategy] = [
    TorrentDownloadingStrategy("strategy_torrent"),
    YtDlpStrategy("strategy_ytdlp"),
]
