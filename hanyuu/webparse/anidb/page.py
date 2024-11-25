import re
from datetime import datetime
from typing import *

from pyquery import PyQuery as pq

from hanyuu.database.models import Category, QItem

from .tools import get_page


def default(value: Any):
    def decorator(wrapped: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(*args, **kwargs) -> Any:
            try:
                return wrapped(*args, **kwargs)
            except:
                return value

        return wrapper

    return decorator


class Page:
    def __init__(self, html: str) -> None:
        self.page = pq(html)

    @classmethod
    async def from_id(cls, anidb_id: int) -> Self:
        return cls(await get_page(anidb_id))

    def _parse_datetime(self, s: str) -> datetime:
        return datetime.strptime(s, "%Y-%m-%d")

    @property
    def anidb_id(self) -> int:
        url = self.page('meta[name="anidb-url"]').eq(0).attr("data-anidb-url")
        return int(re.search("aid=([0-9]+)", url).group(1))

    @property
    @default(None)
    def airing_start(self) -> Optional[datetime]:
        return self._parse_datetime(
            self.page('span[itemprop="startDate"]').eq(0).attr("content")
        )

    @property
    @default(None)
    def airing_end(self) -> Optional[datetime]:
        return self._parse_datetime(
            self.page('span[itemprop="endDate"]').eq(0).attr("content")
        )

    @property
    def mal_url(self) -> str:
        mal_buttons = self.page.find(".i_resource_mal").eq(0)
        href = mal_buttons.attr["href"]
        if href is not None:
            return href
        else:
            return mal_buttons.siblings("a").eq(0).attr["href"]

    @property
    def title(self) -> str:
        return (
            self.page('th.field:contains("Main Title")')
            .eq(0)
            .next_all()
            .children('span[itemprop="name"]')
            .eq(0)
            .text()
        )

    @property
    @default([])
    def qitems(self) -> List[Any]:
        qitems = []
        counters = {}
        for song in self.page("table#songlist > tbody td.name.song"):
            song = pq(song)
            category = (
                song.parent()
                .prev_all()
                .children()
                .extend(song.prev_all())
                .filter(".reltype")
                .eq(-1)
                .text()
                .strip()
                .lower()
            )
            if category == "opening":
                category = Category.Opening
            elif category == "ending":
                category = Category.Ending
            else:
                break
            number = counters[category] = counters.get(category, 0) + 1
            name = song.text().strip()
            name = name if name != "" else None
            try:
                artist = song.next_all("td.name.creator").text().strip()
            except:
                artist = None
            anidb_id = int(song("a").eq(0).attr("href").split("/")[-1])
            qitems.append(
                QItem(
                    anime_id=self.anidb_id,
                    category=category,
                    number=number,
                    song_name=name,
                    song_artist=artist,
                    song_anidb_id=anidb_id,
                )
            )
        return qitems
