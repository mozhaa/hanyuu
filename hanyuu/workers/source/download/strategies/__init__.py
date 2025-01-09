from typing import List

from .base import SourceDownloadStrategy
from .local import LocalFileStrategy
from .torrent import TorrentDownloadingStrategy
from .ytdlp import YtDlpStrategy

strategies: List[SourceDownloadStrategy] = [
    LocalFileStrategy("strategy_local"),
    TorrentDownloadingStrategy("strategy_torrent"),
    # YtDlpStrategy("strategy_ytdlp"),
]
