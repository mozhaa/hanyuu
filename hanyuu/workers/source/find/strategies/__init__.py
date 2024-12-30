from .base import SourceFindStrategy
from .youtube import YoutubeFindStrategy
from typing import List

strategies: List[SourceFindStrategy] = [YoutubeFindStrategy("strategy_youtube")]