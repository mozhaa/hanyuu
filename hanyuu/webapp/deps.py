from typing import *

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from hanyuu.config import Settings, get_settings
from .db.connection import get_session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
