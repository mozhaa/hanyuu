import asyncio
import logging
import re
from functools import partial
from typing import Any, Callable, Optional

from rapidfuzz import fuzz
from yt_dlp import YoutubeDL

from hanyuu.database.main.connection import get_engine
from hanyuu.database.main.models import QItem, QItemSource

from .base import SourceFindStrategy

logger = logging.getLogger(__name__)


class YoutubeFindStrategy(SourceFindStrategy):
    def __init__(
        self,
        name: str,
        title_algorithm: Callable[[str, str], float] = fuzz.token_ratio,
        score_threshold: float = 0.7,
        possible_durations: Optional[list[float]] = None,
        helpers: Optional[list[str]] = None,
        negative_helpers: Optional[list[str]] = None,
    ) -> None:
        super().__init__(name)
        self.title_algorithm = title_algorithm
        self.score_threshold = score_threshold
        self.possible_durations = possible_durations if possible_durations is not None else [90, 150]
        self.helpers = helpers if helpers is not None else ["Creditless", "4K", "HD", "1080p"]
        self.negative_helpers = negative_helpers if negative_helpers is not None else ["Cover", "AMV", "Full", "Lyrics"]

    async def run(self, qitem_id: int) -> None:
        try:
            qitem_source = await self.find_source(qitem_id)
        except RuntimeError as e:
            logger.warning(f"youtube find strategy failed with runtime error: {e}")
            return
        if qitem_source is not None:
            engine = get_engine(True)
            async with engine.async_session() as session:
                session.add(qitem_source)
                await session.commit()

    async def find_source(self, qitem_id: int) -> Optional[QItemSource]:
        sources = await self.get_sorted_sources(qitem_id)
        source, score = sources[0]
        if score >= self.score_threshold:
            logger.info(f"Top score: {score} >= {self.score_threshold}, link={source.path}, success")
            return source
        logger.info(f"Top score: {score} < {self.score_threshold}, link={source.path}, failure")

    async def get_sorted_sources(self, qitem_id: int) -> list[tuple[QItemSource, float]]:
        engine = get_engine(True)
        async with engine.async_session() as session:
            qitem = await session.get(QItem, qitem_id)
            if qitem is None:
                raise RuntimeError(f"qitem with {qitem_id=} does not exist")
            anime = await qitem.awaitable_attrs.anime
            title_ro = anime.shiki_title_ro
            title_en = anime.shiki_title_en

        scores = {}
        for title in [title_ro, title_en]:
            category = qitem.category.name
            query = f"{title} {category} {qitem.number}"
            logger.info(f"YouTube search query: {query}")
            loop = asyncio.get_running_loop()
            ydl_opts = {"quiet": True, "extract_flat": True}
            with YoutubeDL(ydl_opts) as ydl:
                info = await loop.run_in_executor(
                    None, partial(ydl.extract_info, f"ytsearch10:{query}", download=False)
                )
            results = info["entries"]
            logger.info(f"Found {len(results)} youtube search results")
            for _video in results:
                video = {"title": _video["title"], "link": _video["url"], "duration": _video["duration"]}
                score = self._score(video, query)
                link = video["link"]
                if link not in scores:
                    logger.debug(f"Title='{video['title']}', link={link}, score={score:.3f}")
                scores[link] = max(scores.get(link, 0), score)

        scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        scores = [
            (
                QItemSource(qitem_id=qitem.id, platform="yt-dlp", path=link, added_by=self.name),
                score,
            )
            for link, score in scores
        ]

        return scores

    def _title_score(self, title: str, query: str) -> float:
        return self.title_algorithm(preprocess(query, num_w=5), preprocess(title, num_w=5)) / 100

    def _helpers_score(self, title: str) -> float:
        return helpers_score(self.helpers, title)

    def _negative_helpers_score(self, title: str) -> float:
        return helpers_score(self.negative_helpers, title)

    def _duration_score(self, duration: float) -> float:
        return max([assymetrical_similarity(duration, d) for d in self.possible_durations])

    def _score(self, video: dict[str, Any], query: str) -> float:
        negative_helpers_score = self._negative_helpers_score(video["title"])
        if negative_helpers_score > 0:
            return 0

        title_score = self._title_score(video["title"], query)
        helpers_score = self._helpers_score(video["title"])
        duration_score = self._duration_score(video["duration"])

        total_score = contrast(title_score, 2.5) ** 2 * duration_score + 0.5 * helpers_score

        return total_score


def similarity(x: float, y: float, sigma: float = -2, p: float = 2, k: float = 0) -> float:
    return max(0, 1 - abs(x - y) * k) / (1 + 10**sigma * abs(x - y) ** p)


def assymetrical_similarity(
    x: float,
    y: float,
    sigma_left: float = -1,
    p_left: float = 4,
    k_left: float = 0,
    sigma_right: float = -8,
    p_right: float = 6,
    k_right: float = 0.008,
) -> float:
    if x < y:
        return similarity(x, y, sigma=sigma_left, p=p_left, k=k_left)
    else:
        return similarity(x, y, sigma=sigma_right, p=p_right, k=k_right)


def contrast(x: float, k: float = 2) -> float:
    if x < 0.5:
        return (x * 2) ** k / 2
    else:
        return 1 - ((1 - x) * 2) ** k / 2


def preprocess(title: str, num_w: int = 1) -> str:
    title = title.lower().strip()
    title = re.sub("[^A-Za-z0-9 \\-!?:/]", " ", title)
    title = re.sub("\\bopening\\b", "op", title)
    title = re.sub("\\bending\\b", "ed", title)
    title = re.sub("\\b(op|ed)\\b +([0-9]+)", "\\1\\2", title)
    title = re.sub("\\b(op|ed)\\b", "\\g<1>1", title)
    title = re.sub("\\bseason\\b +([0-9]+)", "s\\1", title)
    numerals = ["1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th", "9th", "10th"]
    for i, s in enumerate(numerals):
        title = re.sub(f"{s} +\\bseason\\b", f"s{i + 1}", title)
    if num_w > 1:
        title = re.sub("[0-9]", "\\g<0>" * num_w, title)
    title = re.sub(" {2,}", " ", title)
    return title


def helpers_score(helpers: list[str], s: str) -> float:
    return len(re.findall("|".join([re.escape(w) for w in helpers]), s)) / len(helpers)
