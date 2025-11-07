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


@dataclass
class OsInfo:
    """Stub."""

    os: str = ""
    kernel: str = ""
    platform: str = ""
    machines: str = ""


# step 1: OS
def detect_os() -> OsInfo:
    """Stub."""
    return OsInfo(
        os=platform.system(),
        kernel=platform.release(),
        platform=platform.platform(),
        machines=platform.machine(),
    )


# step 2: Snap / Flatpak
def detect_sandbox() -> dict[str, bool]:
    """Stub."""
    snap = bool(os.environ.get("SNAP") or os.environ.get("SNAP_NAME"))
    flatpak = bool(
        os.environ.get("FLATPAK_ID")
        or os.environ.get("FLATPAK_SESSION_HELPER")
        or Path("/.flatpak-info").exists(),
    )
    return {"snap": snap, "flatpak": flatpak}


# step 3: Distro:
def parse_os_release() -> dict[str, str]:
    """Stub."""
    for _p in ("/etc/os-release", "/usr/lib/os-release"):
        if (p := Path(_p)).exists():
            lines = p.read_text(errors="ignore").splitlines()
            # Process into dict this text format:
            # KEY="VALUE"  # noqa: ERA001
            # KEY2="VALUE2"  # noqa: ERA001
            # ...
            return {k: v[1:-2] for line in lines for k, v in line.split("=")}
    raise FileNotFoundError("")


# step 4: Package manager
def choose_package_manager() -> dict[str, Any]:
    """Stub."""
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


async def detect_libc() -> LibcInfo:
    """Stub."""
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


# Step 6: determine "ldd" via the linker
def ldd_equivalent(libc_family: str, linker: str) -> LddInfo:
    """Stub."""
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


# orchestrator
async def collect_min_report() -> dict[str, Any]:
    """Stub."""
    os_info = detect_os()
    report: dict[str, Any] = {
        "os": os_info.os,
        "kernel": os_info.kernel,
        "supported": os_info.os.lower() == "linux",
        "snap": False,
        "flatpak": False,
        "distro": None,
        "package_manager": None,
        "libc": None,
        "ldd_equivalent": None,
    }

    if not report["supported"]:
        return report

    # Snap/Flatpak
    sb = detect_sandbox()
    report["snap"] = sb.get("snap")
    report["flatpak"] = sb.get("flatpak")

    # Distro
    osr = parse_os_release()
    distro = {
        "id": osr.get("ID"),
        "name": osr.get("NAME"),
        "version_id": osr.get("VERSION_ID"),
        "pretty_name": osr.get("PRETTY_NAME"),
        "id_like": osr.get("ID_LIKE"),
    }
    report["distro"] = distro

    # Package manager
    pm = choose_package_manager()
    report["distro"] = pm

    # libc + linker
    libc = await detect_libc()
    report["libc"] = libc

    # ldd equivalent using linker
    report["ldd_equivalent"] = ldd_equivalent(libc.family, libc.selected_linker)

    return report
