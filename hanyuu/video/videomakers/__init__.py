from typing import List

from .base import VideoMakerBase
from .classic import VideoMaker
from .onesec import OneSecVideoMaker

styles: List[VideoMakerBase] = [
    VideoMaker("classic"),
    OneSecVideoMaker("onesec"),
]
