from typing import *

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from hanyuu.config import Settings, get_settings
from hanyuu.database.connection import get_db


async def get_session() -> AsyncIterator[AsyncSession]:
    db = await get_db("webapp")
    async with db.async_session(expire_on_commit=False) as session:
        yield session


def get_added_by() -> str:
    return "manual"


SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
AddedByDep = Annotated[str, Depends(get_added_by)]
