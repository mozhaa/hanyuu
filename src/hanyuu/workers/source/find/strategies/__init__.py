from typing import List

from .anitousen import AniTousenTorrentStrategy
from .base import SourceFindStrategy
from .shiki import ShikiAttachmentsStrategy
from .youtube import YoutubeFindStrategy

strategies: List[SourceFindStrategy] = [
    AniTousenTorrentStrategy("strategy_anitousen"),
    ShikiAttachmentsStrategy("strategy_shiki"),
    YoutubeFindStrategy("strategy_youtube"),
]

__all__ = [
    "AniTousenTorrentStrategy",
    "ShikiAttachmentsStrategy",
    "SourceFindStrategy",
    "YoutubeFindStrategy",
    "strategies",
]
