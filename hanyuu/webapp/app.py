from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from hanyuu.config import getenv

from .api import api_router

app = FastAPI()
app.mount("/static", StaticFiles(directory=getenv("static_dir")), name="static")
app.include_router(api_router)
