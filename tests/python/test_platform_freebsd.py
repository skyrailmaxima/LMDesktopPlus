from __future__ import annotations

import unittest
from unittest.mock import patch

from lmdesktopplus import platform_freebsd as bsd
from lmdesktopplus.platform_os import (
    FAMILY_FREEBSD,
    FAMILY_LINUX,
    clear_os_family_cache,
    is_freebsd,
    is_linux,
    os_family,
)


class PlatformOsTests(unittest.TestCase):
    def tearDown(self) -> None:
        clear_os_family_cache()

    @patch("lmdesktopplus.platform_os.platform.system", return_value="Linux")
    def test_linux_family(self, _system):
        clear_os_family_cache()
        self.assertEqual(os_family(), FAMILY_LINUX)
        self.assertTrue(is_linux())
        self.assertFalse(is_freebsd())

    @patch("lmdesktopplus.platform_os.platform.system", return_value="FreeBSD")
    def test_freebsd_family(self, _system):
        clear_os_family_cache()
        self.assertEqual(os_family(), FAMILY_FREEBSD)
        self.assertTrue(is_freebsd())
        self.assertFalse(is_linux())

    @patch("lmdesktopplus.platform_os.platform.system", return_value="DragonFly")
    def test_dragonfly_maps_to_freebsd(self, _system):
        clear_os_family_cache()
        self.assertEqual(os_family(), FAMILY_FREEBSD)


class FreeBsdParsersTests(unittest.TestCase):
    def test_parse_boottime(self):
        raw = "{ sec = 1712345678, usec = 123456 } Fri Apr  5 12:34:38 2024"
        self.assertEqual(bsd.parse_boottime(raw), 1712345678.0)

    def test_parse_cp_time(self):
        # user nice sys intr idle
        self.assertEqual(bsd.parse_cp_time("10 1 2 3 84"), (100, 84))

    def test_parse_cp_times_builds_overall_and_cores(self):
        # two CPUs × 5 counters
        rows = bsd.parse_cp_times("10 0 0 0 90 20 0 0 0 80")
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0], (200, 170))
        self.assertEqual(rows[1], (100, 90))
        self.assertEqual(rows[2], (100, 80))

    def test_parse_temperature(self):
        self.assertEqual(bsd.parse_temperature("45.0C"), 45.0)
        self.assertEqual(bsd.parse_temperature("37.5"), 37.5)
        self.assertIsNone(bsd.parse_temperature("9999C"))


class FreeBsdPowerTests(unittest.TestCase):
    @patch("lmdesktopplus.actions.is_freebsd", return_value=True)
    @patch("lmdesktopplus.actions.executable", side_effect=lambda n: "/bin/zzz" if n == "zzz" else None)
    def test_freebsd_suspend_prefers_zzz(self, _exe, _bsd):
        from lmdesktopplus.actions import _power_argv

        self.assertEqual(_power_argv("suspend"), ["zzz"])

    @patch("lmdesktopplus.actions.is_freebsd", return_value=True)
    @patch("lmdesktopplus.actions.executable", return_value=None)
    def test_freebsd_suspend_falls_back_to_acpiconf(self, _exe, _bsd):
        from lmdesktopplus.actions import _power_argv

        self.assertEqual(_power_argv("suspend"), ["acpiconf", "-s", "3"])

    @patch("lmdesktopplus.actions.is_freebsd", return_value=True)
    def test_freebsd_reboot_shutdown(self, _bsd):
        from lmdesktopplus.actions import _power_argv

        self.assertEqual(_power_argv("reboot"), ["shutdown", "-r", "now"])
        self.assertEqual(_power_argv("poweroff"), ["shutdown", "-p", "now"])


if __name__ == "__main__":
    unittest.main()
