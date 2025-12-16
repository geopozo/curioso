"""."""

from __future__ import annotations

import glob
import os
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from curioso import _utils

if TYPE_CHECKING:
    from typing import Any


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

PATTERNS = [
    "/lib*/ld-linux*.so*",
    "/lib/*/ld-linux*.so*",
    "/lib*/ld-*.so*",
    "/lib/*/ld-*.so*",
    "/lib*/ld-musl-*.so*",
    "/lib/*/ld-musl-*.so*",
]


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

    @staticmethod
    def find_dynamic_linkers() -> str | None:
        """Find dynamic linkers in standard locations."""
        if not (
            linkers := list(
                {
                    file
                    for pattern in PATTERNS
                    for file in glob.glob(pattern)  # noqa: PTH207
                    if Path(file).is_file() and os.access(file, os.X_OK)
                },
            )
        ):
            return None

        linkers.sort(
            key=lambda linker: platform.machine() not in linker,  # True becomes 0
        )

        return linkers[0]

    @classmethod
    async def detect_libc(cls) -> LibcInfo:
        """Detect libc family and version."""
        linker_present = cls.find_dynamic_linkers()
        libc_family, libc_version = platform.libc_ver()

        if libc_family == "glibc" or not linker_present:
            return cls(
                family=libc_family,
                version=libc_version,
                selected_linker=linker_present,
                detector="platform.libc_ver" if linker_present else "unknown",
            )
        else:
            out, err, _ = await _utils.run_cmd([linker_present, "--version"])
            combined = (out.decode() + "\n" + err.decode()).strip().lower()
            libc_version = next(
                line.strip().split()[1]
                for line in combined.splitlines()
                if line.startswith("version")
            )
            return cls(
                family="musl",
                version=libc_version,
                selected_linker=linker_present,
                detector="ld --version",
            )


@dataclass
class LddInfo:
    """Ldd detection info."""

    method: str | None = None
    argv: list[str] | None = None
    executable: str | None = None

    def __json__(self) -> dict[str, str | list[str] | None]:
        """Convert to json."""
        return {
            "method": self.method,
            "argv": self.argv,
            "executable": self.executable,
        }

    @classmethod
    def infer(cls, libc_family: str, linker: str | None) -> LddInfo:
        """Detect ldd equivalent command."""
        if libc_family == "glibc" and linker:
            return cls(
                method="glibc-ld--list",
                argv=[linker, "--list", "{target}"],
                executable=linker,
            )

        if libc_family == "musl" and linker:
            return cls(
                method="musl-ld-argv0-ldd",
                argv=["ldd", "{target}"],
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
    ldd_info: LddInfo | None = None

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
            "ldd": self.ldd_info,
        }

    @staticmethod
    def detect_sandbox() -> dict[str, bool]:
        """Detect sandbox environment."""
        snap = bool(os.environ.get("SNAP") or os.environ.get("SNAP_NAME"))
        flatpak = bool(
            os.environ.get("FLATPAK_ID")
            or os.environ.get("FLATPAK_SESSION_HELPER")
            or Path("/.flatpak-info").exists(),
        )
        return {"snap": snap, "flatpak": flatpak}

    @staticmethod
    def choose_package_manager() -> dict[str, list[str]]:
        """Choose available package manager."""
        available_bins = _utils.which_any(PKG_BINARIES)
        available_names = [str(Path(p).resolve()) for p in available_bins]

        if available_bins:
            return {"packages": available_bins, "available": available_names}

        raise FileNotFoundError("No package manager found")

    @classmethod
    async def probe(cls) -> ReportInfo:
        """Detect system configuration and runtime environment."""
        os_name = platform.system()
        supported = os_name.lower() == "linux"
        report = cls(
            os=os_name,
            kernel=platform.release(),
            supported=supported,
            machines=platform.machine(),
        )

        if not supported:
            return report

        osr = platform.freedesktop_os_release()
        report.distro = {
            "id": osr.get("ID"),
            "name": osr.get("NAME"),
            "version_id": osr.get("VERSION_ID"),
            "pretty_name": osr.get("PRETTY_NAME"),
            "id_like": osr.get("ID_LIKE"),
        }
        report.sandbox = cls.detect_sandbox()
        report.package_manager = cls.choose_package_manager()
        report.libc = await LibcInfo.detect_libc()
        report.ldd_info = LddInfo.infer(
            report.libc.family,
            report.libc.selected_linker,
        )

        return report
