import math

from hanyuu.database.main.connection import get_engine
from hanyuu.database.main.models import Anime, QItem, QItemDifficulty

from .base import DifficultyStrategy


class Dumb(DifficultyStrategy):
    async def run(self, qitem_id: int) -> None:
        engine = get_engine()
        async with engine.async_session() as session:
            qitem = await session.get(QItem, qitem_id)
            if qitem is None:
                raise RuntimeError(f"no such qitem with {qitem_id=}")
            anime: Anime = await qitem.awaitable_attrs.anime

            watch_count = anime.shiki_completed + anime.shiki_watching
            number = qitem.number

            value = 241.75 - 44.54 * math.log10(watch_count) + 2.48 * number
            value = max(0, min(100, value))

            difficulty = QItemDifficulty(
                qitem_id=qitem_id,
                value=value,
                added_by=self.name,
            )
            session.add(difficulty)
            await session.commit()
