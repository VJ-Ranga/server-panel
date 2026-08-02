import os
import tempfile
import unittest
from unittest import mock


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import sys
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import panel


class InstalledListTimestampsBackendTests(unittest.TestCase):
    def test_wordpress_sites_include_modified_at(self):
        with tempfile.TemporaryDirectory() as tmp:
            site_path = os.path.join(tmp, "newsite")
            os.makedirs(site_path)
            wp_config = os.path.join(site_path, "wp-config.php")
            with open(wp_config, "w") as f:
                f.write("define('DB_NAME', 'newsite_db');\ndefine('DB_USER', 'newsite_user');\n$table_prefix = 'wp_';\n")

            with mock.patch.object(panel.glob, "glob", side_effect=[[wp_config], [], [], [], [], [], []]), \
                 mock.patch.object(panel, "detect_wp_admin_users", return_value=[]), \
                 mock.patch.object(panel, "find_nginx_site_for_path", return_value="newsite"), \
                 mock.patch.object(panel, "get_nginx_site_port", return_value=8099):
                sites = panel.get_wp_sites()

        self.assertEqual(len(sites), 1)
        self.assertIn("modified_at", sites[0])
        self.assertGreater(sites[0]["modified_at"], 0)

    def test_wordpress_discovery_includes_home_local_pattern(self):
        patterns = []

        def fake_glob(pattern):
            patterns.append(pattern)
            return []

        with mock.patch.object(panel.glob, "glob", side_effect=fake_glob):
            panel.get_wp_sites()

        self.assertTrue(any("/local/*/wp-config.php" in pattern for pattern in patterns))


if __name__ == "__main__":
    unittest.main()
