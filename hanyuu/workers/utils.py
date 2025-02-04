import argparse
import asyncio
import logging
import logging.config
import time
from pathlib import Path
from typing import Any, Awaitable, Callable, List, Optional

import orjson
from filelock import FileLock

logger = logging.getLogger(__name__)


class FiledList:
    def __init__(self, fp: str, readonly: bool = False) -> None:
        self.fp = fp
        self.lock = FileLock(fp + ".lock")
        self.readonly = readonly

    async def __aenter__(self) -> List[Any]:
        self.lock.acquire()
        with open(self.fp, "ab+") as f:
            f.seek(0, 0)
            data = f.read()

        if len(data) == 0:
            self.obj = []
        else:
            self.obj = orjson.loads(data)

        if not isinstance(self.obj, list):
            raise ValueError(f"{self.obj} is not a list!")
        return self.obj

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        if not self.readonly and exc_type is None:
            if not isinstance(self.obj, list):
                raise ValueError(f"{self.obj} is not a list!")
            with open(self.fp, "wb+") as f:
                f.write(orjson.dumps(self.obj))
        self.lock.release()


def restrict_callrate(interval: float, synchronized: bool = False):
    """
    Restrict call rate of async function, so that if one tries to call it,
    and previous call was less than interval seconds before, it waits.

    If synchronized is True, function will be runned under lock, so callers
    will also wait for others to end.
    """

    lock = asyncio.Lock()
    prev_call = 0

    def decorator(wrapped):
        async def wrapper(*args, **kwargs):
            nonlocal prev_call, lock
            async with lock:
                wait_time = prev_call + interval - time.time()
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                prev_call = time.time()

                if synchronized:
                    return await wrapped(*args, **kwargs)
            if not synchronized:
                return await wrapped(*args, **kwargs)

        return wrapper

    return decorator


class StrategyRunner:
    def __init__(
        self,
        select_job: Callable[[], Optional[Awaitable[None]]],
        synchronized: bool = True,
    ) -> None:

        parser = argparse.ArgumentParser(
            "Strategies runner",
            "Concurrently run strategies",
        )
        parser.add_argument(
            "--interval",
            type=int,
            default=10,
            help="interval time between strategy runs in seconds",
        )
        parser.add_argument(
            "--num-threads",
            type=int,
            default=1,
            help="number of threads, that concurrently run strategies",
        )

        self.args = parser.parse_args()
        self.select_job = restrict_callrate(self.args.interval, synchronized)(select_job)

    async def poll(self, select_job: Callable[[], Awaitable[Optional[Awaitable[None]]]]) -> None:
        while True:
            job = await select_job()
            if job is not None:
                await job

    async def poll_many(self) -> None:
        return await asyncio.gather(*[self.poll(self.select_job) for _ in range(self.args.num_threads)])

    def start(self) -> None:
        asyncio.run(self.poll_many())


def worker_log_config(fp: str) -> None:
    class OnlyInternalFilter(logging.Filter):
        def filter(self, record):
            if record.levelno < logging.INFO:
                return False
            path = record.name.split(".")
            is_internal = path[0] in ["__main__", "hanyuu"]
            if not is_internal and record.levelno < logging.WARNING:
                return False
            return True

    CONFIG = {
        "version": 1,
        "formatters": {
            "brief": {"format": "%(asctime)s - %(levelname)s - %(message)s", "datefmt": "%H:%M:%S"},
            "precise": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%d-%m-%y %H:%M:%S",
            },
        },
        "filters": {
            "internal": {
                "()": OnlyInternalFilter,
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "INFO",
                "formatter": "brief",
                "stream": "ext://sys.stderr",
                "filters": ["internal"],
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": fp,
                "level": "NOTSET",
                "formatter": "precise",
                "maxBytes": 5242880,
                "encoding": "utf-8",
                "mode": "a",
            },
        },
        "loggers": {
            "root": {"level": "NOTSET", "handlers": ["console", "file"]},
            "hanyuu": {"level": "NOTSET"},
            "__main__": {"level": "NOTSET"},
        },
    }

    Path(fp).parent.mkdir(parents=True, exist_ok=True)

    logging.config.dictConfig(CONFIG)


def try_make_path_relative(path: Path | str) -> Path:
    if isinstance(path, str):
        path = Path(path)

    path = path.resolve()

    try:
        return path.relative_to(Path.cwd())
    except ValueError:
        return path


async def delayed[T](delay: float, wrapped: Callable[..., T], *args, **kwargs) -> T:
    await asyncio.sleep(delay)
    return await wrapped(*args, **kwargs)
