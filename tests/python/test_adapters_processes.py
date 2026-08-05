from __future__ import annotations

import os
import signal
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lmdesktopplus.adapters.processes import (
    ProcessAdapter,
    parse_proc_stat,
    parse_status_name,
    parse_status_uids,
)


def write_proc(root: Path, pid: int, name: str, uid: int, utime: int, stime: int, rss: int) -> None:
    proc = root / str(pid)
    proc.mkdir(parents=True, exist_ok=True)
    # Minimal /proc/<pid>/stat with enough trailing fields for utime/stime/rss.
    # Format: pid (comm) state ppid ... (fields 3..)
    after = ["S", "1"] + ["0"] * 9 + [str(utime), str(stime)] + ["0"] * 8 + [str(rss)] + ["0"] * 20
    (proc / "stat").write_text(f"{pid} ({name}) {' '.join(after)}\n", encoding="utf-8")
    (proc / "status").write_text(
        f"Name:\t{name}\nUid:\t{uid}\t{uid}\t{uid}\t{uid}\n",
        encoding="utf-8",
    )


class ProcessParserTests(unittest.TestCase):
    def test_parse_proc_stat_with_spaces_in_comm(self):
        # state..cmajflt (11 fields), then utime=10 stime=5, then pad to rss index 21.
        after = ["S", "1"] + ["0"] * 9 + ["10", "5"] + ["0"] * 8 + ["1234"]
        line = f"42 (my proc) {' '.join(after)}\n"
        parsed = parse_proc_stat(line)
        self.assertEqual(parsed, (42, 15, 1234))

    def test_parse_status_helpers(self):
        text = "Name:\tpython3\nUid:\t1000\t1000\t1000\t1000\n"
        self.assertEqual(parse_status_name(text), "python3")
        self.assertEqual(parse_status_uids(text), 1000)


class ProcessAdapterTests(unittest.TestCase):
    def test_snapshot_ranks_by_cpu_after_second_sample(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_proc(root, 10, "idle", 1000, 10, 0, 100)
            write_proc(root, 20, "busy", 1000, 10, 0, 200)
            adapter = ProcessAdapter(
                proc_root=root,
                uid=1000,
                page_size=4096,
                cpu_count=2,
                cache_ttl=0,
                top_n=5,
            )
            first = adapter.snapshot()
            self.assertTrue(first["available"])
            self.assertEqual(len(first["processes"]), 2)
            write_proc(root, 10, "idle", 1000, 12, 0, 100)
            write_proc(root, 20, "busy", 1000, 110, 0, 200)
            # Force elapsed > 0 by adjusting previous mono.
            adapter._prev_mono = adapter._prev_mono - 1.0  # type: ignore[operator]
            second = adapter.snapshot()
            self.assertEqual(second["processes"][0]["name"], "busy")
            self.assertGreater(second["processes"][0]["cpu_percent"], second["processes"][1]["cpu_percent"])
            self.assertEqual(second["processes"][0]["rss_bytes"], 200 * 4096)
            self.assertTrue(second["processes"][0]["owned"])

    def test_terminate_only_owned_pids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_proc(root, 55, "mine", 1000, 1, 0, 10)
            write_proc(root, 66, "other", 0, 1, 0, 10)
            adapter = ProcessAdapter(proc_root=root, uid=1000, cache_ttl=0)
            denied = adapter.command("terminate", {"pid": 66})
            self.assertEqual(denied["error_code"], "permission_denied")
            with patch("os.kill") as kill:
                ok = adapter.command("terminate", {"pid": 55})
                self.assertTrue(ok["ok"])
                kill.assert_called_once_with(55, signal.SIGTERM)

    def test_terminate_rejects_self_and_init(self):
        adapter = ProcessAdapter(proc_root=Path("/tmp"), uid=1000)
        self.assertEqual(
            adapter.command("terminate", {"pid": 1})["error_code"],
            "invalid_argument",
        )
        self.assertEqual(
            adapter.command("terminate", {"pid": os.getpid()})["error_code"],
            "invalid_argument",
        )


if __name__ == "__main__":
    unittest.main()
