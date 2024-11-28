from sqlalchemy import URL

from hanyuu.config import get_settings
from hanyuu.helpers.database import Database

from .models import Base

connections = {}


async def get_db(conn_name: str, echo: bool = False) -> Database:
    global connections
    if conn_name not in connections:
        settings = get_settings()
        db = Database(
            url=URL.create(
                drivername="postgresql+asyncpg",
                database=settings.db_name,
                username=settings.db_username,
                password=settings.db_password,
                host=settings.db_host,
                port=settings.db_port,
            ),
            base=Base,
        )
        db.connect(echo=echo)
        await db.create_tables()
        connections[conn_name] = db
    return connections[conn_name]
