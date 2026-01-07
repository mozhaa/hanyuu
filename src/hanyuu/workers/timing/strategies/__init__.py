from typing import List

from .base import TimingStrategy
from .default import DefaultTiming
from .random import RandomTiming

strategies: List[TimingStrategy] = [
    DefaultTiming("strategy_default"),
    RandomTiming("strategy_random"),
]

__all__ = ["DefaultTiming", "RandomTiming", "TimingStrategy", "strategies"]
