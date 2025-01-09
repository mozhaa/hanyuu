from typing import List

from .base import SourceFindStrategy
from .shiki import ShikiAttachmentsStrategy
from .youtube import YoutubeFindStrategy
from .anitousen import AniTousenTorrentStrategy

strategies: List[SourceFindStrategy] = [
    AniTousenTorrentStrategy("strategy_anitousen"),
    ShikiAttachmentsStrategy("strategy_shiki"),
    YoutubeFindStrategy("strategy_youtube"),
]
