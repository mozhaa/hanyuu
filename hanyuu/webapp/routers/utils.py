from typing import *

from fastapi import APIRouter
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

from hanyuu.config import getenv
from hanyuu.database.main.models import Base
from hanyuu.webapp.deps import AddedByDep, SessionDep

templates = Jinja2Templates(directory=getenv("templates_dir"))


def redirect_to(router: APIRouter, from_url: str, to_name: str) -> None:
    router.get(from_url, response_class=RedirectResponse)(lambda: RedirectResponse(router.url_path_for(to_name)))


def already_exists(name: str, **kwargs) -> Response:
    return Response(content=f"{name.capitalize()} with {kwargs} already exists", status_code=400)


def no_such(name: str, **kwargs) -> Response:
    return Response(content=f"{name.capitalize()} with {kwargs} does not exist", status_code=404)


async def update_model(
    session: SessionDep,
    added_by: Optional[AddedByDep],
    model_type: Type[Base],
    new_item: BaseModel,
    additional_kwargs: Dict[str, Any] = {},
) -> Any:
    existing_item = await session.get(model_type, new_item.id)
    if existing_item is None:
        return no_such("source", id=new_item.id)
    additional_kwargs.update(new_item.model_dump())
    for k, v in additional_kwargs.items():
        existing_item.__setattr__(k, v)
    if added_by is not None:
        # NOTE: replace author mark on update (not sure if it's correct decision)
        existing_item.added_by = added_by
    try:
        await session.commit()
    except IntegrityError as e:
        return Response(content=e._message(), status_code=400)
