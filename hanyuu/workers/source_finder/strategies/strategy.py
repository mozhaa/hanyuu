from abc import ABC, abstractmethod
from typing import Callable, Optional, Awaitable


class SourceFindingStrategy(ABC):
    name: str

    @abstractmethod
    async def run(self, qitem_id: int) -> None:
        """
        Find source for QItem and add to database.

        If find process and download process can be easily divided,
        strategy should not download source in run(). In that case,
        there should be downloading strategy, that is able to download this source.

        Otherwise, when you have to start downloading for finding,
        strategy can download source, and must set local_fp in QItemSource.
        """
        pass


class SourceDownloadingStrategy(ABC):
    @abstractmethod
    async def is_valid(self, qitem_source_id: int) -> Optional[Callable[[], Awaitable[None]]]:
        """
        Check if this source could be downloaded using this strategy.

        If yes, return run() function, that downloads source;
        otherwise, return None
        """
        pass
