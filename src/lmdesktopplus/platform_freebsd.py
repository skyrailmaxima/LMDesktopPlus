"""FreeBSD sysctl helpers for the machine UI metrics sampler.

Uses `sysctl -n` via try_run so poll ticks stay exception-free and work without
ctypes. Linux keeps /proc+/sys; this module is FreeBSD-only.
"""

from __future__ import annotations

import re
from typing import Any

from .fncache import UseLevel, register_fn
from .preopt import parse_float, parse_int, try_run

_BOOTTIME_SEC_RE = re.compile(r"sec\s*=\s*(\d+)")
_TEMP_RE = re.compile(r"([-+]?\d+(?:\.\d+)?)\s*C?", re.IGNORECASE)


@register_fn(
    "platform_freebsd.sysctl_n",
    UseLevel.HIGH,
    "Read one sysctl -n value without raising",
)
def sysctl_n(name: str, *, timeout: float = 2.0) -> str | None:
    # @use: high use — purpose: FreeBSD metrics probe edge
    run = try_run(["sysctl", "-n", name], timeout=timeout)
    if not run.ok:
        return None
    text = run.stdout.strip()
    return text or None


def sysctl_int(name: str) -> int | None:
    return parse_int(sysctl_n(name))


def sysctl_float(name: str) -> float | None:
    return parse_float(sysctl_n(name))


@register_fn(
    "platform_freebsd.parse_boottime",
    UseLevel.MEDIUM,
    "Parse kern.boottime into epoch seconds",
)
def parse_boottime(raw: str | None) -> float | None:
    # @use: medium use — purpose: uptime base from kern.boottime
    if not raw:
        return None
    # Common form: { sec = 1712345678, usec = 123 } Fri ...
    match = _BOOTTIME_SEC_RE.search(raw)
    if match:
        return float(match.group(1))
    # Numeric-only fallback.
    return parse_float(raw.split()[0] if raw.split() else raw)


@register_fn(
    "platform_freebsd.parse_cp_time",
    UseLevel.HIGH,
    "Parse kern.cp_time into (total, idle) tick tuple",
)
def parse_cp_time(raw: str | None) -> tuple[int, int] | None:
    # @use: high use — purpose: FreeBSD CPU% from user/nice/sys/intr/idle
    if not raw:
        return None
    parts = [parse_int(tok) for tok in raw.split()]
    if len(parts) < 5 or any(p is None for p in parts[:5]):
        return None
    user, nice, sys, intr, idle = parts[0], parts[1], parts[2], parts[3], parts[4]
    assert user is not None and nice is not None and sys is not None
    assert intr is not None and idle is not None
    total = user + nice + sys + intr + idle
    return total, idle


@register_fn(
    "platform_freebsd.parse_cp_times",
    UseLevel.HIGH,
    "Parse kern.cp_times into overall + per-core (total, idle) rows",
)
def parse_cp_times(raw: str | None) -> list[tuple[int, int]]:
    # @use: high use — purpose: FreeBSD per-CPU rows matching Linux /proc/stat shape
    if not raw:
        return []
    tokens = raw.split()
    if len(tokens) < 5 or len(tokens) % 5 != 0:
        return []
    nums: list[int] = []
    for tok in tokens:
        value = parse_int(tok)
        if value is None:
            return []
        nums.append(value)
    cores: list[tuple[int, int]] = []
    overall_total = overall_idle = 0
    for i in range(0, len(nums), 5):
        user, nice, sys, intr, idle = nums[i : i + 5]
        total = user + nice + sys + intr + idle
        cores.append((total, idle))
        overall_total += total
        overall_idle += idle
    return [(overall_total, overall_idle), *cores]


def cpu_rows() -> list[tuple[int, int]]:
    # Prefer per-CPU kern.cp_times; fall back to aggregate kern.cp_time.
    rows = parse_cp_times(sysctl_n("kern.cp_times"))
    if rows:
        return rows
    one = parse_cp_time(sysctl_n("kern.cp_time"))
    return [one] if one is not None else []


def boot_time() -> float | None:
    return parse_boottime(sysctl_n("kern.boottime"))


