from dataclasses import dataclass, field
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Callable
from uuid import uuid1

import aiohttp
import ffmpeg

from hanyuu.config import getenv
from hanyuu.database.connection import Database, get_db
from hanyuu.database.models import Category, QItemDifficulty, QItemSourceTiming
from hanyuu.webparse.utils import default_headers

from .base import VideoMakerBase


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


@dataclass
class VideoMakerConfig:
    countdowns_dir: str  # directory with countdowns videos
    difficulty_func: Callable[[int], str]  # difficulty |-> countdown file name
    loudnorm: float = -18
    acodec: str = "aac"
    vcodec: str = "hevc"
    fps: int = 24
    vtiming: VideoTimings = field(default_factory=VideoTimings)
    vpos: VideoPositioning = field(default_factory=VideoPositioning)


class VideoMaker(VideoMakerBase):
    def __init__(self, **kwargs) -> None:
        self.c = VideoMakerConfig(**kwargs)
        self.db: Database = None

    async def create_video(self, timing_id: int, difficulty_id: int) -> str:
        if self.db is None:
            self.db = await get_db("video_maker")
        async with self.db.async_session() as session:
            difficulty = await session.get(QItemDifficulty, difficulty_id)
            timing = await session.get(QItemSourceTiming, timing_id)
            source = await timing.awaitable_attrs.qitem_source
            qitem = await source.awaitable_attrs.qitem
            anime = await qitem.awaitable_attrs.anime
            local_file = await source.awaitable_attrs.local_file

            title = anime.shiki_title_ro
            poster_url = anime.shiki_poster_url
            category = qitem.category
            number = qitem.number
            source_fp = local_file.name
            reveal_start = timing.reveal_start
            guess_start = timing.guess_start

        category_short = {
            Category.Opening: "OP",
            Category.Ending: "ED",
        }[category]
        text = f"{title} {category_short} {number}"

        countdown_fp = (Path(self.c.countdowns_dir) / self.c.difficulty_func(difficulty)).resolve()

        font_fp = (Path(getenv("static_dir")) / "ttf" / "tccm.ttf").resolve()

        output_dir = Path(getenv("resources_dir")) / "videos" / str(uuid1())
        output_fp = output_dir / "video.mp4"
        output_dir.mkdir(parents=True)

        poster_box_fp = Path(getenv("static_dir")) / "png" / "poster_box.png"

        poster_file = NamedTemporaryFile("w+b", delete_on_close=False)
        async with aiohttp.ClientSession(headers=default_headers) as session:
            async with session.get(poster_url) as response:
                poster_file.write(await response.read())
        poster_file.close()

        vt = self.c.vtiming
        vp = self.c.vpos

        countdown = ffmpeg.input(str(countdown_fp.resolve()))
        reveal = ffmpeg.input(source_fp, ss=reveal_start, t=vt.rD)
        guess = ffmpeg.input(source_fp, ss=guess_start, t=vt.gD)
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
            .filter("adelay", delays=vt.ad, all=1)
            .filter("loudnorm", I=self.c.loudnorm)
            .filter("apad", pad_dur=vt.cD - vt.ad - vt.gD)
        )

        reveal_audio = (
            reveal.audio.filter("afade", t="out", st=vt.rst, d=vt.rfo)
            .filter("afade", t="in", st=0, d=vt.rfi)
            .filter("loudnorm", I=self.c.loudnorm)
        )

        result = ffmpeg.concat(countdown_video, guess_audio, reveal_video, reveal_audio, n=2, v=1, a=1)
        output = ffmpeg.output(
            result,
            str(output_fp.resolve()),
            acodec=self.c.acodec,
            vcodec=self.c.vcodec,
            r=self.c.fps,
        )
        output.run()
        return output_fp
