from fastapi import APIRouter

from .routes import routers

api_router = APIRouter()
for router in routers:
    api_router.include_router(router)