@register_fn(
    "platform_freebsd.parse_temperature",
    UseLevel.MEDIUM,
    "Parse FreeBSD sysctl temperature strings like '45.0C'",
)
def parse_temperature(raw: str | None) -> float | None:
    if not raw:
        return None
    match = _TEMP_RE.search(raw)
    if not match:
        return parse_float(raw)
    value = parse_float(match.group(1))
    if value is None:
        return None
    # Some sensors report deci-Kelvin; reject absurd values.
    return value if -20 <= value <= 150 else None


def memory_snapshot() -> dict[str, Any]:
    # @use: high use — purpose: FreeBSD RAM from hw.physmem + vm.stats
    page = sysctl_int("vm.stats.vm.v_page_size") or 4096
    phys = sysctl_int("hw.physmem")
    free = sysctl_int("vm.stats.vm.v_free_count")
    inactive = sysctl_int("vm.stats.vm.v_inactive_count") or 0
    if phys is None or free is None:
        return {"total": 0, "used": 0, "available": 0, "percent": 0.0}
    available = (free + inactive) * page
    used = max(0, phys - available)
    return {
        "total": phys,
        "used": used,
        "available": available,
        "percent": round((used / phys * 100.0) if phys else 0.0, 1),
    }


def net_totals() -> tuple[int, int]:
    # @use: medium use — purpose: sum iface bytes via netstat -ibn (one loop)
    run = try_run(["netstat", "-ibn", "-f", "link"], timeout=3)
    if not run.ok:
        return 0, 0
    rx = tx = 0
    # Header varies; find Ibytes/Obytes columns from first non-empty line.
    lines = [ln for ln in run.stdout.splitlines() if ln.strip()]
    if len(lines) < 2:
        return 0, 0
    header = lines[0].split()
    try:
        ib_idx = header.index("Ibytes")
        ob_idx = header.index("Obytes")
        name_idx = 0
    except ValueError:
        return 0, 0
    for line in lines[1:]:
        parts = line.split()
        if len(parts) <= max(ib_idx, ob_idx):
            continue
        name = parts[name_idx]
        if name == "Name" or name.startswith("lo"):
            continue
        ib = parse_int(parts[ib_idx]) or 0
        ob = parse_int(parts[ob_idx]) or 0
        rx += ib
        tx += ob
    return rx, tx


def temperatures() -> list[dict[str, Any]]:
    # @use: medium use — purpose: sample a few CPU/ACPI thermal sysctls
    values: list[dict[str, Any]] = []
    # Prefer explicit CPU sensors (one bounded loop).
    for idx in range(0, 16):
        raw = sysctl_n(f"dev.cpu.{idx}.temperature")
        temp = parse_temperature(raw)
        if temp is None:
            break
        values.append({"label": f"cpu{idx}", "celsius": round(temp, 1)})
    if values:
        return values[:12]
    for name in ("hw.acpi.thermal.tz0.temperature", "hw.acpi.thermal.tz1.temperature"):
        temp = parse_temperature(sysctl_n(name))
        if temp is not None:
            values.append({"label": name.split(".")[-2], "celsius": round(temp, 1)})
    return values[:12]


@register_fn(
    "platform_freebsd.battery_status_label",
    UseLevel.MEDIUM,
    "Map hw.acpi.battery.state bitfield to Charging/Discharging/Full",
)
def battery_status_label(raw: str | None) -> str:
    # ACPI_BATT_STAT_DISCHARG=1, CHARGING=2, CRITICAL=4 (FreeBSD sys/dev/acpica).
    state = parse_int(raw)
    if state is None:
        return raw or "unknown"
    if state & 2:
        return "Charging"
    if state & 1:
        return "Discharging"
    if state == 0:
        return "Full"
    return f"state:{state}"


def battery() -> dict[str, Any] | None:
    life = sysctl_int("hw.acpi.battery.life")
    if life is None or life < 0:
        return None
    return {
        "percent": life,
        "status": battery_status_label(sysctl_n("hw.acpi.battery.state")),
    }


def cpu_model() -> str:
    return sysctl_n("hw.model") or "unknown"


def pretty_os() -> str:
    # @use: medium use — purpose: identity.os for FreeBSD guests
    release = sysctl_n("kern.osrelease") or ""
    version = sysctl_n("kern.version")
    if version:
        first = version.splitlines()[0].strip()
        return first[:120] if first else f"FreeBSD {release}".strip()
    return f"FreeBSD {release}".strip() or "FreeBSD"
