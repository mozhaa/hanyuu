import argparse
import asyncio
import logging
from pathlib import Path
from typing import Optional

import qbittorrentapi as qbt
from sqlalchemy import select

from hanyuu.config import getenv
from hanyuu.database.main.connection import get_engine
from hanyuu.database.main.models import QItemSource
from hanyuu.workers.utils import try_make_path_relative, worker_log_config

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
        sources = await session.scalars(
            select(QItemSource).where(QItemSource.platform == "torrent").where(QItemSource.dl_info.is_not(None))
        )

        hashes = set([source.dl_info for source in sources])
        if len(hashes) == 0:
            return

        client = get_qbt_client()
        torrents = {t["hash"]: t for t in client.torrents_info(torrent_hashes=hashes)}

        for source in sources:
            if source.dl_info not in torrents:
                logger.warning(f"{source.additional_path} has been removed as it's not in QBT anymore")
                continue

            # get torrent contents from qbt
            files = client.torrents_files(source.dl_info)

            # find file we need
            file = next(iter([f for f in files if f["name"] == source.additional_path]), None)
            if file is None:
                logger.warning(f"{source.additional_path} has been removed as it has invalid file name")
            elif file["progress"] == 1:
                engine = get_engine()
                async with engine.async_session() as session:
                    local_fp = try_make_path_relative(
                        Path(torrents[source.dl_info]["save_path"]) / Path(source.additional_path)  # type: ignore
                    )
                    source.local_fp = str(local_fp)
                    source.dl_info = None
                    await session.commit()
                logger.info(
                    f"{source.additional_path} has been removed as it has been downloaded, local_fp='{local_fp}'"
                )


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
