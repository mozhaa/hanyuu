import random
from datetime import time
from typing import Tuple

from hanyuu.database.main.connection import get_engine
from hanyuu.database.main.models import QItemSourceTiming

from .base import TimingStrategy


class RandomTiming(TimingStrategy):
    async def run(self, qitem_source_id: int) -> None:
        engine = await get_engine()
        async with engine.async_session() as session:
            timing = QItemSourceTiming(
                qitem_source_id=qitem_source_id,
                guess_start=random_time(1 * 1000000, 80 * 1000000),
                reveal_start=time(),
                added_by=self.name,
            )
            session.add(timing)
            await session.commit()


def random_time(a: int, b: int) -> time:
    def propagate(value: int, q: int) -> Tuple[int, int]:
        return value // q, value % q

    microsecond = random.randint(a, b)
    second, microsecond = propagate(microsecond, 1000000)
    minute, second = propagate(second, 60)
    hour, minute = propagate(minute, 60)
    return time(hour=hour, minute=minute, second=second, microsecond=microsecond)
