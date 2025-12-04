import asyncio
import json

from curioso import _utils
from curioso.app import ReportInfo

# ruff: noqa: T201 allow print in CLI


async def main():
    data = await ReportInfo.probe()
    print(
        json.dumps(
            data,
            indent=2,
            sort_keys=False,
            cls=_utils.AutoEncoder,
        ),
    )


def run_cli():
    asyncio.run(main())
