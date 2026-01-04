from abc import ABC, abstractmethod


class TimingStrategy(ABC):
    name: str

    def __init__(self, name: str) -> None:
        self.name = name

    @abstractmethod
    async def run(self, qitem_source_id: int) -> None:
        """
        Predict source timings, and add to database.
        """
        pass
