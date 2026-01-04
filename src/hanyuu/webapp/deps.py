from typing import *

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from hanyuu.config import Settings, get_settings
from hanyuu.database.main.connection import get_engine


async def get_session() -> AsyncIterator[AsyncSession]:
    engine = await get_engine()
    async with engine.async_session(expire_on_commit=False) as session:
        yield session


def get_added_by() -> str:
    return "manual"


SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
AddedByDep = Annotated[str, Depends(get_added_by)]
