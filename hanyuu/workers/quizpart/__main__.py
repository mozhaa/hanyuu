import argparse
import asyncio
import logging
from pathlib import Path

from sqlalchemy import case, delete, label, literal_column, select

from hanyuu.config import getenv
from hanyuu.database.main.connection import get_engine
from hanyuu.database.main.models import QItem, QItemDifficulty, QItemSource, QItemSourceTiming, QuizPart, Category
from hanyuu.video.videomakers import VideoMakerBase, styles
from hanyuu.workers.difficulty.strategies import strategies as _d_strategies
from hanyuu.workers.source.find.strategies import strategies as _s_strategies
from hanyuu.workers.timing.strategies import strategies as _t_strategies
from hanyuu.workers.utils import worker_log_config

d_strategies = ["manual"] + [s.name for s in _d_strategies]
t_strategies = ["manual"] + [s.name for s in _t_strategies]
s_strategies = ["manual"] + [s.name for s in _s_strategies]

root_dir = Path(getenv("resources_dir")) / "videos" / "quizparts"
worker_dir = Path(getenv("resources_dir")) / "workers" / "quizpart"
logger = logging.getLogger(__name__)


async def run_videomaker(timing_id: int, difficulty_id: int, videomaker: VideoMakerBase) -> None:
    engine = await get_engine()
    async with engine.async_session() as session:
        quiz_part = QuizPart(timing_id=timing_id, difficulty_id=difficulty_id, style=videomaker.name, local_fp="")
        session.add(quiz_part)
        await session.flush()
        await session.refresh(quiz_part)
        output_fp = str(root_dir / f"{quiz_part.id}.mkv")
        quiz_part.local_fp = output_fp
        try:
            await videomaker.create_video(timing_id, difficulty_id, output_fp)
            logger.info(f"Created quiz part on {output_fp}")
        except Exception as e:
            logger.warning("Video making failed!")
            await session.delete(quiz_part)
            raise e
        finally:
            await session.commit()


async def run_jobs(args: argparse.Namespace) -> None:
    engine = await get_engine()
    async with engine.async_session() as session:
        # delete quizparts, that are older than their difficulty or timing
        expired_quizparts = (
            await session.scalars(
                select(QuizPart.id)
                .join(QuizPart.difficulty)
                .join(QuizPart.timing)
                .join(QItemSourceTiming.qitem_source)
                .join(QItemSource.qitem)
                .where(
                    (QItem.category == Category.Opening)
                    if args.category == "op"
                    else ((QItem.category == Category.Ending) if args.category == "ed" else True)
                )
                .where(QItemSource.added_by.in_(args.source_strategies))
                .where(QItem.anime_id.in_(args.anime_ids) if len(args.anime_ids) > 0 else True)
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
                        *[(QItemDifficulty.added_by == sname, i) for i, sname in enumerate(args.difficulty_strategies)],
                        else_=len(args.difficulty_strategies),
                    ),
                ),
                label("t_id", QItemSourceTiming.id),
                label(
                    "t_prio",
                    case(
                        *[(QItemSourceTiming.added_by == sname, i) for i, sname in enumerate(args.timing_strategies)],
                        else_=len(args.timing_strategies),
                    ),
                ),
                label("q_id", QItemSource.qitem_id),
            )
            .distinct(QItemSource.id)
            .join(QItemDifficulty, QItemDifficulty.qitem_id == QItemSource.qitem_id)
            .join(QItemSource.timings)
            .join(QItemSource.qitem)
            .where(
                (QItem.category == Category.Opening)
                if args.category == "op"
                else ((QItem.category == Category.Ending) if args.category == "ed" else True)
            )  # only accepted qitem category
            .where(QItemSourceTiming.added_by.in_(args.timing_strategies))  # only accepted difficulties
            .where(QItemDifficulty.added_by.in_(args.difficulty_strategies))  # only accepted timings
            .where(QItemSource.added_by.in_(args.source_strategies))  # only accepted sources
            .where(QItem.anime_id.in_(args.anime_ids) if len(args.anime_ids) > 0 else True)  # only accepted anime ids
            .where(QItemSource.local_fp.isnot(None))  # only downloaded
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
                    & (QuizPart.style == args.style),
                )
                .where(QuizPart.id.is_(None))
            )
        ).all()

        if len(result) == 0:
            await asyncio.sleep(args.wait)
            return

        videomaker = next(filter(lambda vm: vm.name == args.style, styles))
        for s_id, d_id, t_id, q_id in result:
            logger.info(
                f"Running style '{args.style}' on qitem_id={q_id}, "
                f"source_id={s_id}, difficulty_id={d_id}, timing_id={t_id}"
            )
            await run_videomaker(t_id, d_id, videomaker)


async def main(args: argparse.Namespace) -> None:
    while True:
        await run_jobs(args)


if __name__ == "__main__":
    worker_log_config(str((worker_dir / ".log").resolve()))
    parser = argparse.ArgumentParser()
    parser.add_argument("style", type=str, choices=[vm.name for vm in styles], help="style of videomaker to use")
    parser.add_argument("-w", "--wait", type=float, default=10, help="waiting time, if no jobs were found")
    parser.add_argument(
        "-t",
        "--timing-strategies",
        nargs="+",
        type=str,
        choices=t_strategies,
        default=t_strategies,
        help="timing strategies to accept (in order of priority)",
    )
    parser.add_argument(
        "-d",
        "--difficulty-strategies",
        nargs="+",
        type=str,
        choices=d_strategies,
        default=d_strategies,
        help="difficulty strategies to accept (in order of priority)",
    )
    parser.add_argument(
        "-s",
        "--source-strategies",
        nargs="+",
        type=str,
        default=s_strategies,
        choices=s_strategies,
        help="source finding strategies to accept",
    )
    parser.add_argument(
        "-a",
        "--anime-ids",
        nargs="+",
        type=int,
        default=[],
        help="anime ids, to create quizparts for (if not specified, all animes are accepted)",
    )
    parser.add_argument(
        "-c",
        "--category",
        type=str,
        choices=["op", "ed"],
        help="if specified, create quizparts only for qitems of these categories",
    )
    args = parser.parse_args()
    asyncio.run(main(args))
