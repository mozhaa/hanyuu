from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Callable, Optional

import aiohttp
import ffmpeg

from hanyuu.config import getenv
from hanyuu.database.main.connection import get_engine
from hanyuu.database.main.models import Category, QItemDifficulty, QItemSourceTiming
from hanyuu.webparse.utils import default_headers

from .base import VideoMakerBase

countdowns_dir = Path(getenv("static_dir")) / "video" / "countdowns"


def difficulty_func(value: int) -> str:
    return ["very easy.mkv", "easy.mkv", "medium.mkv", "hard.mkv", "very hard.mkv"][min(value // 20, 4)]


@dataclass
class VideoTimings:
    gD: float = 10  # guess duration
    rD: float = 8  # reveal duration

    ad: float = 1  # guess audio delay
    cdi: float = 0.5  # countdown counting delay (from audio start)
    cdo: float = 0.3  # countdown end delay (pause after 0.0)
    cfo: float = 1  # countdown video fade out

    gfo: float = 1.5  # guess audio fade out
    gfi: float = 0  # guess audio fade in
    rfo: float = 2  # reveal fade out
    rfi: float = 0.5  # reveal fade in

    def __post_init__(self) -> None:
        self.gst = self.gD - self.gfo  # start of guess fade out
        self.rst = self.rD - self.rfo  # start of reveal fade out
        self.cD = self.gD + self.ad + self.cdi + self.cdo  # countdown video duration


@dataclass
class VideoPositioning:
    poster_w: int = 252  # poster width
    poster_h: int = 336  # poster height
    poster_x: int = 70  # poster x coordinate
    poster_y: int = 360  # poster y coordinate
    text_x: int = 115  # text x coordinate
    text_y: int = 620  # text y coordinate


class VideoMaker(VideoMakerBase):
    def __init__(
        self,
        name: str,
        countdowns_dir: str = countdowns_dir,  # directory with countdowns videos
        difficulty_func: Callable[[int], str] = difficulty_func,  # difficulty |-> countdown file name
        loudnorm: float = -18,
        acodec: str = "aac",
        vcodec: str = "hevc",
        fps: int = 30,
        vtiming: Optional[VideoTimings] = None,
        vpos: Optional[VideoPositioning] = None,
    ) -> None:
        super().__init__(name)
        self.countdowns_dir = countdowns_dir
        self.difficulty_func = difficulty_func
        self.loudnorm = loudnorm
        self.acodec = acodec
        self.vcodec = vcodec
        self.fps = fps
        self.vtiming = vtiming if vtiming is not None else VideoTimings()
        self.vpos = vpos if vpos is not None else VideoPositioning()

    async def create_video(self, timing_id: int, difficulty_id: int, output_fp: str) -> None:
        engine = await get_engine()
        async with engine.async_session() as session:
            difficulty = await session.get(QItemDifficulty, difficulty_id)
            timing = await session.get(QItemSourceTiming, timing_id)
            source = await timing.awaitable_attrs.qitem_source
            qitem = await source.awaitable_attrs.qitem
            anime = await qitem.awaitable_attrs.anime

        category_short = {
            Category.Opening: "OP",
            Category.Ending: "ED",
        }[qitem.category]
        text = f"{anime.shiki_title_ro} {category_short} {qitem.number}"

        countdown_fp = (Path(self.countdowns_dir) / self.difficulty_func(difficulty.value)).resolve()

        font_fp = (Path(getenv("static_dir")) / "ttf" / "tccm.ttf").resolve()

        Path(output_fp).parent.mkdir(parents=True, exist_ok=True)

        poster_box_fp = Path(getenv("static_dir")) / "png" / "poster_box.png"

        poster_file = NamedTemporaryFile("w+b", delete_on_close=False)
        async with aiohttp.ClientSession(headers=default_headers) as session:
            async with session.get(anime.shiki_poster_url) as response:
                poster_file.write(await response.read())
        poster_file.close()

        vt = self.vtiming
        vp = self.vpos

        countdown = ffmpeg.input(str(countdown_fp.resolve()))
        reveal = ffmpeg.input(source.local_fp, ss=timing.reveal_start, t=vt.rD)
        guess = ffmpeg.input(source.local_fp, ss=timing.guess_start, t=vt.gD)
        poster = ffmpeg.input(poster_file.name, loop=1, t=vt.rD)
        poster_box = ffmpeg.input(poster_box_fp.resolve(), loop=1, t=vt.rD)

        poster_video = poster.video.filter("scale", vp.poster_w, vp.poster_h)
        poster_video = ffmpeg.overlay(poster_box, poster_video)

        reveal_video = (
            reveal.video.filter("scale", 1280, 720, force_original_aspect_ratio="decrease")
            .filter("pad", 1280, 720, "(ow-iw)/2", "(oh-ih)/2")
            .filter("setsar", 1)
        )
        reveal_video = ffmpeg.overlay(reveal_video, poster_video, x=vp.poster_x, y=vp.poster_y)
        reveal_video = (
            reveal_video.drawtext(
                text,
                x=vp.text_x,
                y=vp.text_y,
                fontfile=font_fp,
                fontsize=64,
                fontcolor="white",
                shadowx=4,
                shadowy=4,
                shadowcolor="#000000cc",
                borderw=1.5,
                bordercolor="black",
            )
            .filter("fade", t="in", st=0, d=vt.rfi)
            .filter("fade", t="out", st=vt.rD, d=(vt.rD - vt.rfo))
        )

        countdown_video = countdown.video.filter("fade", t="in", st=0, d=vt.ad).filter(
            "fade", t="out", st=(vt.cD - vt.cfo), d=vt.cfo
        )

        guess_audio = (
            guess.audio.filter("afade", t="out", st=vt.gst, d=vt.gfo)
            .filter("afade", t="in", st=0, d=vt.gfi)
            .filter("adelay", delays=vt.ad * 1000, all=1)
            .filter("loudnorm", I=self.loudnorm)
            .filter("apad", pad_dur=vt.cD - vt.ad - vt.gD)
        )

        reveal_audio = (
            reveal.audio.filter("afade", t="out", st=vt.rst, d=vt.rfo)
            .filter("afade", t="in", st=0, d=vt.rfi)
            .filter("loudnorm", I=self.loudnorm)
        )

        result = ffmpeg.concat(countdown_video, guess_audio, reveal_video, reveal_audio, n=2, v=1, a=1)
        output = ffmpeg.output(
            result,
            output_fp,
            acodec=self.acodec,
            vcodec=self.vcodec,
            r=self.fps,
            nostats=None,
            loglevel="error",
        )

        output.run()
