from .base import SourceDownloadStrategy
from .youtube import YtDlpStrategy
from typing import List

strategies: List[SourceDownloadStrategy] = [YtDlpStrategy("strategy_ytdlp")]