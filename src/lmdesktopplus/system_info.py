from __future__ import annotations

import os
import platform
import socket
import time
from pathlib import Path
from typing import Any

from .preopt import parse_float, try_run
from .util import first_executable


class SystemSampler:
    def __init__(self) -> None:
        self._last_cpu: tuple[int, int] | None = None
        self._last_cores: list[tuple[int, int]] = []
        self._last_net: tuple[float, int, int] | None = None
        self._boot_time = self._read_boot_time()

    @staticmethod
    def _read_boot_time() -> float:
        try:
            for line in Path("/proc/stat").read_text().splitlines():
                if line.startswith("btime "):
                    return float(line.split()[1])
        except OSError:
            pass
        return time.time()

    @staticmethod
    def _cpu_rows() -> list[tuple[int, int]]:
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
        # @use: high use — purpose: metrics GPU sample; nvidia-smi via try_run
        nvidia = SystemSampler._nvidia_gpu()
        if nvidia is not None:
            return nvidia
        # AMD exposes busy percent on many amdgpu systems (one loop).
        for card in sorted(Path("/sys/class/drm").glob("card*/device/gpu_busy_percent")):
            try:
                pct = float(card.read_text().strip())
                name = card.parents[1].name
                return {"name": name, "percent": pct, "source": "sysfs"}
            except (OSError, ValueError):
                continue
        return {"name": "unavailable", "percent": None, "source": None}

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
    def _battery() -> dict[str, Any] | None:
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
        os_release: dict[str, str] = {}
        try:
            for line in Path("/etc/os-release").read_text().splitlines():
                if "=" in line:
                    key, value = line.split("=", 1)
                    os_release[key] = value.strip().strip('"')
        except OSError:
            pass
        return {
            "hostname": socket.gethostname(),
            "user": os.environ.get("USER") or os.environ.get("LOGNAME") or "user",
            "os": os_release.get("PRETTY_NAME", platform.platform()),
            "kernel": platform.release(),
            "architecture": platform.machine(),
            "session": os.environ.get("XDG_CURRENT_DESKTOP") or os.environ.get("DESKTOP_SESSION") or "unknown",
            "session_type": os.environ.get("XDG_SESSION_TYPE", "unknown"),
            "python": platform.python_version(),
            "cpu_model": SystemSampler._cpu_model(),
        }

    @staticmethod
    def _cpu_model() -> str:
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
