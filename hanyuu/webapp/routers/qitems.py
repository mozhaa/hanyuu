from typing import *

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

from hanyuu.database.models import Anime, Category, QItem
from hanyuu.webapp.deps import SessionDep

from .utils import no_such, templates

router = APIRouter(prefix="/qitems")


class QItemSchema(BaseModel):
    id: int
    category: Category
    number: int
    song_name: str
    song_artist: str


@router.post("/", response_class=HTMLResponse)
async def create_qitem(request: Request, session: SessionDep, parent_id: int) -> Any:
    anime = await session.get(Anime, parent_id)
    if anime is None:
        return no_such("anime", mal_id=parent_id)
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
    qitem = QItem(anime_id=parent_id, category=Category.Opening, number=number)
    session.add(qitem)
    session.expire_on_commit = False
    await session.commit()
    sources = await qitem.awaitable_attrs.sources
    for source in sources:
        await source.awaitable_attrs.timings
    await qitem.awaitable_attrs.difficulties
    return templates.TemplateResponse(
        request=request, name="qitem/edit.html", context={"qitem": qitem}
    )


@router.put("/")
async def update_qitem(session: SessionDep, qitem: QItemSchema) -> Any:
    existing_qitem = await session.get(QItem, qitem.id)
    if existing_qitem is None:
        return no_such("qitem", id=qitem.id)
    for k, v in qitem.model_dump().items():
        existing_qitem.__setattr__(k, v)
    try:
        await session.commit()
    except IntegrityError as e:
        return Response(e._message, status_code=400)


@router.delete("/{qitem_id}")
async def delete_qitem(session: SessionDep, qitem_id: int) -> Any:
    qitem = await session.get(QItem, qitem_id)
    if qitem is None:
        return no_such("qitem", id=qitem_id)
    await session.delete(qitem)
    await session.commit()
