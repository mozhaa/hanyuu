from abc import ABC, abstractmethod


class DifficultyStrategy(ABC):
    name: str

    @abstractmethod
    async def run(self, qitem_id: int) -> None:
        """
        Predict QItem difficulty, and add to database.
        """
        pass
