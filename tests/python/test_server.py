from __future__ import annotations

import json
import urllib.error
import urllib.request
import unittest

from lmdesktopplus.server import start_server


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.server, self.thread, self.url = start_server()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(self, path, token=None, body=None):
        headers = {}
        if token is not None:
            headers["X-LMDP-Token"] = token
        data = None
        method = "GET"
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
            method = "POST"
        req = urllib.request.Request(self.url.rstrip("/") + path, data=data, headers=headers, method=method)
        return urllib.request.urlopen(req, timeout=10)

    def test_index_injects_token(self):
        with self.request("/") as response:
            text = response.read().decode()
        self.assertIn(self.server.token, text)
        self.assertNotIn("__LMDP_TOKEN__", text)


    def test_digitalvapor_assets_are_served(self):
        for path, marker in (("/digitalvapor.css", "--dv-accent"), ("/digitalvapor.js", "Digitalvapor")):
            with self.request(path) as response:
                text = response.read().decode()
            self.assertIn(marker, text)

    def test_index_uses_csp_compatible_token_metadata(self):
        with self.request("/") as response:
            text = response.read().decode()
        self.assertIn('name="lmdp-token"', text)
        self.assertNotIn("window.LMDP_TOKEN", text)
        self.assertIn("digitalvapor.css", text)
        self.assertIn("digitalvapor.js", text)

    def test_api_rejects_missing_token(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.request("/api/v1/state")
        self.assertEqual(ctx.exception.code, 401)

    def test_state_and_allowlisted_action(self):
        with self.request("/api/v1/state", self.server.token) as response:
            payload = json.load(response)
        self.assertIn("metrics", payload)
        self.assertIn("assets", payload)
        self.assertIn("audio", payload["adapters"])
        self.assertIn("audio.volume", payload["assets"]["icons"])
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.request("/api/v1/action", self.server.token, {"action": "launch", "target": "not-real"})
        self.assertEqual(ctx.exception.code, 400)

    def test_adapter_command_route_dispatches_allowlisted_command(self):
        class StubAdapter:
            id = "stub"

            def available(self):
                return True

            def snapshot(self):
                return {"available": True}

            def command(self, name, payload):
                if name != "ping":
                    return {"ok": False, "error": "unknown stub command"}
                return {"ok": True, "value": payload.get("value")}

        self.server.state.adapters.register(StubAdapter())
        with self.request(
            "/api/v1/adapter/stub",
            self.server.token,
            {"name": "ping", "payload": {"value": 7}},
        ) as response:
            self.assertEqual(json.load(response), {"ok": True, "value": 7})

        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.request(
                "/api/v1/adapter/stub",
                self.server.token,
                {"name": "unknown", "payload": {}},
            )
        self.assertEqual(ctx.exception.code, 400)

    def test_adapter_command_route_rejects_unknown_adapter(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.request(
                "/api/v1/adapter/not-real",
                self.server.token,
                {"name": "anything", "payload": {}},
            )
        self.assertEqual(ctx.exception.code, 404)

    def test_icon_assets_are_served(self):
        with self.request("/icons/volume.svg") as response:
            text = response.read().decode()
        self.assertIn("<svg", text)
        self.assertIn("currentColor", text)

    def test_icon_path_traversal_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.request("/icons/../app.js")
        self.assertEqual(ctx.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
