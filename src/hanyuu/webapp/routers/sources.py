from typing import *

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse, Response
from pydantic import BaseModel

from hanyuu.database.main.models import QItem, QItemSource
from hanyuu.webapp.deps import AddedByDep, SessionDep

from .utils import no_such, templates, update_model

router = APIRouter(prefix="/sources")


class SourceSchema(BaseModel):
    id: int
    platform: str
    path: str
    additional_path: Optional[str]

    def model_post_init(self, __context):
        if self.additional_path is not None and len(self.additional_path) == 0:
            self.additional_path = None


@router.post("", response_class=HTMLResponse)
async def create_source(request: Request, added_by: AddedByDep, session: SessionDep, parent_id: int) -> Any:
    qitem = await session.get(QItem, parent_id)
    if qitem is None:
        return no_such("qitem", id=parent_id)
    source = QItemSource(qitem_id=qitem.id, platform="yt-dlp", path="", added_by=added_by)
    session.add(source)
    await session.commit()
    await source.awaitable_attrs.timings
    return templates.TemplateResponse(request=request, name="source/edit.html", context={"source": source})


@router.put("")
async def update_source(session: SessionDep, added_by: AddedByDep, source: SourceSchema) -> Any:
    return await update_model(session, added_by, QItemSource, source, additional_kwargs={"invalid": False})


@router.delete("/{id_}")
async def delete_source(session: SessionDep, id_: int) -> Any:
    source = await session.get(QItemSource, id_)
    if source is None:
        return no_such("source", id=id_)
    await session.delete(source)
    await session.commit()


@router.get("/{id_}/downloaded")
async def get_source_video(session: SessionDep, id_: int) -> Any:
    source = await session.get(QItemSource, id_)
    if source.local_fp is None:
        return Response(content=f"QItemSource with id={id_} has not been downloaded yet", status_code=404)
    return FileResponse(source.local_fp)
