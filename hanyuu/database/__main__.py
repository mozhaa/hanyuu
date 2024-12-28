import argparse
import asyncio

from .main.connection import get_engine


async def main():
    parser = argparse.ArgumentParser(
        "Database Tool", "Tool for simple database actions"
    )
    parser.add_argument("--drop-tables", action="store_true")
    args = parser.parse_args()

    engine = await get_engine()
    if args.drop_tables:
        await engine.drop_tables()
        print("Successfully dropped tables.")


if __name__ == "__main__":
    asyncio.run(main())
