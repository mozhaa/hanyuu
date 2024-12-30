from .strategy import SourceFindingStrategy
from .youtube import YoutubeFindingStrategy

# strategies in priority order (from most prioritized to least)
strategies = [YoutubeFindingStrategy("youtube_strategy")]
