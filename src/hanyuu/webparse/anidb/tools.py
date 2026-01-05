from typing import Optional

from aiohttp import ClientSession

from hanyuu.config import getenv

from ..utils import default_headers
from ..zlib_memoize import zlib_memoize


@zlib_memoize(f"{getenv('resources_dir')}/anidb.sqlite3", key_creator=str)
async def get_page(anidb_id: int) -> Optional[str]:
    url = f"https://anidb.net/anime/{anidb_id}"
    print(f"Accessing {url}...")
    async with ClientSession() as session:
        async with session.get(url, headers=default_headers) as response:
            if response.ok:
                return await response.text()
