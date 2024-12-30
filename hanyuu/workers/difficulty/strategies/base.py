from abc import ABC, abstractmethod


class DifficultyStrategy(ABC):
    name: str

    def __init__(self, name: str) -> None:
        self.name = name

    @abstractmethod
    async def run(self, qitem_id: int) -> None:
        """
        Predict QItem difficulty, and add to database.
        """
        pass
