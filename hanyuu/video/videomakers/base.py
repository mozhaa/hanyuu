from abc import ABC, abstractmethod


class VideoMakerBase(ABC):
    @abstractmethod
    async def create_video(self, timing_id: int, difficulty_id: int) -> str: ...
