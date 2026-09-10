from __future__ import annotations

import unittest

from lmdesktopplus import main
from lmdesktopplus.toolkit import available_toolkits, select_toolkit


def _fake_available(mapping):
    def _available(namespace):
        return set(mapping.get(namespace, ()))
    return _available


class ToolkitSelectionTests(unittest.TestCase):
    def test_prefers_gtk4_webkit6(self):
        available = _fake_available({"Gtk": {"3.0", "4.0"}, "WebKit": {"6.0"}, "WebKit2": {"4.1"}})
        tk = select_toolkit(available)
        self.assertIsNotNone(tk)
        self.assertTrue(tk.is_gtk4)
        self.assertEqual((tk.gtk_version, tk.webkit_namespace, tk.webkit_version), ("4.0", "WebKit", "6.0"))

    def test_falls_back_to_gtk3_webkit41(self):
        available = _fake_available({"Gtk": {"3.0", "4.0"}, "WebKit2": {"4.1", "4.0"}})
        tk = select_toolkit(available)
        self.assertFalse(tk.is_gtk4)
        self.assertEqual(tk.webkit_version, "4.1")

    def test_falls_back_to_webkit40(self):
        available = _fake_available({"Gtk": {"3.0"}, "WebKit2": {"4.0"}})
        tk = select_toolkit(available)
        self.assertEqual((tk.gtk_version, tk.webkit_version), ("3.0", "4.0"))

    def test_none_when_no_webkit(self):
        available = _fake_available({"Gtk": {"3.0", "4.0"}})
        self.assertIsNone(select_toolkit(available))

    def test_none_when_nothing_installed(self):
        self.assertIsNone(select_toolkit(_fake_available({})))

    def test_available_toolkits_are_ordered(self):
        available = _fake_available({"Gtk": {"3.0", "4.0"}, "WebKit": {"6.0"}, "WebKit2": {"4.1", "4.0"}})
        order = [(t.gtk_version, t.webkit_version) for t in available_toolkits(available)]
        self.assertEqual(order, [("4.0", "6.0"), ("3.0", "4.1"), ("3.0", "4.0")])


class RunGtkFallbackTests(unittest.TestCase):
    def test_run_gtk_falls_back_to_browser_without_toolkit(self):
        calls = {}

        def fake_browser(url):
            calls["url"] = url
            return 0

        orig_select = main.select_toolkit
        orig_browser = main.run_browser
        main.select_toolkit = lambda: None
        main.run_browser = fake_browser
        try:
            rc = main.run_gtk("http://127.0.0.1:9/", kiosk=False, start_fullscreen=False)
        finally:
            main.select_toolkit = orig_select
            main.run_browser = orig_browser
        self.assertEqual(rc, 0)
        self.assertEqual(calls["url"], "http://127.0.0.1:9/")


if __name__ == "__main__":
    unittest.main()
