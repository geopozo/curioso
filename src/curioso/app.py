"""."""

import glob
import os
import platform
import re
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


def _choose_package_manager() -> dict[str, Any]:
    available_bins = _utils.which_any(PKG_BINARIES)
    available_names = [Path(p).resolve() for p in available_bins]

    if available_bins:
        return {"packages": available_bins, "available": available_names}

    raise FileNotFoundError("No package manager found")


# step 5: libc + linker
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
    """Stub."""

    family: str = "unknown"
    version: str | None = None
    selected_linker: str = ""
    detector: str | None = None

    def __json__(self):
        """Convert to json."""
        return {
            "family": self.family,
            "version": self.version,
            "selected_linker": self.selected_linker,
            "detector": self.detector,
        }


async def _detect_libc() -> LibcInfo:
    linkers = _find_dynamic_linkers()
    sel = linkers[0] if linkers else None

    def parse_glib_ver(text: str) -> str:
        m = re.search(
            r"(?:glibc|gnu c library)[^\d]*(\d+\.\d+(?:\.\d+)?)",
            text,
            re.IGNORECASE,
        )
        return m.group(1) if m else ""

    def parse_musl_ver(text: str) -> str:
        m = re.search(
            r"musl[^0-9]*([0-9]+\.[0-9]+(?:\.[0-9]+)?)",
            text,
            re.IGNORECASE,
        )
        return m.group(1) if m else ""

    if sel:
        out, err, _ = await _utils.run_cmd([sel, "---version"])
        combined = (out.decode() + "\n" + err.decode()).strip()

        if "musl" in combined.lower():
            return LibcInfo(
                family="musl",
                version=parse_musl_ver(combined),
                selected_linker=sel,
                detector="ld--version",
            )
        if (
            "glibc" in combined.lower()
            or "gnu c library" in combined.lower()
            or "ld-linux" in Path(sel).name
        ):
            return LibcInfo(
                family="glibc",
                version=parse_glib_ver(combined),
                selected_linker=sel,
                detector="ld--version",
            )

        out, err, _ = await _utils.run_cmd(["ldd", "--version"], executable=sel)
        combined = (out.decode() + "\n" + err.decode()).strip()
        if "musl" in combined.lower():
            return LibcInfo(
                family="musl",
                version=parse_musl_ver(combined),
                selected_linker=sel,
                detector="ldd-mode",
            )

    fam, ver = platform.libc_ver()
    return LibcInfo(
        family=fam,
        version=ver,
        selected_linker=sel or "",
        detector="platform.libc_ver",
    )


@dataclass
class LddInfo:
    """Stub."""

    method: str = "unknown"
    cmd_template: list[str] | None = None
    executable: str | None = None

    def __json__(self):
        """Convert to json."""
        return {
            "method": self.method,
            "cmd_template": self.cmd_template,
            "executable": self.executable,
        }


# Step 6: determine "ldd" via the linker
def _ldd_equivalent(libc_family: str, linker: str) -> LddInfo:
    if not linker:
        return LddInfo()

    if libc_family == "glibc":
        return LddInfo(
            method="glibc-ld--list",
            cmd_template=[linker, "--list", "{target}"],
        )

    if libc_family == "musl":
        return LddInfo(
            method="musl-ld-argv0-ldd",
            cmd_template=["ldd", "{target}"],
            executable=linker,
        )

    return LddInfo()


@dataclass
class ReportInfo:
    """Stub."""

    os: str = ""
    kernel: str = ""
    supported: bool = False
    machines: str = ""
    snap: bool = False
    flatpak: bool = False
    distro: dict[str, Any] | None = None
    package_manager: dict[str, Any] | None = None
    libc: LibcInfo | None = None
    ldd_equivalent: LddInfo | None = None

    def __json__(self):
        """Convert to json."""
        return {
            "os": self.os,
            "kernel": self.kernel,
            "supported": self.supported,
            "snap": self.snap,
            "flatpak": self.flatpak,
            "distro": self.distro,
            "package_manager": self.package_manager,
            "libc": self.libc,
            "ldd_equivalent": self.ldd_equivalent,
        }


# orchestrator
async def probe() -> ReportInfo:
    """Stub."""
    os_name = platform.system()
    report = ReportInfo(
        os=os_name,
        kernel=platform.release(),
        supported=os_name.lower() == "linux",
        machines=platform.machine(),
    )

    if not report.supported:
        return report

    sb = _detect_sandbox()
    report.snap = sb.get("snap", False)
    report.flatpak = sb.get("flatpak", False)

    osr = platform.freedesktop_os_release()
    report.distro = {
        "id": osr.get("ID"),
        "name": osr.get("NAME"),
        "version_id": osr.get("VERSION_ID"),
        "pretty_name": osr.get("PRETTY_NAME"),
        "id_like": osr.get("ID_LIKE"),
    }
    report.libc = await _detect_libc()
    report.ldd_equivalent = _ldd_equivalent(
        report.libc.family,
        report.libc.selected_linker,
    )

    return report
