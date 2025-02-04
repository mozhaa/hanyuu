import datetime
import hashlib
import logging
import re
from enum import Enum, auto
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse

import aiofiles
import aiohttp
import bencodepy
import qbittorrentapi as qbt

from hanyuu.config import getenv
from hanyuu.database.main.connection import get_engine
from hanyuu.database.main.models import QItemSource
from hanyuu.webparse.utils import default_headers
from hanyuu.workers.utils import FiledList

from .base import SourceDownloadStrategy, InvalidSource, TemporaryFailure

logger = logging.getLogger(__name__)


class TorrentDownloadingStrategy(SourceDownloadStrategy):
    async def run(self, qitem_source: QItemSource) -> None:
        worker_dir = Path(getenv("resources_dir")) / "workers" / "source" / "download" / self.name

        engine = await get_engine()
        async with engine.async_session() as session:
            session.add(qitem_source)
            qitem_source.downloading = True
            await session.commit()

        try:
            if qitem_source.additional_path is None:
                raise InvalidSource("Torrent additional path is invalid")

            torrent_path = TorrentPath(qitem_source.path)
            if not torrent_path.is_valid():
                raise InvalidSource("Torrent path is invalid")

            # retrieve infohash from torrent
            try:
                infohash = await torrent_path.infohash()
            except aiohttp.ClientError:
                raise TemporaryFailure(f"Failed to download torrent by url={qitem_source.path}")
            except (ValueError, KeyError):
                raise InvalidSource("Failed to bdecode torrent file contents")

            # search for that torrent in qbt
            torrent = next(iter(self.qbt_client.torrents_info(torrent_hashes=infohash)), None)
            if torrent is None:
                try:
                    # if torrent was not added before, add it
                    self.qbt_client.torrents_add(
                        urls=torrent_path.path,
                        save_path=str((Path(getenv("resources_dir") / "videos" / "sources" / self.name)).resolve()),
                        tags=f"hanyuu_{self.name}",
                        category="hanyuu",
                        is_paused=True,
                    )
                except (qbt.UnsupportedMediaType415Error, qbt.FileNotFoundError, qbt.TorrentFilePermissionError) as e:
                    exc_type = TemporaryFailure if isinstance(e, qbt.TorrentFilePermissionError) else InvalidSource
                    raise exc_type(f"qBitTorrent failed to add torrent by url={torrent_path.path} with exception: {e}")

                # get new torrent info
                torrent = next(iter(self.qbt_client.torrents_info(torrent_hashes=infohash)), None)
                if torrent is None:
                    raise InvalidSource(f'Couldn\'t add new torrent with url="{torrent_path.path}"')

                # set "don't download" for all files
                files = self.qbt_client.torrents_files(infohash)
                ids = [f["id"] for f in files]
                self.qbt_client.torrents_file_priority(infohash, ids, priority=0)
            else:
                files = self.qbt_client.torrents_files(infohash)

            # find file we need in torrent contents
            file_id, file_path = await self.find_file(files, qitem_source.additional_path)
            if file_id is None:
                raise InvalidSource(f'"{qitem_source.additional_path}" was not found in torrent {torrent_path.path}')

            # set high priority for file we need
            self.qbt_client.torrents_file_priority(infohash, file_id, 6)

            # resume torrent, in case it's paused after we added it
            self.qbt_client.torrents_resume(infohash)

            # add torrent into list of downloading torrents
            async with FiledList(str(worker_dir / "downloading_torrents.json")) as dtfs:
                dtfs.append(
                    {
                        "infohash": infohash,
                        "name": file_path,
                        "qitem_source_id": qitem_source.id,
                        "added_on": datetime.datetime.now(),
                    }
                )
        except Exception as e:
            async with engine.async_session() as session:
                session.add(qitem_source)
                qitem_source.downloading = False
                await session.commit()
            if isinstance(e, (qbt.NotFound404Error, qbt.Conflict409Error)):
                raise TemporaryFailure(f"Exception from qBitTorrent occured: {e}")
            # this should not happen, but if any other exceptions occured, it's an error
            raise e

    @property
    def qbt_client(self) -> qbt.Client:
        if not hasattr(self, "_qbt_client"):
            conn_info = {
                "host": getenv("qbt_host"),
                "port": getenv("qbt_port"),
                "username": getenv("qbt_username"),
                "password": getenv("qbt_password"),
            }

            self._qbt_client = qbt.Client(**conn_info)
            try:
                self._qbt_client.auth_log_in()
            except qbt.APIConnectionError as e:
                raise TemporaryFailure(f"Failed to auth to qBitTorrent: {e}")
        return self._qbt_client

    async def find_file(self, files: qbt.TorrentFilesList, name: str) -> Tuple[Optional[int], Optional[str]]:
        target = Path(name)
        for file in files:
            # with root folder or without
            with_root = Path(file["name"])
            without_root = Path("/".join(with_root.parts[1:]))
            if with_root == target or without_root == target:
                return file["id"], file["name"]
        return None, None


class PathType(Enum):
    LOCAL = auto()
    URL = auto()
    MAGNET = auto()


def is_magnet(path: str) -> bool:
    return path.startswith("magnet:")


def is_url(path: str) -> bool:
    return len(urlparse(path).netloc) >= 3 and path.endswith(".torrent")


def is_local(path: str) -> bool:
    if windows_disk_regex.match(path) is not None:
        path = path[2:]
    return forbidden_path_characters_regex.search(path) is None and path.endswith(".torrent")


def get_path_type(path: str) -> Optional[PathType]:
    if is_magnet(path):
        return PathType.MAGNET
    elif is_url(path):
        return PathType.URL
    elif is_local(path):
        return PathType.LOCAL
    return


forbidden_path_characters_regex = re.compile("[" + re.escape('<>":|?*') + "]")
windows_disk_regex = re.compile("^[A-Za-z]:.*$")


class TorrentPath:
    def __init__(self, path: str) -> None:
        self.path = path
        self.path_type = get_path_type(path)

    def is_valid(self) -> bool:
        if self.path_type == PathType.MAGNET:
            logger.warning("Magnet links are not supported yet (don't know how to retrieve info hash)")
            return False
        return self.path_type is not None

    async def infohash(self) -> str:
        if not hasattr(self, "_infohash"):
            if self.path_type == PathType.URL:
                async with aiohttp.ClientSession() as session:
                    async with session.get(self.path, headers=default_headers) as response:
                        data = await response.content.read()
            elif self.path_type == PathType.LOCAL:
                async with aiofiles.open(self.path, "rb") as f:
                    data = await f.read()
            else:
                raise ValueError(f"Invalid torrent path (recognized type = {self.path_type})")

            self._infohash = hashlib.sha1(bencodepy.encode(bencodepy.decode(data)[b"info"])).hexdigest()
        return self._infohash
