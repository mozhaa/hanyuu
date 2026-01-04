import asyncio
from argparse import Namespace
from typing import *

import aiofiles
from filelock import FileLock
from sqlalchemy import select

import hanyuu.webparse.anidb as anidb
from hanyuu.config import getenv
from hanyuu.database.main.connection import get_engine
from hanyuu.database.main.models import Anime, QItem


class ProcessedList:
    def __init__(self, filename: str) -> None:
        self.filename = filename

    async def _create_file(self) -> None:
        async with aiofiles.open(self.filename, "w+"):
            pass

    async def get(self) -> List[int]:
        await self._create_file()
        async with aiofiles.open(self.filename, "r") as f:
            return [int(t.strip()) for t in await f.readlines()]

    async def is_present(self, anidb_id: int) -> bool:
        return anidb_id in await self.get()

    async def insert(self, anidb_id: int) -> List[int]:
        if not await self.is_present(anidb_id):
            async with aiofiles.open(self.filename, "a+") as f:
                await f.write(f"{anidb_id}\n")


class Queue:
    def __init__(self, filename: str, lock_filename: str) -> None:
        self.filename = filename
        self.lock = FileLock(lock_filename)

    async def _create_queue_file(self) -> None:
        async with aiofiles.open(self.filename, "w+"):
            pass

    async def pop(self) -> Optional[int]:
        with self.lock:
            await self._create_queue_file()
            async with aiofiles.open(self.filename, "r") as f:
                lines = await f.readlines()
            anime_id = None
            if len(lines) == 0:
                return None
            anime_id = int(lines[0].strip())
            lines = lines[1:]
            async with aiofiles.open(self.filename, "w") as f:
                await f.writelines(lines)
            return anime_id

    async def push(self, anidb_id: int) -> None:
        with self.lock:
            await self._create_queue_file()
            async with aiofiles.open(self.filename, "a") as f:
                await f.writelines([f"{anidb_id}\n"])


async def process_anime(anime_id: int) -> None:
    print(f"Processing {anime_id}...", end="")
    page = await anidb.Page.from_id(anime_id)
    qitems = page.qitems
    async with engine.async_session() as session:
        result = await session.scalars(select(QItem).where(QItem.anime_id == anime_id))
        existing_qitems = [f"{q.category} {q.number}" for q in result.all()]
        qitems = [q for q in qitems if f"{q.category} {q.number}" not in existing_qitems]
        if len(qitems) > 0:
            session.add_all(qitems)
            await session.commit()
    await processed_list.insert(anime_id)
    print(f" fetched {len(qitems)}")


async def read_from_db() -> Optional[int]:
    async with engine.async_session() as session:
        anime_ids = (await session.scalars(select(Anime.id).outerjoin(Anime.qitems).where(QItem.id.is_(None)))).all()
    processed = await processed_list.get()
    for anime_id in anime_ids:
        if anime_id not in processed:
            return anime_id
    return None


async def start(args: Namespace) -> None:
    global worker_dir, engine, processed_list

    engine = await get_engine()
    worker_dir = f"{getenv("resources_dir")}/workers/qitems_parser"
    processed_list = ProcessedList(f"{worker_dir}/processed.txt")
    queue = Queue(f"{worker_dir}/queue.txt", f"{worker_dir}/queue.lock")

    while True:
        anime_id = await queue.pop() or await read_from_db()

        if anime_id is not None:
            await process_anime(anime_id)
        else:
            print("Nothing to process")

        await asyncio.sleep(args.interval)
