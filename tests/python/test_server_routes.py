from __future__ import annotations

import unittest

from lmdesktopplus.server import RequestHandler


class ServerRouteTableTests(unittest.TestCase):
    def test_post_routes_cover_known_endpoints(self):
        expected = {
            "/api/v1/settings",
            "/api/v1/action",
            "/api/v1/agents/launch",
            "/api/v1/media",
            "/api/v1/network/connect",
            "/api/v1/network/disconnect",
        }
        self.assertEqual(set(RequestHandler.POST_ROUTES), expected)
        for name in RequestHandler.POST_ROUTES.values():
            self.assertTrue(callable(getattr(RequestHandler, name)))

    def test_post_prefix_includes_adapter(self):
        prefixes = [prefix for prefix, _name in RequestHandler.POST_PREFIX_ROUTES]
        self.assertIn("/api/v1/adapter/", prefixes)
        for _prefix, name in RequestHandler.POST_PREFIX_ROUTES:
            self.assertTrue(callable(getattr(RequestHandler, name)))

    def test_get_routes_and_prefixes(self):
        self.assertIn("/api/v1/network/scan", RequestHandler.GET_ROUTES)
        prefixes = [prefix for prefix, _auth, _name in RequestHandler.GET_PREFIX_ROUTES]
        self.assertIn("/api/v1/state", prefixes)
        self.assertIn("/wallpaper-thumbs/", prefixes)
        for _path, _auth, name in [
            *[(p, a, n) for p, (a, n) in RequestHandler.GET_ROUTES.items()],
            *RequestHandler.GET_PREFIX_ROUTES,
        ]:
            self.assertTrue(callable(getattr(RequestHandler, name)))


if __name__ == "__main__":
    unittest.main()
