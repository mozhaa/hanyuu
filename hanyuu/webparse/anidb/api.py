from typing import *

from aiohttp import ClientSession

from ..utils import default_headers
from ..zlib_memoize import zlib_memoize


@zlib_memoize("anidb.sqlite3", key_creator=str)
async def get_page(anidb_id: int) -> Optional[str]:
    url = f"https://anidb.net/anime/{anidb_id}"
    async with ClientSession() as session:
        async with session.get(url, headers=default_headers) as response:
            if response.ok:
                return await response.text()
