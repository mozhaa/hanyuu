from typing import *

import orjson
from aiohttp import ClientSession

from ..utils import default_headers

graphql_url = "https://shikimori.one/api/graphql"
graphql_args = (
    "name, russian, english, japanese, synonyms, "
    "kind, rating, score, status, episodes, duration, "
    "airedOn { year month day }, releasedOn { year month day }, url, "
    "poster { originalUrl mainUrl }, genres { name }, "
    "videos { kind name url playerUrl }, scoresStats { score count }, "
    "statusesStats { status count }"
)


async def get_anime(mal_id: int) -> Optional[Dict[str, Any]]:
    query = f'{{ animes(ids: "{mal_id}", limit: 1) {{ {graphql_args} }} }}'
    body = {"operationName": None, "query": query, "variables": {}}
    async with ClientSession(headers=default_headers) as session:
        async with session.post(url=graphql_url, json=body) as response:
            data = orjson.loads(await response.text())
    animes = data["data"]["animes"]
    return animes[0] if len(animes) > 0 else None


async def search(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    query = f'{{ animes(search: "{query}", limit: {limit}) {{ {graphql_args} }} }}'
    body = {"operationName": None, "query": query, "variables": {}}
    async with ClientSession(headers=default_headers) as session:
        async with session.post(url=graphql_url, json=body) as response:
            data = orjson.loads(await response.text())
    return data["data"]["animes"]
