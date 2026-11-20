import os
import sys
import tempfile
import unittest
from unittest import mock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import panel


class AssetRouteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.assets = os.path.join(self.tmp.name, "assets")
        os.makedirs(os.path.join(self.assets, "fonts"))
        with open(os.path.join(self.assets, "fonts", "a.woff2"), "wb") as f:
            f.write(b"font")
        with open(os.path.join(self.assets, "notes.txt"), "w") as f:
            f.write("x")
        with open(os.path.join(self.tmp.name, "secret.png"), "wb") as f:
            f.write(b"png")
        self.patch = mock.patch.object(panel, "ASSETS_DIR", self.assets)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_serves_allowed_file_with_mime(self):
        path, mime = panel.resolve_asset("fonts/a.woff2")
        self.assertEqual(path, os.path.realpath(os.path.join(self.assets, "fonts", "a.woff2")))
        self.assertEqual(mime, "font/woff2")

    def test_rejects_traversal_outside_assets(self):
        self.assertEqual(panel.resolve_asset("../secret.png"), (None, None))
        self.assertEqual(panel.resolve_asset("/etc/passwd"), (None, None))

    def test_rejects_unlisted_types_and_missing_files(self):
        self.assertEqual(panel.resolve_asset("notes.txt"), (None, None))
        self.assertEqual(panel.resolve_asset("fonts/missing.woff2"), (None, None))

    def test_assets_route_is_checked_before_auth(self):
        import inspect
        src = inspect.getsource(panel.Handler.do_GET)
        self.assertLess(src.index('"/assets/"'), src.index("self.authed()"))


if __name__ == "__main__":
    unittest.main()
