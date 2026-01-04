import random

from hanyuu.database.main.connection import get_engine
from hanyuu.database.main.models import QItemDifficulty

from .base import DifficultyStrategy


class Random(DifficultyStrategy):
    async def run(self, qitem_id: int) -> None:
        engine = await get_engine()
        async with engine.async_session() as session:
            difficulty = QItemDifficulty(
                qitem_id=qitem_id,
                value=random.randint(0, 100),
                added_by=self.name,
            )
            session.add(difficulty)
            await session.commit()
