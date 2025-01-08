import logging
import re
from pathlib import Path
from typing import List, Optional

import bencodepy
from rapidfuzz import fuzz

from hanyuu.config import getenv
from hanyuu.database.main.connection import get_engine
from hanyuu.database.main.models import (
    Anime,
    AnimeType,
    AODAnime,
    Category,
    QItem,
    QItemSource,
)

from .base import SourceFindStrategy

logger = logging.getLogger(__name__)


class AniTousenTorrentStrategy(SourceFindStrategy):
    def __init__(
        self,
        name: str,
        torrent_fp: Optional[Path] = None,
        folder_threshold: float = 0.9,
        file_threshold: float = 0.8,
    ) -> None:
        super().__init__(name)
        self.torrent_fp = torrent_fp or Path(getenv("static_dir")) / "anitousen.torrent"
        self.folder_threshold = folder_threshold
        self.file_threshold = file_threshold

    @property
    def files(self) -> List[List[str]]:
        if not hasattr(self, "_files"):
            torrent = bencodepy.decode_from_file(self.torrent_fp)
            paths = [[b.decode(encoding="utf-8") for b in f[b"path"]] for f in torrent[b"info"][b"files"]]
            self._files = {}
            for path in paths:
                folder = "/".join(path[:-1])
                file = path[-1]
                if folder not in self._files:
                    self._files[folder] = []
                self._files[folder].append(file)

        return self._files

    async def run(self, qitem_id: int) -> None:
        source = await self._find_source(qitem_id)
        if source is None:
            logger.info(f"Strategy failure! qitem_id={qitem_id}")
            return
        logger.info(f"Strategy success! New source for qitem_id={qitem_id}: {source}")
        engine = await get_engine()
        async with engine.async_session() as session:
            session.add(source)
            await session.commit()

    async def _find_source(self, qitem_id: int) -> Optional[QItemSource]:
        engine = await get_engine()
        async with engine.async_session() as session:
            qitem = await session.get(QItem, qitem_id)
            anime = await qitem.awaitable_attrs.anime
            aod = await session.get(AODAnime, anime.mal_id)

        folder = self._find_folder(anime)
        if folder is None:
            return

        file = self._find_file(folder, qitem, anime, aod)
        if file is None:
            return

        return QItemSource(qitem_id=qitem_id, platform="torrent", path=folder + "/" + file, added_by=self.name)

    def _title_score(self, anime: Anime, folder: str) -> float:
        possible_titles = [anime.shiki_title_ro, anime.shiki_title_en]
        return max(fuzz.ratio(title, folder) / 100 for title in possible_titles if title is not None)

    def _find_folder(self, anime: Anime) -> Optional[str]:
        logger.info("Trying to find folder...")
        folders = list(self.files.keys())
        scored_folders = [(folder, self._title_score(anime, folder)) for folder in folders]

        scored_folders.sort(key=lambda x: x[1], reverse=True)
        best_folder, best_score = scored_folders[0]
        logger.info(
            f"Top 3 folders:\n\t{'\n\t'.join([f'({title} - {score:.3f})' for title, score in scored_folders[:3]])}"
        )

        if best_score >= self.folder_threshold:
            logger.info(f"Folder success! Best score = {best_score:.3f} >= {self.folder_threshold:.3f}")
            return best_folder
        logger.info(f"Folder failure! Best score = {best_score:.3f} < {self.folder_threshold:.3f}")

    def _find_file(self, folder: str, qitem: QItem, anime: Anime, aod: AODAnime) -> Optional[str]:
        files = self.files[folder]
        if len(files) == 0:
            return

        season = get_anime_season(anime, aod)

        global_pattern = r"^\[AniTousen\] (.+?) - (.+) \((.+)\)\..+$"

        # OP09, ONA 1, Movie 1-6
        tag_pattern = r"([A-Za-z]+)[ -]?(\d+-\d+|\d+)?"
        tag_separator_pattern = r"(?: |, )"
        tag1 = f"(?:{tag_pattern + tag_separator_pattern})?"
        tag2 = f"(?:{tag_pattern})"
        n_tags = 5
        tags_pattern = f"^{tag1 * (n_tags - 1) + tag2}$"
        tag_number_pattern = r"^(\d+)-(\d+)|(\d+)$"

        tags_regex = re.compile(tags_pattern)
        global_regex = re.compile(global_pattern)
        tag_num_regex = re.compile(tag_number_pattern)

        class AnitousenFilename:
            def __init__(self, filename: str) -> None:
                match = global_regex.match(filename)
                _, self.song_name, self.song_artist = match.groups()
                tags = tags_regex.match(match.group(1).strip()).groups()

                self.show_types = {}  # tv, ova, ona, special, movie
                self.theme_type = None  # op, ed
                self.theme_num = 1  # OP1, ED04
                self.version = None  # v1, v2
                self.episode = None  # EP04

                for tag_name, tag_num in zip(tags[::2], tags[1::2]):
                    if tag_name is None:
                        continue
                    tag_name = tag_name.lower()

                    if tag_name == "sp":
                        tag_name = "special"

                    n1 = None
                    if tag_num is not None:
                        tag_num_match = tag_num_regex.match(tag_num)
                        n1 = int(tag_num_match.group(3) or tag_num_match.group(1))

                    if tag_name in ["tv", "special", "ona", "ova", "movie", "game"]:
                        self.show_types[tag_name] = n1 if n1 is not None else 1
                    elif tag_name in ["op", "ed"]:
                        self.theme_type = tag_name
                        self.theme_num = n1 if n1 is not None else 1
                    elif tag_name == "v":
                        self.version = n1
                    elif tag_name == "ep":
                        self.episode = n1
                    else:
                        pass  # impossible

                # there's only one exception without explicit theme type
                self.theme_type = self.theme_type or "op"

            def season_score(self) -> float:
                expected_show_type_s = {
                    AnimeType.TV: "tv",
                    AnimeType.OVA: "ova",
                    AnimeType.ONA: "ona",
                    AnimeType.SPECIAL: "special",
                    AnimeType.UNKNOWN: "tv",
                    None: "tv",
                }[aod.anime_type if aod is not None else None]
                if expected_show_type_s not in self.show_types:
                    return 0
                return divergence(self.show_types[expected_show_type_s], season)

            def is_correct_theme_type(self) -> bool:
                return self.theme_type == {Category.Opening: "op", Category.Ending: "ed"}[qitem.category]

            def theme_number_score(self) -> float:
                return divergence(self.theme_num, qitem.number)

            def song_name_score(self) -> float:
                if qitem.song_name is not None and self.song_name is not None:
                    return fuzz.ratio(qitem.song_name.lower(), self.song_name.lower(), score_cutoff=90) / 100
                return 0

            def song_artist_score(self) -> float:
                if qitem.song_artist is not None and self.song_artist is not None:
                    return fuzz.ratio(qitem.song_artist.lower(), self.song_artist.lower(), score_cutoff=90) / 100
                return 0

            def version_score(self, weight: float = 0.25) -> float:
                # prioritize v1
                return 1 - weight + weight / (self.version if self.version is not None else 1)

            def episode_score(self) -> float:
                # prioritize not episode-specific themes
                if self.episode is None:
                    return 1
                return 0.9

            def score(self) -> float:
                if self.song_name_score() > 0:
                    return self.version_score() * 2
                if not self.is_correct_theme_type():
                    return 0

                return (
                    self.theme_number_score() * self.season_score() * self.version_score() * self.episode_score()
                ) ** 0.25

        scored_names = [(name, AnitousenFilename(name).score()) for name in files]
        scored_names.sort(key=lambda x: x[1], reverse=True)
        logger.info(f"Top 3 files:\n\t{'\n\t'.join([f'({title} - {score:.3f})' for title, score in scored_names[:3]])}")

        best_name, best_score = scored_names[0]
        if best_score >= self.file_threshold:
            logger.info(f"File success! Best score = {best_score:.3f} >= {self.file_threshold:.3f}")
            return best_name
        logger.info(f"File failure! Best score = {best_score:.3f} < {self.file_threshold:.3f}")


def get_anime_season(anime: Anime, aod: AODAnime) -> int:
    season_regex = re.compile(r"(?:season *(\d+)|(\d+)(?:st|nd|rd|th)? *season|\bs(\d+)\b)", flags=re.IGNORECASE)
    number_regex = re.compile(r"\b(\d+)\b")

    titles = (
        [anime.shiki_title_ro, anime.shiki_title_en, anime.shiki_title_jp, anime.shiki_title_ru]
        + (anime.shiki_synonyms or [])
        + ((aod.synonyms or []) if aod is not None else [])
    )
    titles = [t for t in titles if t is not None and len(t) > 0]
    numbers = dict()
    for title in titles:
        season_match = season_regex.search(title)
        if season_match is not None:
            season_num = next(iter([int(n) for n in season_match.groups() if n is not None and n.isdigit()]))
            return season_num

        number_match = number_regex.search(title)
        if number_match is not None:
            num = int(number_match.group(1))
            numbers[num] = numbers.get(num, 0) + 1
    best_number, quantity = max(list(numbers.items()), default=(0, 0), key=lambda x: x[1])
    if quantity > 3:
        return best_number
    return 1


def divergence(x: float, y: float, p: float = 2) -> float:
    return 1 / (1 + abs(x - y)) ** p
