from typing import List

from .base import SourceFindStrategy
from .shiki import ShikiAttachmentsStrategy
from .youtube import YoutubeFindStrategy

strategies: List[SourceFindStrategy] = [
    ShikiAttachmentsStrategy("strategy_shiki"),
    YoutubeFindStrategy("strategy_youtube"),
]
