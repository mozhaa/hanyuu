from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from hanyuu.config import getenv

from .routers import *
from .routers.utils import redirect_to

app = FastAPI()
redirect_to(app, "/", "read_animes")
app.mount("/static", StaticFiles(directory=getenv("static_dir")), name="static")

app.include_router(animes.router)
app.include_router(qitems.router)
app.include_router(difficulties.router)
app.include_router(sources.router)
app.include_router(timings.router)
