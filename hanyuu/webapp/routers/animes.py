import asyncio
from typing import *

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel
from sqlalchemy import select

import hanyuu.webparse.anidb as anidb
import hanyuu.webparse.shiki as shiki
from hanyuu.database.main.models import Anime, AODAnime
from hanyuu.webapp.deps import SessionDep

from .utils import already_exists, no_such, templates

router = APIRouter(prefix="/animes")


@router.get("", response_class=HTMLResponse)
async def read_animes(request: Request, session: SessionDep, page: int = 1) -> Any:
    page_size = 20
    result = await session.scalars(
        select(Anime).order_by(Anime.updated_at.desc()).limit(page_size).offset((page - 1) * page_size)
    )
    return templates.TemplateResponse(request=request, name="anime/read_all.html", context={"animes": result.all()})


@router.get("/search", response_class=JSONResponse)
async def search_animes(session: SessionDep, request: Request, q: str) -> Any:
    results = await shiki.search(query=q, limit=30)
    result_ids = [int(item["id"]) for item in results]
    already_exist = (await session.scalars(select(Anime.mal_id).where(Anime.mal_id.in_(result_ids)))).all()
    for result in results:
        result["added"] = int(result["id"]) in already_exist
    return templates.TemplateResponse(
        request=request,
        name="anime/search.html",
        context={"animes": results},
    )


@router.post("", status_code=201)
async def create_anime(session: SessionDep, mal_id: int) -> Any:
    if await session.get(Anime, mal_id) is not None:
        return already_exists("anime", mal_id=mal_id)
    shiki_anime = await shiki.get_anime(mal_id)
    aod_anime = await session.get(AODAnime, mal_id)
    shiki_anime, aod_anime = await asyncio.gather(shiki.get_anime(mal_id), session.get(AODAnime, mal_id))

    anidb_id = None
    if aod_anime is None:
        if shiki_anime.get("anidb_id", None) is None:
            raise RuntimeError(
                f"Couldn't parse anidb_id by mal_id={mal_id} (missing from AOD, not in shiki external links)"
            )
        else:
            anidb_id = shiki_anime["anidb_id"]
    else:
        anidb_id = aod_anime.anidb_id

    anidb_page = await anidb.Page.from_id(anidb_id)
    ratings_count = sum([score[1] for score in shiki_anime["scoresStats"]])
    rating = (
        sum([score[0] * score[1] for score in shiki_anime["scoresStats"]]) / ratings_count
        if ratings_count > 0
        else None
    )
    statuses = dict([(status[0], status[1]) for status in shiki_anime["statusesStats"]])
    result = Anime(
        mal_id=mal_id,
        anidb_id=anidb_id,
        shiki_title_ro=shiki_anime["name"],
        shiki_title_ru=shiki_anime["russian"],
        shiki_title_en=shiki_anime["english"],
        shiki_title_jp=shiki_anime["japanese"],
        shiki_url=shiki_anime["url"],
        shiki_status=shiki_anime["status"],
        shiki_poster_url=shiki_anime["poster"]["originalUrl"],
        shiki_poster_thumb_url=shiki_anime["poster"]["mainUrl"],
        shiki_episodes=shiki_anime["episodes"],
        shiki_duration=shiki_anime["duration"],
        shiki_rating=rating,
        shiki_ratings_count=ratings_count,
        shiki_planned=statuses["planned"],
        shiki_completed=statuses["completed"],
        shiki_watching=statuses["watching"],
        shiki_dropped=statuses["dropped"],
        shiki_on_hold=statuses["on_hold"],
        shiki_age_rating=shiki_anime["rating"],
        shiki_aired_on=shiki_anime["airedOn"],
        shiki_released_on=shiki_anime["releasedOn"],
        shiki_videos=[v.values() for v in shiki_anime["videos"]],
        shiki_synonyms=shiki_anime["synonyms"],
        shiki_genres=[g["name"] for g in shiki_anime["genres"]],
        qitems=anidb_page.qitems,
    )
    session.add(result)
    await session.commit()


@router.get("/{mal_id}", response_class=HTMLResponse)
async def read_anime(request: Request, session: SessionDep, mal_id: int) -> Any:
    anime = await session.get(Anime, mal_id)
    if anime is None:
        return no_such("anime", id=mal_id)
    qitems = await anime.awaitable_attrs.qitems
    for qitem in qitems:
        sources = await qitem.awaitable_attrs.sources
        for source in sources:
            await source.awaitable_attrs.timings
        await qitem.awaitable_attrs.difficulties
    return templates.TemplateResponse(
        request=request,
        name="anime/read.html",
        context={"anime": anime},
    )


@router.delete("/{mal_id}")
async def delete_anime(session: SessionDep, mal_id: int) -> Any:
    anime = await session.get(Anime, mal_id)
    if anime is None:
        return Response(content=f"Anime with id={mal_id} does not exist", status_code=400)
    await session.delete(anime)
    await session.commit()


class AnimeAliasScheme(BaseModel):
    id: int
    alias: str


@router.put("")
async def update_alias(session: SessionDep, obj: AnimeAliasScheme) -> Any:
    anime = await session.get(Anime, obj.id)
    if anime is None:
        return Response(content=f"Anime with id={obj.id} does not exist", status_code=400)
    if len(obj.alias) == 0:
        obj.alias = None
    anime.alias = obj.alias
    await session.commit()
