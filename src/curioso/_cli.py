import asyncio
import json

from curioso import app

# ruff: noqa: T201 allow print in CLI


async def main():
    data = await app.probe()
    print(json.dumps(data, indent=2, sort_keys=False))


def run_cli():
    asyncio.run(main())
