from typing import *
from urllib.parse import quote_plus
from ..utils import default_headers

from aiohttp import ClientSession


async def search(query: str) -> Any:
    url = f"https://myanimelist.net/search/prefix.json?type=all&keyword={quote_plus(query)}&v=1"
    async with ClientSession() as session:
        async with session.get(url, headers=default_headers) as response:
            return await response.json()
