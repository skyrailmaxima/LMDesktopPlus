from __future__ import annotations

import json
import subprocess
import unittest
from unittest.mock import patch

from lmdesktopplus.adapters.storage import (
    RemovableStorageAdapter,
    normalize_device,
    parse_lsblk_json,
)


def completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


LSBLK = {
    "blockdevices": [
        {
            "name": "sda",
            "path": "/dev/sda",
            "type": "disk",
            "size": "500G",
            "fstype": None,
            "label": None,
            "mountpoint": None,
            "rm": False,
            "hotplug": False,
            "tran": "sata",
            "children": [
                {
                    "name": "sda1",
                    "path": "/dev/sda1",
                    "type": "part",
                    "size": "500G",
                    "fstype": "ext4",
                    "label": "root",
                    "mountpoint": "/",
                    "rm": False,
                    "hotplug": False,
                    "tran": None,
                }
            ],
        },
        {
            "name": "sdb",
            "path": "/dev/sdb",
            "type": "disk",
            "size": "16G",
            "fstype": None,
            "label": None,
            "mountpoint": None,
            "rm": True,
            "hotplug": True,
            "tran": "usb",
            "children": [
                {
                    "name": "sdb1",
                    "path": "/dev/sdb1",
                    "type": "part",
                    "size": "16G",
                    "fstype": "vfat",
                    "label": "STICK",
                    "mountpoint": None,
                    "rm": True,
                    "hotplug": True,
                    "tran": "usb",
                }
            ],
        },
    ]
}


class StorageParserTests(unittest.TestCase):
    def test_parse_keeps_removable_partitions_only(self):
        rows = parse_lsblk_json(LSBLK)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["path"], "/dev/sdb1")
        self.assertTrue(rows[0]["allowlisted"])
        self.assertFalse(rows[0]["mounted"])

    def test_normalize_device_allowlist(self):
        self.assertEqual(normalize_device("/dev/sdb1"), "/dev/sdb1")
        self.assertEqual(normalize_device("/dev/nvme0n1p2"), "/dev/nvme0n1p2")
        self.assertIsNone(normalize_device("/dev/sda"))
        self.assertIsNone(normalize_device("/dev/sda1;rm"))
        self.assertIsNone(normalize_device("../../etc/passwd"))


class StorageAdapterTests(unittest.TestCase):
    def test_unavailable_without_lsblk(self):
        self.assertEqual(
            RemovableStorageAdapter(lsblk="", udisksctl="").snapshot(),
            {"available": False},
        )

    @patch("lmdesktopplus.preopt.run_capture")
    def test_snapshot_lists_removable(self, run_capture):
        run_capture.return_value = completed(json.dumps(LSBLK))
        adapter = RemovableStorageAdapter(
            lsblk="/usr/bin/lsblk",
            udisksctl="/usr/bin/udisksctl",
            cache_ttl=5.0,
        )
        snap = adapter.snapshot()
        self.assertTrue(snap["available"])
        self.assertTrue(snap["can_mount"])
        self.assertEqual(snap["devices"][0]["label"], "STICK")
        self.assertEqual(adapter.snapshot()["devices"][0]["path"], "/dev/sdb1")
        self.assertEqual(run_capture.call_count, 1)

    @patch("lmdesktopplus.preopt.run_capture")
    def test_mount_and_unmount(self, run_capture):
        run_capture.side_effect = [
            completed(json.dumps(LSBLK)),  # snapshot gate
            completed("Mounted /dev/sdb1 at /media/user/STICK.\n"),
            completed(json.dumps(LSBLK)),  # snapshot gate for unmount
            completed(),
        ]
        adapter = RemovableStorageAdapter(
            lsblk="/usr/bin/lsblk",
            udisksctl="/usr/bin/udisksctl",
        )
        mounted = adapter.command("mount", {"device": "/dev/sdb1"})
        self.assertTrue(mounted["ok"])
        self.assertEqual(mounted["mountpoint"], "/media/user/STICK")
        self.assertEqual(
            run_capture.call_args_list[1].args[0],
            ["/usr/bin/udisksctl", "mount", "-b", "/dev/sdb1"],
        )
        unmounted = adapter.command("unmount", {"path": "/dev/sdb1"})
        self.assertTrue(unmounted["ok"])
        self.assertEqual(
            run_capture.call_args_list[3].args[0],
            ["/usr/bin/udisksctl", "unmount", "-b", "/dev/sdb1"],
        )

    @patch("lmdesktopplus.preopt.run_capture")
    def test_rejects_non_removable_and_missing_udisks(self, run_capture):
        run_capture.return_value = completed(json.dumps(LSBLK))
        no_udisks = RemovableStorageAdapter(
            lsblk="/usr/bin/lsblk",
            udisksctl=None,
        )
        result = no_udisks.command("mount", {"device": "/dev/sdb1"})
        self.assertEqual(result["error_code"], "unavailable")

        adapter = RemovableStorageAdapter(
            lsblk="/usr/bin/lsblk",
            udisksctl="/usr/bin/udisksctl",
        )
        bad = adapter.command("mount", {"device": "/dev/sda1"})
        self.assertEqual(bad["error_code"], "invalid_argument")


if __name__ == "__main__":
    unittest.main()
