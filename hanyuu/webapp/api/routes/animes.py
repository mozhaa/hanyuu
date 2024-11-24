from sqlalchemy import select
from fastapi import APIRouter
from ...db.models import Anime
from ...deps import SessionDep


router = APIRouter()


@router.get("/")
@router.get("/animes/")
async def get_animes(session: SessionDep, page: int = 1):
    page_size = 20
    return (
        await session.scalars(
            select(Anime).limit(page_size).offset((page - 1) * page_size)
        )
    ).all()
