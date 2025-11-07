import asyncio
import shutil
import subprocess


async def run_cmd(
    commands: list[str],
    executable: str | None = None,
) -> tuple[bytes, bytes, int | None]:
    proc = await asyncio.create_subprocess_exec(
        *commands,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        executable=executable,
    )
    stdout, stderr = await proc.communicate()
    return stdout, stderr, proc.returncode


def which_any(names: list[str]) -> list[str]:
    return [n for n in names if shutil.which(n)]
