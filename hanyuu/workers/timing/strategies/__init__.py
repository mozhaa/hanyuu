from .base import TimingStrategy
from .default import DefaultTiming
from typing import List

strategies: List[TimingStrategy] = [DefaultTiming("strategy_default")]
