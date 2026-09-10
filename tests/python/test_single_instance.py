from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from lmdesktopplus import single_instance
from lmdesktopplus.single_instance import SingleInstance, focus_existing_window


class SingleInstanceTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        patcher = mock.patch.object(
            single_instance, "runtime_dir", return_value=Path(self._tmp.name)
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_second_acquire_is_rejected_while_held(self):
        first = SingleInstance()
        self.assertTrue(first.acquire())
        self.addCleanup(first.release)

        second = SingleInstance()
        self.assertFalse(second.acquire())

    def test_release_allows_reacquire(self):
        first = SingleInstance()
        self.assertTrue(first.acquire())
        first.release()

        second = SingleInstance()
        self.assertTrue(second.acquire())
        self.addCleanup(second.release)

    def test_owner_pid_records_current_process(self):
        guard = SingleInstance()
        self.assertTrue(guard.acquire())
        self.addCleanup(guard.release)
        self.assertEqual(guard.owner_pid(), os.getpid())

    def test_context_manager_releases_on_exit(self):
        with SingleInstance() as guard:
            self.assertTrue(guard.acquire())
        # Lock released on __exit__, so a fresh guard can take it.
        again = SingleInstance()
        self.assertTrue(again.acquire())
        self.addCleanup(again.release)

    def test_release_without_acquire_is_safe(self):
        guard = SingleInstance()
        guard.release()  # must not raise


class FocusExistingWindowTests(unittest.TestCase):
    def test_returns_false_without_focus_tools(self):
        with mock.patch.object(single_instance, "executable", return_value=None):
            self.assertFalse(focus_existing_window("lmdesktopplus"))

    def test_uses_wmctrl_when_available(self):
        def fake_executable(name):
            return "/usr/bin/wmctrl" if name == "wmctrl" else None

        with mock.patch.object(single_instance, "executable", side_effect=fake_executable), \
                mock.patch.object(single_instance, "spawn", return_value=True) as spawn:
            self.assertTrue(focus_existing_window("lmdesktopplus"))
            spawn.assert_called()


if __name__ == "__main__":
    unittest.main()
