import asyncio
import re

import orjson
from aiohttp import ClientSession
from sqlalchemy import delete

from hanyuu.database.connection import get_db
from hanyuu.database.models import AnimeType, AODAnime, ReleaseSeason, Status
from hanyuu.webparse.utils import default_headers

mal_regexp = re.compile("^https://myanimelist.net/anime/([0-9]+)$")
anidb_regexp = re.compile("^https://anidb.net/anime/([0-9]+)")


async def update() -> None:
    url = (
        "https://raw.githubusercontent.com/manami-project/anime-offline-database/"
        "master/anime-offline-database-minified.json"
    )

    print("Downloading .json...", end=" ")
    async with ClientSession() as session:
        async with session.get(url, headers=default_headers) as response:
            raw_json = await response.read()
            print(f"downloaded {len(raw_json)} bytes")
    data = orjson.loads(raw_json)

    print(f"Database version from {data["lastUpdate"]}")
    print("Processing items...", end=" ")
    animes = []
    for item in data["data"]:
        mal_id = None
        anidb_id = None
        for source in item["sources"]:
            mal_match = mal_regexp.search(source)
            if mal_match is not None:
                mal_id = int(mal_match.group(1))
                continue
            anidb_match = anidb_regexp.search(source)
            if anidb_match is not None:
                anidb_id = int(anidb_match.group(1))
                continue
        if mal_id is None or anidb_id is None:
            continue

        anime = AODAnime(
            anidb_id=anidb_id,
            mal_id=mal_id,
            sources=item["sources"],
            poster_url=item["picture"],
            poster_thumb_url=item["thumbnail"],
            title=item["title"],
            anime_type=AnimeType[item["type"]],
            status=Status[item["status"]],
            episodes=item["episodes"],
            duration=item["duration"]["value"] if "duration" in item else None,
            tags=item["tags"],
            synonyms=item["synonyms"],
            related_animes=item["relatedAnime"],
            release_year=(
                item["animeSeason"]["year"] if "year" in item["animeSeason"] else None
            ),
            release_season=ReleaseSeason[item["animeSeason"]["season"]],
        )

        animes.append(anime)

    print(f"Found {len(animes)} animes")
    print("Commiting to database...", end=" ")
    db = await get_db("aod_update")
    async with db.async_session() as session:
        await session.execute(delete(AODAnime))
        session.add_all(animes)
        await session.commit()

    print("Ok")


if __name__ == "__main__":
    asyncio.run(update())
