import argparse
import asyncio
import logging
from pathlib import Path
from typing import Optional

import qbittorrentapi as qbt

from hanyuu.config import getenv
from hanyuu.database.main.connection import get_engine
from hanyuu.database.main.models import QItemSource
from hanyuu.workers.utils import FiledList, try_make_path_relative, worker_log_config

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
    worker_dir = Path(getenv("resources_dir")) / "workers" / "source" / "download" / strategy_name
    async with FiledList(str(worker_dir / "downloading_torrents.json")) as dtfs:
        hashes = set([t["infohash"] for t in dtfs])
        if len(hashes) == 0:
            return

        client = get_qbt_client()
        torrents = {t["hash"]: t for t in client.torrents_info(torrent_hashes=hashes)}

        new_dtfs = []
        for dtf in dtfs:
            if dtf["infohash"] not in torrents:
                logger.warning(f"{dtf["name"]} has been removed as it's not in QBT anymore")
                continue

            # get torrent contents from qbt
            files = client.torrents_files(dtf["infohash"])

            # find file we need
            file = next(iter([f for f in files if f["name"] == dtf["name"]]), None)
            if file is None:
                logger.warning(f"{dtf["name"]} has been removed as it has invalid file name")
            elif file["progress"] == 1:
                engine = await get_engine()
                async with engine.async_session() as session:
                    source = await session.get(QItemSource, dtf["qitem_source_id"])
                    local_fp = try_make_path_relative(Path(torrents[dtf["infohash"]]["save_path"]) / Path(dtf["name"]))
                    source.local_fp = str(local_fp)
                    source.downloading = False
                    await session.commit()
                logger.info(f"{dtf["name"]} has been removed as it has been downloaded, local_fp='{local_fp}'")
            else:
                new_dtfs.append(dtf)

        dtfs[:] = new_dtfs


async def main(interval: float, strategy_name: str) -> None:
    while True:
        await check(strategy_name)
        await asyncio.sleep(interval)


if __name__ == "__main__":
    parser = argparse.ArgumentParser("Torrent status checking")
    parser.add_argument("-t", type=float, default=15, help="interval between fetches of qbt torrents info")
    parser.add_argument("--strategy", type=str, default="strategy_torrent", help="name of torrent strategy")
    args = parser.parse_args()
    worker_log_config(Path(getenv("resources_dir")) / "workers" / "torrents.log")
    asyncio.run(main(args.t, args.strategy))
