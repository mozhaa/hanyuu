import argparse
import asyncio
import logging
from pathlib import Path

from sqlalchemy import case, delete, label, literal_column, select

from hanyuu.config import getenv
from hanyuu.database.main.connection import get_engine
from hanyuu.database.main.models import (
    QItemDifficulty,
    QItemSource,
    QItemSourceTiming,
    QuizPart,
)
from hanyuu.video.videomakers import VideoMakerBase, styles
from hanyuu.workers.utils import restrict_callrate, worker_log_config

d_strategies = ["manual", "strategy_random"]
t_strategies = ["manual", "strategy_default"]
root_dir = Path(getenv("resources_dir")) / "videos" / "quizparts"
worker_dir = Path(getenv("resources_dir")) / "workers" / "quizpart"
logger = logging.getLogger(__name__)


async def run_videomaker(timing_id: int, difficulty_id: int, videomaker: VideoMakerBase) -> None:
    engine = await get_engine()
    async with engine.async_session() as session:
        quiz_part = QuizPart(timing_id=timing_id, difficulty_id=difficulty_id, style="classic", local_fp="")
        session.add(quiz_part)
        await session.flush()
        await session.refresh(quiz_part)
        output_fp = root_dir / f"{quiz_part.id}.mkv"
        quiz_part.local_fp = str(output_fp.resolve())
        try:
            await videomaker.create_video(timing_id, difficulty_id, str(output_fp.resolve()))
            logger.info(f"Created quiz part on {output_fp}")
        except Exception as e:
            logger.warning("Video making failed!")
            await session.delete(quiz_part)
            raise e
        finally:
            await session.commit()


async def run_job(k: bool, videomaker: VideoMakerBase) -> None:
    engine = await get_engine()
    async with engine.async_session() as session:
        # delete quizparts, that are older than their difficulty or timing
        expired_quizparts = (
            await session.scalars(
                select(QuizPart.id)
                .join(QuizPart.difficulty)
                .join(QuizPart.timing)
                .where(
                    (QuizPart.updated_at < QItemDifficulty.updated_at)
                    | (QuizPart.updated_at < QItemSourceTiming.updated_at)
                )
            )
        ).all()
        if len(expired_quizparts) > 0:
            logger.info(f"Deleting expired quizparts with ids={expired_quizparts}")
            await session.execute(delete(QuizPart).where(QuizPart.id.in_(expired_quizparts)))
            await session.commit()

        # downloaded sources with their best possible difficulty and timing
        best_dt_pairs = (
            select(
                label("s_id", QItemSource.id),
                label("d_id", QItemDifficulty.id),
                label(
                    "d_prio",
                    case(
                        *[(QItemDifficulty.added_by == sname, i) for i, sname in enumerate(d_strategies)],
                        else_=len(d_strategies),
                    ),
                ),
                label("t_id", QItemSourceTiming.id),
                label(
                    "t_prio",
                    case(
                        *[(QItemSourceTiming.added_by == sname, i) for i, sname in enumerate(t_strategies)],
                        else_=len(t_strategies),
                    ),
                ),
                label("q_id", QItemSource.qitem_id),
            )
            .distinct(QItemSource.id)
            .join(QItemDifficulty, QItemDifficulty.qitem_id == QItemSource.qitem_id)
            .join(QItemSource.timings)
            .where(QItemSource.local_fp.isnot(None))
            .order_by(
                QItemSource.id,
                literal_column("d_prio"),
                literal_column("t_prio"),
                QItemDifficulty.updated_at.desc(),
                QItemSourceTiming.updated_at.desc(),
            )
        ).subquery()

        # subtract already existing quiz_parts from such sources and (difficulty, timing) pairs
        result = (
            await session.execute(
                select(
                    best_dt_pairs.c.s_id,
                    best_dt_pairs.c.d_id,
                    best_dt_pairs.c.t_id,
                    best_dt_pairs.c.q_id,
                )
                .outerjoin(
                    QuizPart,
                    (QuizPart.difficulty_id == best_dt_pairs.c.d_id)
                    & (QuizPart.timing_id == best_dt_pairs.c.t_id)
                    & (QuizPart.style == "classic"),
                )
                .where(QuizPart.id.is_(None))
            )
        ).fetchone()

        if result is not None:
            s_id, d_id, t_id, q_id = result
            logger.info(
                f"Running style '{videomaker.name}' on qitem_id={q_id}, "
                f"source_id={s_id}, difficulty_id={d_id}, timing_id={t_id}"
            )
            await run_videomaker(t_id, d_id, videomaker)
            if not k:
                quizparts_to_delete = (
                    await session.scalars(
                        select(QuizPart.id)
                        .join(QuizPart.timing)
                        .join(QItemSourceTiming.qitem_source)
                        .where(QItemSource.id == s_id)
                        .where(
                            (QuizPart.difficulty_id != d_id)
                            | (QuizPart.timing_id != t_id)
                            | (QuizPart.style != videomaker.name)
                        )
                    )
                ).all()

                if len(quizparts_to_delete) > 0:
                    logger.info(f"Clearing quizparts with same source_id={s_id} by ids={quizparts_to_delete}")
                    await session.execute(delete(QuizPart).where(QuizPart.id.in_(quizparts_to_delete)))
                    await session.commit()
            return

    logger.debug("No jobs were found")


async def main(interval: float, k: bool, videomaker: VideoMakerBase) -> None:
    rate_limited_run_job = restrict_callrate(interval)(run_job)
    while True:
        await rate_limited_run_job(k, videomaker)


if __name__ == "__main__":
    worker_log_config(str((worker_dir / ".log").resolve()))
    parser = argparse.ArgumentParser()
    parser.add_argument("style", type=str, help="style of videomaker to use")
    parser.add_argument("-t", type=float, default=10, help="interval in seconds between job starts")
    parser.add_argument(
        "-k",
        action="store_true",
        help="keep existing quiz parts, even if better one was created (same source but better difficulty or timing)",
    )
    args = parser.parse_args()
    try:
        videomaker = next(filter(lambda vm: vm.name == args.style, styles))
    except StopIteration:
        raise ValueError(f"No such style: {args.style}. Possible styles: {[vm.name for vm in styles]}")
    asyncio.run(main(args.t, args.k, videomaker))
