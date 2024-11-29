from typing import *

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from hanyuu.database.models import QItem, QItemDifficulty
from hanyuu.webapp.deps import AddedByDep, SessionDep

from .utils import no_such, templates, update_model

router = APIRouter(prefix="/difficulties")


class DifficultySchema(BaseModel):
    id: int
    value: int = Field(ge=1, le=100)


@router.post("/", response_class=HTMLResponse)
async def create_difficulty(
    request: Request, added_by: AddedByDep, session: SessionDep, parent_id: int
) -> Any:
    qitem = await session.get(QItem, parent_id)
    if qitem is None:
        return no_such("qitem", id=parent_id)
    difficulty = QItemDifficulty(qitem_id=qitem.id, value=1, added_by=added_by)
    session.add(difficulty)
    await session.commit()
    return templates.TemplateResponse(
        request=request, name="difficulty/edit.html", context={"difficulty": difficulty}
    )


@router.put("/")
async def update_difficulty(
    session: SessionDep, added_by: AddedByDep, difficulty: DifficultySchema
) -> Any:
    return await update_model(session, added_by, QItemDifficulty, difficulty)


@router.delete("/{id_}")
async def delete_difficulty(session: SessionDep, id_: int) -> Any:
    difficulty = await session.get(QItemDifficulty, id_)
    if difficulty is None:
        return no_such("difficulty", id=id_)
    await session.delete(difficulty)
    await session.commit()
