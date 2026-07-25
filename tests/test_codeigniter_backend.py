import inspect
import os
import sys
import tempfile
import unittest
from unittest import mock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import panel


class CodeIgniterBackendTests(unittest.TestCase):
    def test_discovers_codeigniter_apps_from_spark_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            app_path = os.path.join(tmp, "ciapp")
            os.makedirs(app_path)
            open(os.path.join(app_path, "spark"), "w").close()
            with open(os.path.join(app_path, ".env"), "w") as f:
                f.write('\n'.join([
                    'app.baseURL="http://localhost:8200/"',
                    'database.default.database="ciapp_db"',
                    'database.default.username="ciapp_user"',
                    'database.default.password="ciapp_pass"',
                ]))

            with mock.patch.object(panel.glob, "glob", return_value=[os.path.join(app_path, "spark")]), \
                 mock.patch.object(panel, "find_nginx_site_for_path", return_value="ciapp"), \
                 mock.patch.object(panel, "get_nginx_site_port", return_value=8200), \
                 mock.patch.object(panel, "run_cmd", return_value={"success": True, "stdout": "CodeIgniter v4.5.0\n", "stderr": ""}):
                apps = panel.get_codeigniter_apps()

        self.assertEqual(len(apps), 1)
        self.assertEqual(apps[0]["name"], "ciapp")
        self.assertEqual(apps[0]["path"], app_path)
        self.assertEqual(apps[0]["app_url"], "http://localhost:8200/")
        self.assertEqual(apps[0]["db_name"], "ciapp_db")
        self.assertEqual(apps[0]["db_user"], "ciapp_user")
        self.assertEqual(apps[0]["db_pass"], "ciapp_pass")
        self.assertEqual(apps[0]["nginx_site"], "ciapp")
        self.assertEqual(apps[0]["port"], 8200)
        self.assertEqual(apps[0]["version"], "CodeIgniter v4.5.0")

    def test_handler_declares_codeigniter_routes(self):
        source = inspect.getsource(panel.Handler)
        for route in [
            "/api/codeigniter/apps",
            "/api/codeigniter/next_port",
            "/api/codeigniter/install",
            "/api/codeigniter/port",
            "/api/codeigniter/install/",
            "/api/codeigniter/delete/",
        ]:
            self.assertIn(route, source)


if __name__ == "__main__":
    unittest.main()
