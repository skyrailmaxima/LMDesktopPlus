from __future__ import annotations

import os
import platform
import socket
import time
from pathlib import Path
from typing import Any

from . import platform_freebsd as bsd
from .fncache import UseLevel, register_fn
from .platform_os import is_freebsd, is_linux
from .preopt import Outcome, first_ok_scan, parse_float, parse_int, try_run
from .util import first_executable


def _read_sysfs_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None


def _bytes_to_mb(raw: Any) -> float | None:
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        value = float(raw)
    else:
        value = parse_float(raw)
        if value is None:
            as_int = parse_int(raw)
            value = float(as_int) if as_int is not None else None
    if value is None:
        return None
    # Values ≥ 1 MiB are treated as bytes (rocm-smi / amdgpu sysfs).
    return round(value / (1024.0 * 1024.0), 1) if value >= 1_048_576 else round(value, 1)


def _normalize_csv_headers(headers: list[str]) -> dict[str, str]:
    # Lowercased header → original key for alias lookups (one pass).
    return {header.lower(): header for header in headers}


@register_fn(
    "system_info.parse_rocm_smi_csv",
    UseLevel.HIGH,
    "Parse rocm-smi --csv product/use/vram/temp into GPU metrics row",
)
def parse_rocm_smi_csv(stdout: str) -> dict[str, Any] | None:
    """Map first data row from rocm-smi CSV onto the shared GPU snapshot shape.

    @use: high use — purpose: AMD ROCm metrics without raising into poll.
    """
    lines = [
        line.strip()
        for line in stdout.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if len(lines) < 2:
        return None
    headers = [part.strip() for part in lines[0].split(",")]
    header_index = _normalize_csv_headers(headers)
    # One loop: first usable device row wins.
    for line in lines[1:]:
        cols = [part.strip() for part in line.split(",")]
        if len(cols) < 2:
            continue
        row = {headers[i]: cols[i] for i in range(min(len(headers), len(cols)))}
        percent = _row_float(
            row,
            header_index,
            ("gpu use (%)", "gpu%"),
        )
        mem_total = _bytes_to_mb(
            _row_raw(
                row,
                header_index,
                ("vram total memory (b)", "vram total memory(b)"),
            )
        )
        mem_used = _bytes_to_mb(
            _row_raw(
                row,
                header_index,
                ("vram total used memory (b)", "vram total used memory(b)"),
            )
        )
        temp = _row_float(
            row,
            header_index,
            (
                "temperature (sensor edge) (c)",
                "temperature (sensor junction) (c)",
                "temperature (sensor mem) (c)",
                "temperature (c)",
            ),
        )
        name = _row_raw(row, header_index, ("card series", "card model", "device")) or "AMD GPU"
        if percent is None and mem_total is None and temp is None:
            continue
        return {
            "name": str(name),
            "percent": percent,
            "memory_used_mb": mem_used,
            "memory_total_mb": mem_total,
            "temperature_c": temp,
            "source": "rocm-smi",
        }
    return None


def _row_raw(
    row: dict[str, str],
    header_index: dict[str, str],
    keys: tuple[str, ...],
) -> str | None:
    # @use: high use — purpose: O(aliases) CSV cell lookup via lowered header map
    for key in keys:
        actual = header_index.get(key)
        if actual is None:
            continue
        value = row.get(actual)
        if value not in (None, "", "N/A"):
            return value
    return None


def _row_float(
    row: dict[str, str],
    header_index: dict[str, str],
    keys: tuple[str, ...],
) -> float | None:
    raw = _row_raw(row, header_index, keys)
    return None if raw is None else parse_float(raw)


@register_fn(
    "system_info.probe_amd_sysfs_card",
    UseLevel.HIGH,
    "Read one amdgpu DRM card: busy%, VRAM, edge temp, product name",
)
def probe_amd_sysfs_card(card: Path) -> dict[str, Any] | None:
    """Probe a single `/sys/class/drm/cardN` tree for AMD metrics.

    @use: high use — purpose: AMD without ROCm userspace tools.
    """
    device = card / "device"
    busy_path = device / "gpu_busy_percent"
    if not busy_path.is_file():
        return None
    busy_raw = _read_sysfs_text(busy_path)
    percent = parse_float(busy_raw) if busy_raw is not None else None
    mem_used = _bytes_to_mb(_read_sysfs_text(device / "mem_info_vram_used"))
    mem_total = _bytes_to_mb(_read_sysfs_text(device / "mem_info_vram_total"))
    temp = _amd_sysfs_temp_c(device)
    name = (
        _read_sysfs_text(device / "product_name")
        or _amd_sysfs_marketing_name(device)
        or card.name
    )
    if percent is None and mem_total is None and temp is None:
        return None
    return {
        "name": name,
        "percent": percent,
        "memory_used_mb": mem_used,
        "memory_total_mb": mem_total,
        "temperature_c": temp,
        "source": "amdgpu-sysfs",
    }


def _amd_sysfs_temp_c(device: Path) -> float | None:
    # @use: high use — purpose: first amdgpu hwmon temp1_input (millidegC)
    hwmon_root = device / "hwmon"
    if not hwmon_root.is_dir():
        return None
    for hwmon in sorted(hwmon_root.glob("hwmon*")):
        raw = _read_sysfs_text(hwmon / "temp1_input")
        if raw is None:
            continue
        milli = parse_float(raw)
        if milli is None:
            continue
        celsius = milli / 1000.0 if milli > 200 else milli
        if -20 <= celsius <= 150:
            return round(celsius, 1)
    return None


def _amd_sysfs_marketing_name(device: Path) -> str | None:
    # @use: medium use — purpose: best-effort label from uevent PCI ids
    uevent = _read_sysfs_text(device / "uevent")
    if not uevent:
        return None
    vendor = device_id = None
    for line in uevent.splitlines():
        if line.startswith("PCI_ID="):
            parts = line.split("=", 1)[1].split(":")
            if len(parts) == 2:
                vendor, device_id = parts[0].lower(), parts[1].lower()
            break
    if vendor == "1002" and device_id:
        return f"AMD GPU ({device_id})"
    return "AMD GPU" if vendor == "1002" else None


class SystemSampler:
    def __init__(self) -> None:
        self._last_cpu: tuple[int, int] | None = None
        self._last_cores: list[tuple[int, int]] = []
        self._last_net: tuple[float, int, int] | None = None
        self._boot_time = self._read_boot_time()

    @staticmethod
    def _read_boot_time() -> float:
        if is_freebsd():
            boot = bsd.boot_time()
            return boot if boot is not None else time.time()
        if not is_linux():
            return time.time()
        try:
            for line in Path("/proc/stat").read_text().splitlines():
                if line.startswith("btime "):
                    return float(line.split()[1])
        except OSError:
            pass
        return time.time()

    @staticmethod
    def _cpu_rows() -> list[tuple[int, int]]:
        if is_freebsd():
            return bsd.cpu_rows()
        if not is_linux():
            return []
        rows: list[tuple[int, int]] = []
        try:
            for line in Path("/proc/stat").read_text().splitlines():
                if not line.startswith("cpu"):
                    break
                parts = line.split()
                if not parts[0][3:].isdigit() and parts[0] != "cpu":
                    continue
                values = [int(x) for x in parts[1:]]
                idle = values[3] + (values[4] if len(values) > 4 else 0)
                total = sum(values)
                rows.append((total, idle))
        except (OSError, ValueError):
            pass
        return rows

    @staticmethod
    def _delta_percent(prev: tuple[int, int] | None, cur: tuple[int, int]) -> float:
        if prev is None:
            return 0.0
        dt = cur[0] - prev[0]
        di = cur[1] - prev[1]
        if dt <= 0:
            return 0.0
        return max(0.0, min(100.0, 100.0 * (dt - di) / dt))

    @staticmethod
    def _memory() -> dict[str, Any]:
        if is_freebsd():
            return bsd.memory_snapshot()
        if not is_linux():
            return {"total": 0, "used": 0, "available": 0, "percent": 0.0}
        data: dict[str, int] = {}
        try:
            for line in Path("/proc/meminfo").read_text().splitlines():
                key, rest = line.split(":", 1)
                data[key] = int(rest.strip().split()[0]) * 1024
        except (OSError, ValueError):
            return {"total": 0, "used": 0, "available": 0, "percent": 0.0}
        total = data.get("MemTotal", 0)
        avail = data.get("MemAvailable", data.get("MemFree", 0))
        used = max(0, total - avail)
        return {
            "total": total,
            "used": used,
            "available": avail,
            "percent": round((used / total * 100.0) if total else 0.0, 1),
        }

    @staticmethod
    def _disk() -> dict[str, Any]:
        try:
            st = os.statvfs(str(Path.home()))
            total = st.f_blocks * st.f_frsize
            free = st.f_bavail * st.f_frsize
            used = max(0, total - free)
            return {"total": total, "used": used, "free": free, "percent": round(used / total * 100.0, 1) if total else 0.0}
        except OSError:
            return {"total": 0, "used": 0, "free": 0, "percent": 0.0}

    @staticmethod
    def _net_totals() -> tuple[int, int]:
        if is_freebsd():
            return bsd.net_totals()
        if not is_linux():
            return 0, 0
        rx = tx = 0
        try:
            for line in Path("/proc/net/dev").read_text().splitlines()[2:]:
                iface, values = line.split(":", 1)
                iface = iface.strip()
                if iface == "lo":
                    continue
                parts = values.split()
                rx += int(parts[0])
                tx += int(parts[8])
        except (OSError, ValueError, IndexError):
            pass
        return rx, tx

    def _network(self) -> dict[str, Any]:
        now = time.monotonic()
        rx, tx = self._net_totals()
        down = up = 0.0
        if self._last_net:
            then, old_rx, old_tx = self._last_net
            dt = max(0.001, now - then)
            down = max(0.0, (rx - old_rx) / dt)
            up = max(0.0, (tx - old_tx) / dt)
        self._last_net = (now, rx, tx)
        return {"rx_total": rx, "tx_total": tx, "down_bps": round(down, 1), "up_bps": round(up, 1)}

    @staticmethod
    def _temperatures() -> list[dict[str, Any]]:
        if is_freebsd():
            return bsd.temperatures()
        if not is_linux():
            return []
        values: list[dict[str, Any]] = []
        base = Path("/sys/class/thermal")
        if not base.exists():
            return values
        for zone in sorted(base.glob("thermal_zone*")):
            try:
                raw = float((zone / "temp").read_text().strip())
                label = (zone / "type").read_text().strip()
                temp_c = raw / 1000.0 if raw > 500 else raw
                if -20 <= temp_c <= 150:
                    values.append({"label": label, "celsius": round(temp_c, 1)})
            except (OSError, ValueError):
                continue
        return values[:12]

    @staticmethod
    def _gpu() -> dict[str, Any]:
        # @use: high use — purpose: metrics GPU sample; nvidia → AMD → unavailable
        def probe(fn) -> Outcome:
            row = fn()
            return Outcome.success(row) if row is not None else Outcome.fail("miss")

        result = first_ok_scan(
            (
                SystemSampler._nvidia_gpu,
                SystemSampler._amd_rocm_gpu,
                SystemSampler._amd_sysfs_gpu,
            ),
            probe,
            empty_error="no gpu backend",
        )
        return (
            result.value
            if result.ok
            else {"name": "unavailable", "percent": None, "source": None}
        )

    @staticmethod
    def _nvidia_gpu() -> dict[str, Any] | None:
        if not first_executable(["nvidia-smi"]):
            return None
        run = try_run(
            [
                "nvidia-smi",
                "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            timeout=2,
        )
        if not run.ok or not run.stdout.strip():
            return None
        first = [x.strip() for x in run.stdout.splitlines()[0].split(",")]
        if len(first) < 5:
            return None
        percent = parse_float(first[1])
        mem_used = parse_float(first[2])
        mem_total = parse_float(first[3])
        temp = parse_float(first[4])
        if None in (percent, mem_used, mem_total, temp):
            return None
        return {
            "name": first[0],
            "percent": percent,
            "memory_used_mb": mem_used,
            "memory_total_mb": mem_total,
            "temperature_c": temp,
            "source": "nvidia-smi",
        }

    @staticmethod
    def _amd_rocm_gpu() -> dict[str, Any] | None:
        # @use: high use — purpose: AMD metrics via rocm-smi CSV (try_run)
        if not first_executable(["rocm-smi"]):
            return None
        run = try_run(
            [
                "rocm-smi",
                "--showproductname",
                "--showuse",
                "--showmeminfo",
                "vram",
                "--showtemp",
                "--csv",
            ],
            timeout=2,
        )
        if not run.ok or not run.stdout.strip():
            return None
        return parse_rocm_smi_csv(run.stdout)

    @staticmethod
    def _amd_sysfs_gpu() -> dict[str, Any] | None:
        # @use: high use — purpose: amdgpu sysfs util/VRAM/temp without ROCm tools
        cards = sorted(Path("/sys/class/drm").glob("card[0-9]*"))
        for card in cards:
            row = probe_amd_sysfs_card(card)
            if row is not None:
                return row
        return None

    @staticmethod
    def _battery() -> dict[str, Any] | None:
        if is_freebsd():
            return bsd.battery()
        if not is_linux():
            return None
        for bat in sorted(Path("/sys/class/power_supply").glob("BAT*")):
            try:
                capacity = int((bat / "capacity").read_text().strip())
                status = (bat / "status").read_text().strip()
                return {"percent": capacity, "status": status}
            except (OSError, ValueError):
                continue
        return None

    @staticmethod
    def identity() -> dict[str, Any]:
        if is_freebsd():
            os_pretty = bsd.pretty_os()
        else:
            os_release: dict[str, str] = {}
            try:
                for line in Path("/etc/os-release").read_text().splitlines():
                    if "=" in line:
                        key, value = line.split("=", 1)
                        os_release[key] = value.strip().strip('"')
            except OSError:
                pass
            os_pretty = os_release.get("PRETTY_NAME", platform.platform())
        return {
            "hostname": socket.gethostname(),
            "user": os.environ.get("USER") or os.environ.get("LOGNAME") or "user",
            "os": os_pretty,
            "kernel": platform.release(),
            "architecture": platform.machine(),
            "session": os.environ.get("XDG_CURRENT_DESKTOP") or os.environ.get("DESKTOP_SESSION") or "unknown",
            "session_type": os.environ.get("XDG_SESSION_TYPE", "unknown"),
            "python": platform.python_version(),
            "cpu_model": SystemSampler._cpu_model(),
        }

    @staticmethod
    def _cpu_model() -> str:
        if is_freebsd():
            return bsd.cpu_model()
        if is_linux():
            try:
                for line in Path("/proc/cpuinfo").read_text(errors="replace").splitlines():
                    if line.lower().startswith("model name"):
                        return line.split(":", 1)[1].strip()
            except OSError:
                pass
        return platform.processor() or "unknown"

    def sample(self) -> dict[str, Any]:
        rows = self._cpu_rows()
        overall = rows[0] if rows else (0, 0)
        cores = rows[1:] if len(rows) > 1 else []
        cpu_pct = self._delta_percent(self._last_cpu, overall)
        core_pct = [self._delta_percent(self._last_cores[i] if i < len(self._last_cores) else None, row) for i, row in enumerate(cores)]
        self._last_cpu = overall
        self._last_cores = cores
        return {
            "timestamp": time.time(),
            "uptime_seconds": max(0, int(time.time() - self._boot_time)),
            "cpu": {"percent": round(cpu_pct, 1), "cores": [round(v, 1) for v in core_pct], "count": os.cpu_count() or len(cores)},
            "memory": self._memory(),
            "disk": self._disk(),
            "network": self._network(),
            "gpu": self._gpu(),
            "temperatures": self._temperatures(),
            "battery": self._battery(),
            "load_average": list(os.getloadavg()) if hasattr(os, "getloadavg") else [0.0, 0.0, 0.0],
        }
