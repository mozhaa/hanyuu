import re
from functools import cache
from typing import *

import orjson
from rapidfuzz import process
from rapidfuzz.fuzz import partial_ratio

from hanyuu.config import getenv


@cache
def get_database(
    filename: str = f"{getenv("resources_dir")}/anime-offline-database-minified.json",
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


def search(query: str, limit: int, cutoff: float = 80) -> List[Dict[str, Any]]:
    def processor(item) -> str:
        return ("|||".join([item["title"]] + item["synonyms"])).lower()

    def query_preprocess(pattern: str):
        return {"title": pattern, "synonyms": []}

    def result_postprocess(result: List[Any]) -> List[Any]:
        return [item[0] for item in result]

    db = get_database()
    result = process.extract(
        query_preprocess(query),
        db["data"],
        processor=processor,
        scorer=partial_ratio,
        limit=limit,
        score_cutoff=cutoff,
    )

    return result_postprocess(result)
