from .base import SourceDownloadStrategy
from .ytdlp import YtDlpStrategy
from typing import List

strategies: List[SourceDownloadStrategy] = [YtDlpStrategy("strategy_ytdlp")]
