from typing import *

from pyquery import PyQuery as pq

from ..utils import default
from .tools import get_page


class Page:
    def __init__(self, html: str) -> None:
        self.page = pq(html)

    @classmethod
    async def from_mal_id(cls, mal_id: int) -> Self:
        return cls(await get_page(mal_id))

    @property
    @default("https://shikimori.one/assets/globals/missing/preview_animanga.png")
    def poster_thumb_url(self) -> str:
        return self.page(".c-poster .b-image img").eq(0).attr("src")

    @property
    @default("https://shikimori.one/assets/globals/missing/main.png")
    def poster_url(self) -> str:
        return self.page(".c-poster .b-image").eq(0).attr("data-href")

    @property
    def titles(self) -> List[str]:
        return list(
            map(
                lambda s: s.strip(),
                self.page("header.head > h1").eq(0).text().split("/"),
            )
        )

    @property
    def title_ru(self) -> str:
        return self.titles[0]

    @property
    def title_ro(self) -> str:
        return self.titles[-1]

    @property
    def scores_stats(self) -> List[Tuple[str, int]]:
        return eval(self.page("#rates_scores_stats").eq(0).attr["data-stats"])

    @property
    @default(None)
    def rating(self) -> Optional[float]:
        return (
            sum([int(stat[0]) * stat[1] for stat in self.scores_stats])
            / self.ratings_count
        )

    @property
    @default(0)
    def ratings_count(self) -> int:
        return sum([stat[1] for stat in self.scores_stats])

    @property
    def statuses_stats(self) -> Dict[str, int]:
        return {
            k: v
            for k, v in eval(
                self.page("#rates_statuses_stats").eq(0).attr("data-stats")
            )
        }

    @property
    @default(0)
    def watching(self) -> int:
        return self.statuses_stats.get("watching")

    @property
    @default(0)
    def completed(self) -> int:
        return self.statuses_stats.get("completed")

    @property
    @default(0)
    def plan_to_watch(self) -> int:
        return self.statuses_stats.get("planned")

    @property
    @default(0)
    def dropped(self) -> int:
        return self.statuses_stats.get("dropped")

    @property
    @default(0)
    def on_hold(self) -> int:
        return self.statuses_stats.get("on_hold")

    @property
    @default(0)
    def favorites(self) -> int:
        return int(self.page(".b-favoured .subheadline .count").eq(0).text())

    @property
    @default(0)
    def comments(self) -> int:
        return int(self.page('[title="Все комментарии"] > .count').eq(0).text())

    @property
    def anidb_url(self) -> str:
        return self.page(".b-external_link.anime_db .b-link").eq(0).attr("data-href")
