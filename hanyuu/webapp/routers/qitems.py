from typing import *

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from hanyuu.database.main.models import Anime, Category, QItem
from hanyuu.webapp.deps import SessionDep

from .utils import no_such, templates, update_model

router = APIRouter(prefix="/qitems")


class QItemSchema(BaseModel):
    id: int
    category: Category
    number: int
    song_name: str
    song_artist: str


@router.post("", response_class=HTMLResponse)
async def create_qitem(request: Request, session: SessionDep, parent_id: int) -> Any:
    anime = await session.get(Anime, parent_id)
    if anime is None:
        return no_such("anime", id=parent_id)
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


@router.put("")
async def update_qitem(session: SessionDep, qitem: QItemSchema) -> Any:
    return await update_model(session, None, QItem, qitem)


@router.delete("/{id_}")
async def delete_qitem(session: SessionDep, id_: int) -> Any:
    qitem = await session.get(QItem, id_)
    if qitem is None:
        return no_such("qitem", id=id_)
    await session.delete(qitem)
    await session.commit()
