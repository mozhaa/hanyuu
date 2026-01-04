import argparse
import asyncio

from . import start

if __name__ == "__main__":
    argparser = argparse.ArgumentParser(
        "QItems Parser",
        usage="Periodically scan through hanyuu.database, and parse QItems from AniDB for animes.",
    )
    argparser.add_argument(
        "-i",
        "--interval",
        type=int,
        default=30,
        help="interval time between anidb requests, in seconds",
    )
    args = argparser.parse_args()
    asyncio.run(start(args))
