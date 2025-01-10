from .base import TimingStrategy
from .default import DefaultTiming
from .random import RandomTiming
from typing import List

strategies: List[TimingStrategy] = [
    DefaultTiming("strategy_default"),
    RandomTiming("strategy_random"),
]
