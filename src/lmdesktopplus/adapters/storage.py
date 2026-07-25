"""Removable storage via lsblk + udisksctl (Stage C).

@use levels: snapshot/parse are medium; mount/unmount are low use.
Only allowlisted removable partition paths may be mounted.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from typing import Any

from ..fncache import UseLevel, register_fn
from ..util import executable, run_capture
from .base import command_error, dispatch_command

# Removable/hotplug partitions and whole disks only — never system roots by path alone.
_DEVICE_RE = re.compile(
    r"^/dev/(?:"
    r"sd[a-z]+\d+"
    r"|vd[a-z]+\d+"
    r"|nvme\d+n\d+p\d+"
    r"|mmcblk\d+p\d+"
    r")$"
)


def normalize_device(value: Any) -> str | None:
    # @use: medium use — purpose: allowlist removable partition device paths
    if not isinstance(value, str):
        return None
    device = value.strip()
    if not _DEVICE_RE.match(device):
        return None
    return device


def _flatten_blockdevices(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # @use: medium use — purpose: flatten lsblk children into a single walk list
    flat: list[dict[str, Any]] = []
    for node in nodes:
        flat.append(node)
        children = node.get("children") or []
        if isinstance(children, list):
            flat.extend(_flatten_blockdevices(children))
    return flat


def is_removable_candidate(node: dict[str, Any]) -> bool:
    # @use: medium use — purpose: keep USB/MMC/hotplug volumes only
    node_type = str(node.get("type") or "").lower()
    if node_type not in {"part", "disk"}:
        return False
    rm = node.get("rm") in (True, 1, "1", "true", "True")
    hotplug = node.get("hotplug") in (True, 1, "1", "true", "True")
    tran = str(node.get("tran") or "").lower()
    return rm or hotplug or tran in {"usb", "firewire", "mmc", "sdio"}


@register_fn(
    "storage.parse_lsblk_json",
    UseLevel.MEDIUM,
    "Parse lsblk -J into allowlisted removable volume rows",
)
def parse_lsblk_json(payload: str | dict[str, Any]) -> list[dict[str, Any]]:
    # @use: medium use — purpose: Monitor/Settings storage panel device list
    data = json.loads(payload) if isinstance(payload, str) else payload
    devices = data.get("blockdevices") if isinstance(data, dict) else None
    if not isinstance(devices, list):
        return []
    rows: list[dict[str, Any]] = []
    for node in _flatten_blockdevices(devices):
        if not is_removable_candidate(node):
            continue
        path = node.get("path") or (
            f"/dev/{node['name']}" if node.get("name") else None
        )
        if not isinstance(path, str):
            continue
        # Prefer partitions for mount/unmount; keep disks that have no children listed.
        node_type = str(node.get("type") or "").lower()
        children = node.get("children") or []
        if node_type == "disk" and children:
            continue
        rows.append(
            {
                "name": str(node.get("name") or path),
                "path": path,
                "type": node_type,
                "size": str(node.get("size") or ""),
                "fstype": node.get("fstype") or None,
                "label": node.get("label") or None,
                "mountpoint": node.get("mountpoint") or None,
                "mounted": bool(node.get("mountpoint")),
                "tran": node.get("tran") or None,
                "allowlisted": bool(normalize_device(path)),
            }
        )
    rows.sort(key=lambda row: row["path"])
    return rows


class RemovableStorageAdapter:
    """List and mount/unmount removable volumes through udisksctl."""

    id = "storage"

    def __init__(
        self,
        cache_ttl: float = 5.0,
        lsblk: str | None = None,
        udisksctl: str | None = None,
    ) -> None:
        if lsblk is None:
            lsblk = executable("lsblk")
        if udisksctl is None:
            udisksctl = executable("udisksctl")
        self.lsblk = lsblk or None
        self.udisksctl = udisksctl or None
        self.cache_ttl = cache_ttl
        self._cached_at = 0.0
        self._cached_snapshot: dict[str, Any] | None = None

    def available(self) -> bool:
        return bool(self.lsblk)

    def snapshot(self) -> dict[str, Any]:
        # @use: medium use — purpose: storage panel poll via lsblk -J
        if not self.available():
            return {"available": False}
        now = time.monotonic()
        if self._cached_snapshot is not None and now - self._cached_at < self.cache_ttl:
            return self._cached_snapshot.copy()
        try:
            result = run_capture(
                [
                    self.lsblk,
                    "-J",
                    "-o",
                    "NAME,PATH,TYPE,SIZE,FSTYPE,LABEL,MOUNTPOINT,RM,HOTPLUG,TRAN",
                ],
                timeout=5,
            )
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip() or "lsblk failed")
            devices = parse_lsblk_json(result.stdout)
            snapshot = {
                "available": True,
                "backend": "lsblk",
                "can_mount": bool(self.udisksctl),
                "devices": devices,
            }
        except (OSError, RuntimeError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
            snapshot = {"available": False, "last_error": str(exc)}
        self._cached_at = now
        self._cached_snapshot = snapshot
        return snapshot.copy()

    def command(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        # @use: medium use — purpose: mount/unmount/refresh via command hashmap
        return dispatch_command(self._commands(), name, payload, adapter_id=self.id)

    def _commands(self) -> dict[str, Any]:
        return {
            "mount": lambda payload: self._require_lsblk(
                lambda: self._require_udisks(lambda: self._device_action("mount", payload))
            ),
            "unmount": lambda payload: self._require_lsblk(
                lambda: self._require_udisks(lambda: self._device_action("unmount", payload))
            ),
            "refresh": lambda _payload: self._require_lsblk(self._refresh),
        }

    def _require_lsblk(self, action):
        if not self.available():
            return command_error("unavailable", "lsblk is not installed")
        return action()

    def _require_udisks(self, action):
        if not self.udisksctl:
            return command_error("unavailable", "udisksctl is not installed")
        return action()

    def _refresh(self) -> dict[str, Any]:
        self._cached_snapshot = None
        return {"ok": True, **self.snapshot()}

    def _device_action(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        device = normalize_device(payload.get("device") or payload.get("path"))
        if device is None:
            return command_error(
                "invalid_argument",
                "device must be an allowlisted removable partition path",
            )
        return self._mount_or_unmount(action, device)

    def _mount_or_unmount(self, action: str, device: str) -> dict[str, Any]:
        # @use: low use — purpose: udisksctl mount/unmount after live allowlist check
        # Confirm the device still looks removable before invoking udisks.
        snap = self.snapshot()
        known = {
            row["path"]: row
            for row in snap.get("devices", [])
            if isinstance(row, dict) and row.get("path")
        }
        entry = known.get(device)
        if entry is None or not entry.get("allowlisted"):
            return command_error(
                "invalid_argument",
                "device is not a currently detected removable volume",
            )
        try:
            result = run_capture(
                [self.udisksctl, action, "-b", device],
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            if isinstance(exc, subprocess.TimeoutExpired):
                return command_error("timeout", f"udisksctl {action} timed out")
            return command_error("internal_error", str(exc))
        if result.returncode != 0:
            error = result.stderr.strip() or result.stdout.strip() or f"udisksctl {action} failed"
            lower = error.lower()
            if "permission" in lower or "not authorized" in lower or "polkit" in lower:
                return command_error("permission_denied", error)
            return command_error("internal_error", error)
        self._cached_snapshot = None
        return {
            "ok": True,
            "action": action,
            "device": device,
            "mountpoint": self._parse_mountpoint(result.stdout or "") if action == "mount" else None,
            "message": (result.stdout or "").strip() or None,
        }

    @staticmethod
    def _parse_mountpoint(stdout: str) -> str | None:
        # @use: low use — purpose: extract "Mounted … at PATH" from udisksctl
        for line in stdout.splitlines():
            if "at" in line.lower():
                # Typical: Mounted /dev/sdb1 at /media/user/LABEL
                parts = line.rsplit(" at ", 1)
                if len(parts) == 2:
                    return parts[1].strip().rstrip(".")
        return None
