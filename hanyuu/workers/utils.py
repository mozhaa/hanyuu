import argparse
import asyncio
import time
from typing import Awaitable, Callable, List, Optional

import aiofiles
from filelock import FileLock


class FiledList:
    def __init__(self, fp: str, readonly: bool = False) -> None:
        self.fp = fp
        self.lock = FileLock(fp + ".lock")
        self.readonly = readonly

    async def __aenter__(self) -> List[int]:
        self.lock.acquire()
        async with aiofiles.open(self.fp, "a+") as f:
            await f.seek(0, 0)
            self.list = [int(x.strip()) for x in await f.readlines()]
        return self.list

    async def __aexit__(self, *args, **kwargs) -> None:
        if not self.readonly:
            print("writing", self.list)
            async with aiofiles.open(self.fp, "w+") as f:
                await f.writelines([f"{x}\n" for x in self.list])
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
