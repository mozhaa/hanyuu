from typing import List

from .base import DifficultyStrategy
from .random import Random

strategies: List[DifficultyStrategy] = [Random("strategy_random")]
