import asyncio
import logging
import logging.config
import time
from pathlib import Path
from typing import Any, Callable, List

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


def try_make_path_relative(path: Path | str, root_path: Path) -> Path:
    if isinstance(path, str):
        path = Path(path)

    path = path.expanduser().resolve()

    try:
        return path.relative_to(root_path)
    except ValueError:
        return path


def make_absolute(path: Path, root_path: Path) -> Path:
    if path.is_absolute():
        return path
    else:
        return root_path / path


async def delayed[T](delay: float, wrapped: Callable[..., T], *args, **kwargs) -> T:
    await asyncio.sleep(delay)
    return await wrapped(*args, **kwargs)


def compare_path_with_and_without_root(path: str, path_without_root: str) -> bool:
    with_root = Path(path)
    without_root = Path("/".join(with_root.parts[1:]))
    p = Path(path_without_root)
    return with_root == p or without_root == p
