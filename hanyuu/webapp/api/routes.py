from typing import *

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

import hanyuu.webparse.anidb as anidb
import hanyuu.webparse.anime_offline_database as aod
import hanyuu.webparse.shiki as shiki
from hanyuu.config import getenv
from hanyuu.database.models import Anime
from hanyuu.webapp.deps import SessionDep

router = APIRouter()
templates = Jinja2Templates(directory=getenv("templates_dir"))


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


@router.get("/animes/complete/search", response_class=JSONResponse)
async def search_animes_autocomplete(q: str) -> Any:
    return aod.search(query=q, limit=10)


@router.get("/animes/search", response_class=JSONResponse)
async def search_animes(request: Request, q: str) -> Any:
    return templates.TemplateResponse(
        request=request,
        name="anime/search.html",
        context={"animes": aod.search(query=q, limit=30, cutoff=60)},
    )


@router.get("/anime/{anime_id}", response_class=HTMLResponse)
async def read_anime(request: Request, session: SessionDep, anime_id: int) -> Any:
    anime = await session.get(Anime, anime_id)
    shiki_page = await shiki.Page.from_mal_id(anime.mal_id)
    qitems = await anime.awaitable_attrs.qitems
    for qitem in qitems:
        sources = await qitem.awaitable_attrs.sources
        for source in sources:
            await source.awaitable_attrs.timings
        await qitem.awaitable_attrs.difficulties
    return templates.TemplateResponse(
        request=request,
        name="anime/read.html",
        context={"anime": anime, "shiki": shiki_page},
    )


@router.post("/anime", status_code=201)
async def create_anime(session: SessionDep, anime_id: int) -> Any:
    if await session.get(Anime, anime_id) is not None:
        return Response(
            content=f"Anime with id={anime_id} already exists", status_code=400
        )
    page = anidb.Page(await anidb.get_page(anime_id))
    result = Anime(
        id=anime_id,
        mal_id=page.mal_id,
        title_ro=page.title_ro,
        title_en=page.title_en,
        poster_url=page.poster_url,
        poster_thumb_url=page.poster_thumb_url,
    )
    session.add(result)
    await session.commit()


@router.get("/anime/anidb/{anime_id}", response_class=HTMLResponse)
async def read_anidb_page(anime_id: int) -> Any:
    return await anidb.get_page(anime_id)


@router.post("/animes/search", response_class=JSONResponse)
async def search_anime(query: str) -> Any:
    # TODO: we can use shiki grqphql search, because it supports russian
    if len(query) == 0:
        return []
    return aod.search(query)
