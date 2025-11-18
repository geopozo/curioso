"""."""

import glob
import os
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from curioso import _utils

PKG_BINARIES = [
    "apt",
    "apt-get",
    "dnf",
    "yum",
    "zypper",
    "pacman",
    "apk",
    "xbps-install",
    "emerge",
    "nix",
    "nix-env",
    "swupd",
    "eopkg",
    "urpmi",
]


def _detect_sandbox() -> dict[str, bool]:
    snap = bool(os.environ.get("SNAP") or os.environ.get("SNAP_NAME"))
    flatpak = bool(
        os.environ.get("FLATPAK_ID")
        or os.environ.get("FLATPAK_SESSION_HELPER")
        or Path("/.flatpak-info").exists(),
    )
    return {"snap": snap, "flatpak": flatpak}


def _choose_package_manager() -> dict[str, list[str]]:
    available_bins = _utils.which_any(PKG_BINARIES)
    available_names = [str(Path(p).resolve()) for p in available_bins]

    if available_bins:
        return {"packages": available_bins, "available": available_names}

    raise FileNotFoundError("No package manager found")


def _find_dynamic_linkers() -> list[str]:
    patterns = [
        "/lib*/ld-linux*.so*",
        "/lib/*/ld-linux*.so*",
        "/lib*/ld-*.so*",
        "/lib/*/ld-*.so*",
        "/lib*/ld-musl-*.so*",
        "/lib/*/ld-musl-*.so*",
    ]

    found = {
        p
        for pat in patterns
        for p in glob.glob(pat)  # noqa: PTH207
        if Path(p).is_file() and os.access(p, os.X_OK)
    }

    mach = platform.machine()
    (sorted_list := list(found)).sort(
        key=lambda x: (0 if mach and mach in x else 1, len(x)),
    )

    return sorted_list


@dataclass
class LibcInfo:
    """Libc detection info."""

    family: str = "unknown"
    version: str | None = None
    selected_linker: str | None = None
    detector: str | None = None

    def __json__(self) -> dict[str, str | None]:
        """Convert to json."""
        return {
            "family": self.family,
            "version": self.version,
            "selected_linker": self.selected_linker,
            "detector": self.detector,
        }


async def _detect_libc() -> LibcInfo:
    linkers = _find_dynamic_linkers()
    sel_linker = linkers[0] if linkers else None
    fam, ver = platform.libc_ver()

    if fam == "glibc" or not sel_linker:
        return LibcInfo(
            family=fam,
            version=ver,
            selected_linker=sel_linker,
            detector="platform.libc_ver",
        )
    else:
        out, err, _ = await _utils.run_cmd([sel_linker, "--version"])
        combined = (out.decode() + "\n" + err.decode()).strip().lower()
        version = next(
            line.strip().split()[1]
            for line in combined.splitlines()
            if line.startswith("version")
        )
        return LibcInfo(
            family="musl",
            version=version,
            selected_linker=sel_linker,
            detector="ld--version",
        )


@dataclass
class LddInfo:
    """Ldd detection info."""

    method: str | None = None
    cmd_template: list[str] | None = None
    executable: str | None = None

    def __json__(self) -> dict[str, str | list[str] | None]:
        """Convert to json."""
        return {
            "method": self.method,
            "cmd_template": self.cmd_template,
            "executable": self.executable,
        }

    @classmethod
    def equivalent(cls, libc_family: str, linker: str | None) -> "LddInfo":
        """Stub."""
        if libc_family == "glibc" and linker:
            return cls(
                method="glibc-ld--list",
                cmd_template=[linker, "--list", "{target}"],
            )

        if libc_family == "musl" and linker:
            return cls(
                method="musl-ld-argv0-ldd",
                cmd_template=["ldd", "{target}"],
                executable=linker,
            )

        return cls()


@dataclass()
class ReportInfo:
    """System report metadata and compatibility info."""

    os: str | None = None
    kernel: str | None = None
    supported: bool = False
    machines: str | None = None
    sandbox: dict[str, bool] | None = None
    distro: dict[str, Any] | None = None
    package_manager: dict[str, Any] | None = None
    libc: LibcInfo | None = None
    ldd_equivalent: LddInfo | None = None

    def __json__(self) -> dict[str, Any]:
        """Convert to json."""
        return {
            "os": self.os,
            "kernel": self.kernel,
            "machines": self.machines,
            "supported": self.supported,
            "sandbox": self.sandbox,
            "distro": self.distro,
            "package_manager": self.package_manager,
            "libc": self.libc,
            "ldd_equivalent": self.ldd_equivalent,
        }


async def probe() -> ReportInfo:
    """Detect system configuration and runtime environment."""
    os_name = platform.system()
    supported = os_name.lower() == "linux"
    report = ReportInfo(
        os=os_name,
        kernel=platform.release(),
        supported=supported,
        machines=platform.machine(),
    )

    if not supported:
        return report

    osr = platform.freedesktop_os_release()
    report.distro = {k.lower(): v for k, v in osr.items()}
    report.sandbox = _detect_sandbox()
    report.package_manager = _choose_package_manager()
    report.libc = await _detect_libc()
    report.ldd_equivalent = LddInfo.equivalent(
        report.libc.family,
        report.libc.selected_linker,
    )

    return report
