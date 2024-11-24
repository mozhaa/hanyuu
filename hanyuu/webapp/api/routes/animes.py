from typing import List

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

import hanyuu.webparse.anidb as anidb

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
