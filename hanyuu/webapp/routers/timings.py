from datetime import datetime, time
from typing import *

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, field_validator

from hanyuu.database.models import QItem, QItemSourceTiming
from hanyuu.webapp.deps import AddedByDep, SessionDep

from .utils import no_such, templates, update_model

router = APIRouter(prefix="/timings")


class TimingSchema(BaseModel):
    id: int
    guess_start: time
    reveal_start: time

    @classmethod
    def str_to_time(cls, repr: str) -> time:
        possible_formats = [
            "%H:%M:%S.%f",
            "%M:%S.%f",
            "%S.%f",
            "%H:%M:%S",
            "%M:%S",
            "%S",
        ]
        for format in possible_formats:
            try:
                return datetime.strptime(repr, format).time()
            except ValueError:
                continue
        raise ValueError(f'"{repr}" is not a valid timestamp')

    @field_validator("guess_start", mode="before")
    @classmethod
    def guess_start_transform(cls, s: str) -> time:
        return cls.str_to_time(s)

    @field_validator("reveal_start", mode="before")
    @classmethod
    def reveal_start_transform(cls, s: str) -> time:
        return cls.str_to_time(s)


@router.post("", response_class=HTMLResponse)
async def create_timing(
    request: Request, added_by: AddedByDep, session: SessionDep, parent_id: int
) -> Any:
    qitem = await session.get(QItem, parent_id)
    if qitem is None:
        return no_such("qitem", id=parent_id)
    timing = QItemSourceTiming(qitem_source_id=qitem.id, added_by=added_by)
    session.add(timing)
    await session.commit()
    return templates.TemplateResponse(
        request=request, name="timing/edit.html", context={"timing": timing}
    )


@router.put("")
async def update_timing(
    session: SessionDep, added_by: AddedByDep, timing: TimingSchema
) -> Any:
    return await update_model(session, added_by, QItemSourceTiming, timing)


@router.delete("/{id_}")
async def delete_timing(session: SessionDep, id_: int) -> Any:
    timing = await session.get(QItemSourceTiming, id_)
    if timing is None:
        return no_such("timing", id=id_)
    await session.delete(timing)
    await session.commit()
