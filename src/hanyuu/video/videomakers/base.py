from abc import ABC, abstractmethod


class VideoMakerBase(ABC):
    name: str

    def __init__(self, name: str) -> None:
        self.name = name

    @abstractmethod
    async def create_video(self, timing_id: int, difficulty_id: int, output_dir: str) -> None:
        """
        Create video from given timing and difficulty, and output to output_dir.
        """
        pass
