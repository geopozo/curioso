import asyncio
import json
import shutil
import subprocess


class AutoEncoder(json.JSONEncoder):
    def default(self, o):
        if hasattr(o, "__json__"):
            return o.__json__()
        return super().default(o)


async def run_cmd(
    commands: list[str],
    executable: str | None = None,
) -> tuple[bytes, bytes, int]:
    proc = await asyncio.create_subprocess_exec(
        *commands,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        executable=executable,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode is None:
        raise RuntimeError("Impossible to reach this code.")

    return stdout, stderr, proc.returncode


def which_any(names: list[str]) -> list[str]:
    return [n2 for n in names if (n2 := shutil.which(n))]
