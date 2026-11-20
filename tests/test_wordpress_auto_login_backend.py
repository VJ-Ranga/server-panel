import os
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class WordPressAutoLoginBackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(PROJECT_ROOT, "panel.py")) as f:
            cls.source = f.read()
        with open(os.path.join(PROJECT_ROOT, "wp-install-helper.sh")) as f:
            cls.helper = f.read()
        with open(os.path.join(PROJECT_ROOT, "wp-auto-login-plugin.php")) as f:
            cls.plugin = f.read()

    def test_backend_exposes_lifecycle_and_token_routes(self):
        self.assertIn('path == "/api/wordpress/auto-login"', self.source)
        self.assertIn('path == "/api/wordpress/auto-login/token"', self.source)
        self.assertIn('"--auto-login-install"', self.helper)
        self.assertIn('"--auto-login-remove"', self.helper)

    def test_helper_validates_path_before_plugin_operations(self):
        block = self.helper.split('if [ "$INSTALL_PATH" = "--auto-login-install" ]', 1)[1]
        self.assertIn('is_safe_wp_path "$INSTALL_PATH"', block)
        self.assertIn('wp-config.php', block)
        self.assertIn('rm -rf "$PLUGIN_DIR"', block)

    def test_token_flow_uses_short_lived_native_login(self):
        self.assertIn("set_transient", self.plugin)
        self.assertIn("create_wp_auto_login_token", self.source)
        self.assertIn("wp_set_auth_cookie", self.plugin)

    def test_auto_login_php_uses_variable_that_wordpress_cannot_overwrite(self):
        self.assertIn('$server_panel_path = {repr(install_path)};', self.source)
        self.assertNotIn('$path = {repr(install_path)};', self.source)


if __name__ == "__main__":
    unittest.main()
