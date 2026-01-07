from typing import List

from .base import DifficultyStrategy
from .dumb import Dumb
from .random import Random

strategies: List[DifficultyStrategy] = [Dumb("strategy_dumb"), Random("strategy_random")]

__all__ = ["DifficultyStrategy", "Dumb", "Random", "strategies"]
