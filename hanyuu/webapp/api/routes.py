from typing import *

from fastapi import APIRouter, Request
import asyncio
from fastapi.responses import HTMLResponse, JSONResponse, Response, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from pydantic import BaseModel

import hanyuu.webparse.shiki as shiki
import hanyuu.webparse.anidb as anidb
from hanyuu.config import getenv
from hanyuu.database.models import *
from hanyuu.webapp.deps import SessionDep

router = APIRouter()
templates = Jinja2Templates(directory=getenv("templates_dir"))


def redirect_to(from_url: str, to_name: str) -> None:
    router.get(from_url, response_class=RedirectResponse)(
        lambda: RedirectResponse(router.url_path_for(to_name))
    )


redirect_to("/", "read_animes")


@router.get("/animes", response_class=HTMLResponse)
async def read_animes(request: Request, session: SessionDep, page: int = 1) -> Any:
    page_size = 20
    result = await session.scalars(
        select(Anime)
        .order_by(Anime.updated_at.desc())
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    return templates.TemplateResponse(
        request=request, name="anime/read_all.html", context={"animes": result.all()}
    )


@router.get("/animes/search", response_class=JSONResponse)
async def search_animes(session: SessionDep, request: Request, q: str) -> Any:
    results = await shiki.search(query=q, limit=30)
    result_ids = [int(item["id"]) for item in results]
    already_exist, exist_in_aod = map(
        lambda r: r.all(),
        await asyncio.gather(
            session.scalars(select(Anime.mal_id).where(Anime.mal_id.in_(result_ids))),
            session.scalars(
                select(AODAnime.mal_id).where(AODAnime.mal_id.in_(result_ids))
            ),
        ),
    )
    results = [result for result in results if int(result["id"]) in exist_in_aod]
    for result in results:
        result["added"] = int(result["id"]) in already_exist
    return templates.TemplateResponse(
        request=request,
        name="anime/search.html",
        context={"animes": results},
    )


@router.get("/anime/{mal_id}", response_class=HTMLResponse)
async def read_anime(request: Request, session: SessionDep, mal_id: int) -> Any:
    anime = await session.get(Anime, mal_id)
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


@router.delete("/anime")
async def delete_anime(session: SessionDep, mal_id: int) -> Any:
    anime = await session.get(Anime, mal_id)
    if anime is None:
        return Response(
            content=f"Anime with id={mal_id} does not exist", status_code=400
        )
    await session.delete(anime)
    await session.commit()


@router.post("/anime", status_code=201)
async def create_anime(session: SessionDep, mal_id: int) -> Any:
    if await session.get(Anime, mal_id) is not None:
        return Response(
            content=f"Anime with id={mal_id} already exists", status_code=400
        )
    aod_anime = await session.get(AODAnime, mal_id)
    if aod_anime is None:
        return Response(content=f"No such anime with id={mal_id}", status_code=400)
    anidb_page, shiki_anime = await asyncio.gather(
        anidb.Page.from_id(aod_anime.anidb_id), shiki.get_anime(mal_id)
    )
    ratings_count = sum([score[1] for score in shiki_anime["scoresStats"]])
    rating = (
        sum([score[0] * score[1] for score in shiki_anime["scoresStats"]])
        / ratings_count
    )
    statuses = dict([(status[0], status[1]) for status in shiki_anime["statusesStats"]])
    result = Anime(
        mal_id=mal_id,
        anidb_id=aod_anime.anidb_id,
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


class QItemSchema(BaseModel):
    id: int
    category: Category
    number: int
    song_name: Optional[str] = None
    song_artist: Optional[str] = None


@router.post("/anime/{mal_id}/qitem", response_model=QItemSchema)
async def create_qitem(session: SessionDep, mal_id: int) -> Any:
    anime = await session.get(Anime, mal_id)
    if anime is None:
        return Response(f"Anime with id={mal_id} does not exist", status_code=400)
    qitems = await anime.awaitable_attrs.qitems
    # take minimal excluded opening number for new number
    numbers = sorted(
        [qitem.number for qitem in qitems if qitem.category == Category.Opening]
    )
    number = 1
    for existing_number in numbers:
        if number == existing_number:
            number += 1
        else:
            break
    qitem = QItem(anime_id=mal_id, category=Category.Opening, number=number)
    session.add(qitem)
    session.expire_on_commit = False
    await session.commit()
    return qitem
