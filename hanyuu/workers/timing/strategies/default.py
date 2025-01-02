from datetime import time

from hanyuu.database.main.connection import get_engine
from hanyuu.database.main.models import QItemSourceTiming

from .base import TimingStrategy


class DefaultTiming(TimingStrategy):
    def __init__(self, name: str) -> None:
        self.name = name

    async def run(self, qitem_source_id: int) -> None:
        engine = await get_engine()
        async with engine.async_session() as session:
            timing = QItemSourceTiming(
                qitem_source_id=qitem_source_id,
                guess_start=time(),
                reveal_start=time(second=50),
                added_by=self.name,
            )
            session.add(timing)
            await session.commit()
