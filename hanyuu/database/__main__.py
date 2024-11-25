import argparse
import asyncio

from .connection import get_db


async def main():
    parser = argparse.ArgumentParser(
        "Database Tool", "Tool for simple database actions"
    )
    parser.add_argument("--drop-tables", action="store_true")
    args = parser.parse_args()

    db = await get_db("database_tool")
    if args.drop_tables:
        await db.drop_tables()
        print("Successfully dropped tables.")


if __name__ == "__main__":
    asyncio.run(main())
