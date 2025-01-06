from typing import List

from .base import VideoMakerBase
from .classic import VideoMaker

styles: List[VideoMakerBase] = [VideoMaker("classic")]
