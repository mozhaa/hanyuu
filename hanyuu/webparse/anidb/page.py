import re
from typing import *

from pyquery import PyQuery as pq

from hanyuu.database.models import Category, QItem

from ..utils import default
from .tools import get_page


class Page:
    def __init__(self, html: str) -> None:
        self.page = pq(html)

    @classmethod
    async def from_id(cls, anidb_id: int) -> Self:
        return cls(await get_page(anidb_id))

    @property
    def anidb_id(self) -> int:
        url = self.page('meta[name="anidb-url"]').eq(0).attr("data-anidb-url")
        return int(re.search("aid=([0-9]+)", url).group(1))

    @property
    @default([])
    def qitems(self) -> List[QItem]:
        qitems = []
        counters = {}
        anidb_ids = set()
        for song in self.page("table#songlist > tbody td.name.song"):
            song = pq(song)
            anidb_id = int(song("a").eq(0).attr("href").split("/")[-1])
            if anidb_id in anidb_ids:
                continue
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
            anidb_ids.add(anidb_id)
            qitems.append(
                QItem(
                    anime_id=self.anidb_id,
                    category=category,
                    number=number,
                    song_name=name,
                    song_artist=artist,
                )
            )
        return qitems
