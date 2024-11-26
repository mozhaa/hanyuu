from typing import *

from aiohttp import ClientSession
from pyquery import PyQuery as pq

from ..utils import default_headers
from ..zlib_memoize import zlib_memoize
from hanyuu.config import getenv


@zlib_memoize(F"{getenv("resources_dir")}/shiki.sqlite3", key_creator=str)
async def get_page(mal_id: int) -> Optional[str]:
    url = f"https://shikimori.one/animes/{mal_id}"
    async with ClientSession() as session:
        while True:
            print(f"Accessing {url}...")
            async with session.get(url, headers=default_headers) as response:
                page_data = await response.text()
                page = pq(page_data)
                errors = page(".error-404").eq(0)
                if len(errors) == 0:
                    return page_data
                if errors.text() != "302":
                    return None
                new_url = page(".dialog a").attr("href")
                if url == new_url:
                    return None
                url = new_url