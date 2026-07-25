import inspect
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import panel


class PhpProjectsBackendTests(unittest.TestCase):
    def test_discovers_panel_created_php_project_from_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            app_path = os.path.join(tmp, "plainphp")
            os.makedirs(app_path)
            meta_path = os.path.join(app_path, ".server-panel-project.json")
            with open(meta_path, "w") as f:
                json.dump({
                    "type": "php",
                    "name": "plainphp",
                    "template": "php_db",
                    "install_path": app_path,
                    "nginx_site": "plainphp",
                    "port": 8300,
                    "db_name": "plainphp_db",
                    "db_user": "plainphp_user",
                    "db_created": True,
                    "created_at": 123,
                }, f)

            with mock.patch.object(panel.glob, "glob", return_value=[meta_path]), \
                 mock.patch.object(panel, "find_nginx_site_for_path", return_value="plainphp"), \
                 mock.patch.object(panel, "get_nginx_site_port", return_value=8300):
                apps = panel.get_php_projects()

        self.assertEqual(len(apps), 1)
        self.assertEqual(apps[0]["name"], "plainphp")
        self.assertEqual(apps[0]["template"], "php_db")
        self.assertEqual(apps[0]["path"], app_path)
        self.assertEqual(apps[0]["db_name"], "plainphp_db")
        self.assertEqual(apps[0]["db_user"], "plainphp_user")
        self.assertTrue(apps[0]["db_created"])
        self.assertEqual(apps[0]["nginx_site"], "plainphp")
        self.assertEqual(apps[0]["port"], 8300)

    def test_template_generation_for_php_db_contains_config_and_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            metadata = {
                "type": "php",
                "name": "plainphp",
                "template": "php_db",
                "install_path": "/var/www/plainphp",
                "nginx_site": "plainphp",
                "port": 8300,
                "db_name": "plainphp_db",
                "db_user": "plainphp_user",
                "db_created": True,
                "created_at": 123,
            }
            panel.write_php_project_files(tmp, metadata, "secretpass")
            self.assertTrue(os.path.exists(os.path.join(tmp, "index.php")))
            self.assertTrue(os.path.exists(os.path.join(tmp, "config.php")))
            self.assertTrue(os.path.exists(os.path.join(tmp, ".server-panel-project.json")))
            with open(os.path.join(tmp, "config.php")) as f:
                config = f.read()
            self.assertIn("plainphp_db", config)
            self.assertIn("plainphp_user", config)
            self.assertIn("secretpass", config)

    def test_handler_declares_php_project_routes(self):
        source = inspect.getsource(panel.Handler)
        for route in [
            "/api/php-projects/apps",
            "/api/php-projects/next_port",
            "/api/php-projects/install",
            "/api/php-projects/port",
            "/api/php-projects/install/",
            "/api/php-projects/delete/",
        ]:
            self.assertIn(route, source)


if __name__ == "__main__":
    unittest.main()
