import re
from functools import cache
from typing import *

import orjson
from rapidfuzz import process
from rapidfuzz.fuzz import partial_token_ratio


@cache
def get_database(
    filename: str = "anime-offline-database-minified.json",
    only_on_anidb: bool = True,
) -> Dict[str, Any]:
    anidb_regexp = re.compile("anidb.net")

    def has_anidb(sources: List[str]) -> bool:
        return any([anidb_regexp.search(source) is not None for source in sources])

    with open(filename, "rb") as f:
        db = orjson.loads(f.read())
    if not only_on_anidb:
        return db
    db["data"] = [item for item in db["data"] if has_anidb(item["sources"])]
    return db


def search(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    def processor(item) -> str:
        return (" ".join([item["title"]] + item["synonyms"])).lower()

    def query_preprocess(pattern: str):
        return {"title": pattern, "synonyms": []}

    db = get_database()
    result = process.extract(
        query_preprocess(query),
        db["data"],
        processor=processor,
        scorer=partial_token_ratio,
        limit=10,
    )

    return result
