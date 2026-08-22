import getpass
import os
import re
import subprocess
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HELPER_PATH = os.path.join(PROJECT_ROOT, "wp-install-helper.sh")


class WordpressCustomPathTests(unittest.TestCase):
    def run_safe_path_check(self, path, panel_user=None):
        with open(HELPER_PATH) as f:
            helper = f.read()
        match = re.search(r"is_safe_wp_path\(\) \{.*?\n\}", helper, re.S)
        self.assertIsNotNone(match, "wp helper safe path function not found")
        script = f"{match.group(0)}\nis_safe_wp_path {path!r}\n"
        env = os.environ.copy()
        env["PANEL_USER"] = panel_user or getpass.getuser()
        return subprocess.run(["bash", "-c", script], env=env, check=False)

    def test_wp_helper_allows_current_user_local_custom_path(self):
        user = getpass.getuser()

        result = self.run_safe_path_check(f"/home/{user}/local/test", user)

        self.assertEqual(result.returncode, 0)

    def test_wp_helper_rejects_other_user_local_custom_path(self):
        user = getpass.getuser()

        result = self.run_safe_path_check("/home/someone-else/local/test", user)

        self.assertNotEqual(result.returncode, 0)

    def test_wp_helper_grants_www_data_traverse_access_for_home_local_paths(self):
        with open(HELPER_PATH) as f:
            helper = f.read()

        self.assertIn("ensure_www_data_home_access", helper)
        self.assertIn("setfacl -m u:www-data:--x", helper)
        self.assertIn("/home/\"$PANEL_USER\"", helper)

    def test_wp_helper_normalizes_wp_content_for_plugin_updates(self):
        with open(HELPER_PATH) as f:
            helper = f.read()

        self.assertIn("set_wp_update_perms", helper)
        self.assertIn('chown -R www-data:www-data "$INSTALL_PATH/wp-content"', helper)
        self.assertIn('find "$INSTALL_PATH/wp-content" -type d -exec chmod 2775 {} \\;', helper)


if __name__ == "__main__":
    unittest.main()
