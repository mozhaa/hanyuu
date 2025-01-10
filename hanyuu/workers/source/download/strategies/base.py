from abc import ABC, abstractmethod

from hanyuu.database.main.models import QItemSource


class SourceDownloadStrategy(ABC):
    name: str

    def __init__(self, name: str) -> None:
        self.name = name

    @abstractmethod
    async def run(self, qitem_source: QItemSource) -> None:
        """
        Try to download source with this strategy.
        Possible outcomes:

        - source is invalid (raises InvalidSource)

        - strategy temprorary failed, f.e. no internet access (raises TemporaryFailure)

        - strategy successed
        """
        pass


class InvalidSource(Exception):
    pass


class TemporaryFailure(Exception):
    pass
