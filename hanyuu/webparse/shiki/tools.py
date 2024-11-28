from typing import *

import orjson
from aiohttp import ClientSession

from ..utils import default_headers

graphql_url = "https://shikimori.one/api/graphql"
graphql_args = (
    "id, name, russian, english, japanese, synonyms, "
    "kind, rating, score, status, episodes, duration, "
    "airedOn { year month day }, releasedOn { year month day }, url, "
    "poster { originalUrl mainUrl }, genres { name }, "
    "videos { kind name url playerUrl }, scoresStats { score count }, "
    "statusesStats { status count }"
)


def process_anime(anime: Dict[str, Any]) -> Dict[str, Any]:
    def set_default(obj: Dict[str, Any], key: str, value: Any) -> Dict[str, Any]:
        if obj.get(key, None) is None:
            obj[key] = value
        return obj

    def set_defaults(obj: Dict[str, Any], defaults: Dict[str, Any]) -> Dict[str, Any]:
        for key, value in defaults.items():
            obj = set_default(obj, key, value)
        return obj

    anime = set_default(
        anime,
        "poster",
        {
            "originalUrl": "https://shikimori.one/assets/globals/missing/main.png",
            "mainUrl": "https://shikimori.one/assets/globals/missing/"
            "preview_animanga.png",
        },
    )

    anime["statusesStats"] = set_defaults(
        dict(map(lambda x: x.values(), anime["statusesStats"])),
        {
            "planned": 0,
            "completed": 0,
            "watching": 0,
            "dropped": 0,
            "on_hold": 0,
        },
    ).items()

    anime["scoresStats"] = set_defaults(
        dict(map(lambda x: x.values(), anime["scoresStats"])),
        {i: 0 for i in range(1, 11)},
    ).items()

    return anime


async def get_anime(mal_id: int) -> Optional[Dict[str, Any]]:
    query = f'{{ animes(ids: "{mal_id}", limit: 1) {{ {graphql_args} }} }}'
    body = {"operationName": None, "query": query, "variables": {}}
    async with ClientSession(headers=default_headers) as session:
        async with session.post(url=graphql_url, json=body) as response:
            data = orjson.loads(await response.text())
    animes = data["data"]["animes"]
    return process_anime(animes[0]) if len(animes) > 0 else None


async def search(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    query = (
        f'{{ animes(search: "{query}", limit: {limit}, rating: "!rx") '
        f"{{ {graphql_args} }} }}"
    )
    body = {"operationName": None, "query": query, "variables": {}}
    async with ClientSession(headers=default_headers) as session:
        async with session.post(url=graphql_url, json=body) as response:
            data = orjson.loads(await response.text())
    return list(map(process_anime, data["data"]["animes"]))
