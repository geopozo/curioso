import asyncio

from curioso import app


async def main():
    data = await app.probe()
    data.to_json(pretty=True)


def run_cli():
    asyncio.run(main())
