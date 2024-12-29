from typing import List

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
