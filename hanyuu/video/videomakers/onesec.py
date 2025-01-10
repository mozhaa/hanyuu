from pathlib import Path

import ffmpeg

from hanyuu.config import getenv
from hanyuu.database.main.connection import get_engine
from hanyuu.database.main.models import QItemSourceTiming

from .base import VideoMakerBase

countdown_fp = Path(getenv("static_dir")) / "video" / "one_sec_guess_265.mp4"


class OneSecVideoMaker(VideoMakerBase):
    async def create_video(self, timing_id: int, difficulty_id: int, output_fp: str) -> None:
        engine = await get_engine()
        async with engine.async_session() as session:
            timing = await session.get(QItemSourceTiming, timing_id)
            source = await timing.awaitable_attrs.qitem_source
            qitem = await source.awaitable_attrs.qitem

        font_fp = (Path(getenv("static_dir")) / "ttf" / "VOGUE.TTF").resolve()
        input_fp = Path(source.local_fp).resolve()
        output_fp = Path(output_fp).resolve()
        output_fp.parent.mkdir(parents=True, exist_ok=True)

        countdown = ffmpeg.input(str(countdown_fp.resolve()))
        guess = ffmpeg.input(str(input_fp), ss=timing.guess_start, t=1)
        reveal = ffmpeg.input(str(input_fp), ss=timing.reveal_start, t=5)

        reveal_video = (
            reveal.video.filter("scale", 1280, 720, force_original_aspect_ratio="decrease")
            .filter("pad", 1280, 720, "(ow-iw)/2", "(oh-ih)/2")
            .filter("setsar", 1)
        )

        reveal_video = (
            reveal_video.filter("fade", t="in", st=0, d=0.5)
            .filter("fade", t="out", st=4, d=1)
            .drawtext(
                qitem.number,
                x="(1280-tw)/2",
                y="(720-th)/2",
                fontfile=str(font_fp),
                fontsize=512,
                fontcolor="white",
                borderw=16,
                bordercolor="black",
            )
        )

        ga_norm = (
            guess.audio.filter("aformat", channel_layouts="stereo|mono")
            .filter("loudnorm", I=-18)
            .filter_multi_output("asplit")
        )

        guess_audio_1 = ga_norm[0].filter("adelay", delays=3 * 1000, all=1)
        guess_audio_2 = ga_norm[1].filter("adelay", delays=3 * 1000, all=1).filter("apad", pad_dur=5)
        guess_audio = ffmpeg.concat(guess_audio_1, guess_audio_2, n=2, v=0, a=1)

        reveal_audio = (
            reveal.audio.filter("loudnorm", I=-18)
            .filter("afade", t="out", st=4, d=1)
            .filter("afade", t="in", st=0, d=0.5)
        )

        result = ffmpeg.concat(countdown.video, guess_audio, reveal_video, reveal_audio, n=2, v=1, a=1)
        output = ffmpeg.output(
            result,
            filename=output_fp,
            acodec="aac",
            vcodec="libx264",
            preset="faster",
        )

        try:
            output.run()
        except ffmpeg.Error as e:
            if e.stdout is not None:
                print("stdout:", e.stdout.decode("utf8"))
            if e.stderr is not None:
                print("stderr:", e.stderr.decode("utf8"))
            raise e
