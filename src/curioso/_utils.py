import shutil
import subprocess


def run_cmd(
    argv: list[str],
    timeout: int = 6,
    executable: str | None = None,
) -> tuple[int, str, str]:
    try:
        p = subprocess.run(  # noqa: S603, UP022
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=timeout,
            executable=executable,
        )
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except FileNotFoundError:
        return 127, "", f"{executable or argv[0]}: not found"
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"


def which_any(names: list[str]) -> list[str]:
    return [n for n in names if shutil.which(n)]
