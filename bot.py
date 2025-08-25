# bot.py  (à la racine du repo)
from __future__ import annotations
import asyncio
from cli import parse_cli
from engine.app import run_app

async def main() -> None:
    args = parse_cli()
    await run_app(args)

if __name__ == "__main__":
    asyncio.run(main())