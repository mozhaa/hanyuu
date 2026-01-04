import logging
import re

from rapidfuzz.distance.Levenshtein import similarity

from hanyuu.database.main.connection import get_engine
from hanyuu.database.main.models import Category, QItem, QItemSource

from .base import SourceFindStrategy

logger = logging.getLogger(__name__)


class ShikiAttachmentsStrategy(SourceFindStrategy):
    async def run(self, qitem_id: int) -> None:
        engine = await get_engine()
        async with engine.async_session() as session:
            qitem = await session.get(QItem, qitem_id)
            anime = await qitem.awaitable_attrs.anime
            attachments = anime.shiki_videos

        # replace NULL's with empty strings
        attachments = [[x if x is not None else "" for x in attachment] for attachment in attachments]

        # keep only op(ed) videos
        attachments = [x for x in attachments if x[0].lower() == self._short_category(qitem.category)]
        if len(attachments) == 0:
            logger.info("No suitable videos were found in attachments")
            return
        logger.info(f"Attachments of correct type: {len(attachments)}")

        # score by title and sort by score
        scored_attachments = [(self._score(x[1], qitem), x[2], x[1]) for x in attachments]
        scored_attachments.sort(reverse=True)

        # take best result, with score > 0.25
        score, link, title = scored_attachments[0]
        if score > 0:
            logger.info(f"Success, score = {score}, title = {title}, link = {link}")
            async with engine.async_session() as session:
                session.add(QItemSource(qitem_id=qitem.id, platform="yt-dlp", path=link, added_by=self.name))
                await session.commit()
        logger.info(f"Failure, score = {score}, title = {title}, link = {link}")

    def _short_category(self, category: Category) -> str:
        return {Category.Opening: "op", Category.Ending: "ed"}[category]

    def _score(self, title: str, qitem: QItem) -> float:
        # lower for ignoring case
        title = title.lower()

        # replace full category name with short
        title = re.sub("\\bopening", "op", title)
        title = re.sub("\\bending", "ed", title)

        pattern = f"\\b(nc *)?{self._short_category(qitem.category)} *([0-9]+) *(v[0-9]+)?\\b"
        match1 = re.search(pattern, title)
        match2 = re.search("(ver\\.|v\\.|version) *([0-9]+)", title)

        # is creditless (NCOP1 f.e.)
        creditless = match1 is not None and match1.group(1) is not None
        creditless_penalty = 1 if creditless else 0.5

        # opening(ending) number is correct
        number = int(match1.group(2) or "1") if match1 is not None else 1
        number_match = number == qitem.number

        # version (ED2v1 f.e.), the lower the version - the better
        if match1 is not None:
            version = int((match1.group(3) or "v1")[1:])
        elif match2 is not None:
            version = int(match2.group(2))
        else:
            version = 1
        version_penalty = 0.5 + 0.5 / version

        # song full version (OP1 Full f.e.)
        match3 = re.search(pattern + " *full\\b", title)
        is_full = match3 is not None

        # song name is present in title
        song_name_match = (
            len(qitem.song_name) >= 3
            and similarity(qitem.song_name.lower(), title.lower()) / len(qitem.song_name) > 0.9
        )

        total_score = (not is_full) * version_penalty * creditless_penalty * (song_name_match or number_match)
        logger.debug(
            f'Scoring "{title}": is_full={is_full}, number_match={number_match}, song_name_match={song_name_match}, '
            f"version_penalty={version_penalty}, creditless={creditless}; Total score: {total_score}"
        )

        return total_score
