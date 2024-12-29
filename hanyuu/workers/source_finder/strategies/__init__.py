from .strategy import SourceFindingStrategy
from .youtube import YoutubeSearchStrategy

# strategies in priority order (from most prioritized to least)
strategies = [YoutubeSearchStrategy()]
