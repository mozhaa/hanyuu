import ffmpeg
from typing import Iterable
from tempfile import NamedTemporaryFile
from pathlib import Path


def cat(videos: Iterable[str], output_fp: str) -> None:
    tf = NamedTemporaryFile("w+", suffix=".txt", delete_on_close=False)
    tf.writelines([f"file '{Path(fp).resolve()}'\n" for fp in videos])
    tf.close()
    tf_path = tf.name
    try:
        command = ffmpeg.output(ffmpeg.input(tf_path, f="concat", safe=0), output_fp, c="copy")
        print(command.compile())
        command.run()
    finally:
        Path(tf_path).unlink()
