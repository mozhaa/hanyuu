from abc import ABC, abstractmethod
from typing import Awaitable, Callable, Optional, Tuple


class SourceDownloadStrategy(ABC):
    name: str

    def __init__(self, name: str) -> None:
        self.name = name

    @abstractmethod
    async def check(
        self, qitem_source_id: int, download_dir: str
    ) -> Tuple[bool, Optional[Callable[[], Awaitable[None]]]]:
        """
        Check if source can be downloaded with this strategy,
        and, if yes, return async function, that does this.
        """
        pass
