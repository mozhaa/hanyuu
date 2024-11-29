from fastapi import APIRouter
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from hanyuu.config import getenv

templates = Jinja2Templates(directory=getenv("templates_dir"))


def redirect_to(router: APIRouter, from_url: str, to_name: str) -> None:
    router.get(from_url, response_class=RedirectResponse)(
        lambda: RedirectResponse(router.url_path_for(to_name))
    )


def already_exists(name: str, **kwargs) -> Response:
    return Response(
        content=f"{name.capitalize()} with {kwargs} already exists", status_code=400
    )


def no_such(name: str, **kwargs) -> Response:
    return Response(
        content=f"{name.capitalize()} with {kwargs} does not exist", status_code=404
    )
