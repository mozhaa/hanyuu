from abc import ABC, abstractmethod
from typing import Optional

from hanyuu.database.main.models import QItemSource


class SourceFindingStrategy(ABC):
    @abstractmethod
    async def find_source(self, qitem_id: int) -> Optional[QItemSource]: ...
