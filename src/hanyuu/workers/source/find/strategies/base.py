from abc import ABC, abstractmethod


class SourceFindStrategy(ABC):
    name: str

    def __init__(self, name: str) -> None:
        self.name = name

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
