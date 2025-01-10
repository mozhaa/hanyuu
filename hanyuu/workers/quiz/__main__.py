import argparse
import asyncio
import logging
import random
from abc import ABC
from datetime import datetime
from pathlib import Path
from typing import Generator, List

from sqlalchemy import select

from hanyuu.config import getenv
from hanyuu.database.main.connection import get_engine
from hanyuu.database.main.models import (
    Category,
    QItem,
    QItemDifficulty,
    QItemSource,
    QItemSourceTiming,
    QuizPart,
)
from hanyuu.video.videocat import cat
from hanyuu.video.videomakers import styles
from hanyuu.workers.difficulty.strategies import strategies as _d_strategies
from hanyuu.workers.source.find.strategies import strategies as _s_strategies
from hanyuu.workers.timing.strategies import strategies as _t_strategies

d_strategies = ["manual"] + [s.name for s in _d_strategies]
t_strategies = ["manual"] + [s.name for s in _t_strategies]
s_strategies = ["manual"] + [s.name for s in _s_strategies]
style_names = [vm.name for vm in styles]

logger = logging.getLogger(__name__)

root_dir = Path(getenv("resources_dir")) / "videos" / "quiz"


class RandomPicker(ABC):
    def choice[T](self, items: List[T]) -> T:
        return items[self.sample(len(items) - 1)]

    def gen_sequence[T](self, items: List[T], length: int) -> Generator[T, None, None]:
        for _ in range(length):
            yield self.choice(items)

    def sample(self, limit: int) -> int:
        pass


class SimpleRandomPicker(RandomPicker):
    def sample(self, limit: int) -> int:
        return random.randint(0, limit)


class MemoryRandomPicker(RandomPicker):
    def __init__(self, memory_size: int) -> None:
        self.memory_size = memory_size
        self.memory = []

    def sample(self, limit: int) -> int:
        choices = set(range(0, limit + 1))
        choices -= set(self.memory)
        choice = random.choice(list(choices))
        self.memory.append(choice)
        self.memory = self.memory[-self.memory_size:]
        return choice


async def main(args: argparse.Namespace) -> None:
    engine = await get_engine()
    async with engine.async_session() as session:
        quizparts = (
            await session.scalars(
                select(QuizPart.local_fp)
                .join(QuizPart.difficulty)
                .join(QuizPart.timing)
                .join(QItemSourceTiming.qitem_source)
                .join(QItemDifficulty.qitem)
                .where(
                    (QItem.category == Category.Opening)
                    if args.category == "op"
                    else ((QItem.category == Category.Ending) if args.category == "ed" else True)
                )
                .where(QItemSource.added_by.in_(args.source_strategies))
                .where(QItem.anime_id.in_(args.anime_ids) if len(args.anime_ids) > 0 else True)
                .where(QItemSource.added_by.in_(args.source_strategies))
                .where(QItemSourceTiming.added_by.in_(args.timing_strategies))
                .where(QItemDifficulty.added_by.in_(args.difficulty_strategies))
                .where(QuizPart.style.in_(args.styles))
            )
        ).all()

    if args.random == "simple":
        picker = SimpleRandomPicker()
    elif args.random == "memory":
        picker = MemoryRandomPicker(args.memory_size)

    root_dir.mkdir(parents=True, exist_ok=True)
    output_fp = root_dir / (args.output or (str(datetime.now().strftime("%Y_%m_%d__%H_%M_%S_%f") + ".mp4")))
    cat(picker.gen_sequence(quizparts, args.count), str(output_fp.resolve()))


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-S",
        "--styles",
        nargs="+",
        type=str,
        choices=style_names,
        default=style_names,
        help="styles to choose quiz parts from",
    )
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
    parser.add_argument(
        "-r",
        "--random",
        type=str,
        default="simple",
        choices=["simple", "memory"],
        help="type of random choicing of quiz parts order.\n"
        "simple - sample random quizpart on each iteration;\n"
        "memory - same as simple, but exclude ones, that was less than M steps before",
    )
    parser.add_argument(
        "-M",
        "--memory-size",
        type=int,
        default=10,
        help="size of memory for random memory algorithm",
    )
    parser.add_argument(
        "-n",
        "--count",
        type=int,
        required=True,
        help="number of quizparts to take",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        help="output filename (only name, without path and extension), or random if not specified",
    )
    args = parser.parse_args()
    asyncio.run(main(args))
