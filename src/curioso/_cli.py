import asyncio

from curioso import app


def run_cli():
    asyncio.run(app.probe())
