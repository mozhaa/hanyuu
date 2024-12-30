from .base import DifficultyStrategy
from .random import Random
from typing import List

strategies: List[DifficultyStrategy] = [Random("strategy_random")]
