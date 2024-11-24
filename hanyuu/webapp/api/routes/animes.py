from typing import *

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

import hanyuu.webparse.anidb as anidb
import hanyuu.webparse.mal as mal
import hanyuu.webparse.anime_offline_database as aod

from ...db.models import Anime
from ...deps import SessionDep

router = APIRouter()


class AnimeIn(BaseModel):
    id: int


class AnimeOut(BaseModel):
    id: int
    title: str


@router.post("/animes/", response_model=AnimeOut)
async def create_anime(session: SessionDep, anime: AnimeIn) -> Anime:
    page = anidb.Page(await anidb.get_page(anime.id))
    anime = Anime(id=anime.id, title=page.title)
    session.add(anime)
    try:
        await session.commit()
        return anime
    except IntegrityError:
        await session.rollback()
        raise ValueError("Failed to add anime!")


@router.get("/animes/", response_model=List[AnimeOut])
async def read_animes(session: SessionDep, page: int = 1) -> List[Anime]:
    page_size = 20
    result = await session.scalars(
        select(Anime)
        .order_by(Anime.updated_at.desc())
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    return result.all()


@router.get("/anime/anidb/{anime_id}", response_class=HTMLResponse)
async def read_anidb_page(anime_id: int) -> Any:
    return await anidb.get_page(anime_id)


@router.get("/animes/search", response_class=JSONResponse)
async def search_anime(query: str) -> Any:
    if len(query) == 0:
        return []
    return aod.search(query)
