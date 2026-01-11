import argparse
import asyncio
import logging
from functools import cache
from pathlib import Path
from typing import Optional

import qbittorrentapi as qbt
from sqlalchemy import select

from hanyuu.config import getenv
from hanyuu.database.main.connection import get_engine
from hanyuu.database.main.models import QItemSource
from hanyuu.workers.utils import compare_path_with_and_without_root, try_make_path_relative, worker_log_config

_qbt_client: Optional[qbt.Client] = None
logger = logging.getLogger(__name__)


def get_qbt_client() -> qbt.Client:
    global _qbt_client
    if _qbt_client is None:
        conn_info = {
            "host": getenv("qbt_host"),
            "port": getenv("qbt_port"),
            "username": getenv("qbt_username"),
            "password": getenv("qbt_password"),
        }

        _qbt_client = qbt.Client(**conn_info)
        _qbt_client.auth_log_in()
    return _qbt_client


async def check(strategy_name: str) -> None:
    async with get_engine().async_session() as session:
        sources = (
            await session.scalars(
                select(QItemSource).where(QItemSource.platform == "torrent").where(QItemSource.dl_info.is_not(None))
            )
        ).all()

        logger.debug(f"found {len(sources)} downloading sources: {[source.id for source in sources]}")
        hashes = set([source.dl_info for source in sources])
        if len(hashes) == 0:
            return

        client = get_qbt_client()
        torrents = {t["hash"]: t for t in client.torrents_info(torrent_hashes=hashes)}

        @cache
        def get_torrent_files(infohash: str) -> qbt.TorrentFilesList:
            return client.torrents_files(infohash)

        for source in sources:
            if source.dl_info not in torrents:
                logger.warning(f"{source.path} not in QBT anymore")
                continue

            # get torrent contents from qbt
            files = get_torrent_files(source.dl_info)

            # find file we need
            it = (f for f in files if compare_path_with_and_without_root(f["name"], source.additional_path))  # type: ignore
            file = next(it, None)
            if file is None:
                logger.warning(f"{source.additional_path} was not found in torrent contents")
            elif file["progress"] == 1:
                local_fp = try_make_path_relative(
                    Path(torrents[source.dl_info]["save_path"]) / Path(file["name"])  # type: ignore
                )
                source.local_fp = str(local_fp)
                source.dl_info = None
                logger.info(f"{source.additional_path} has been downloaded (unset dl_info), {local_fp=}")
        await session.commit()


async def main(interval: float, strategy_name: str) -> None:
    while True:
        await check(strategy_name)
        await asyncio.sleep(interval)


if __name__ == "__main__":
    parser = argparse.ArgumentParser("Torrent status checking")
    parser.add_argument("-t", type=float, default=15, help="interval between fetches of qbt torrents info")
    parser.add_argument("--strategy", type=str, default="strategy_torrent", help="name of torrent strategy")
    args = parser.parse_args()
    worker_log_config(str(Path(getenv("resources_dir")) / "workers" / "torrents.log"))
    asyncio.run(main(args.t, args.strategy))
