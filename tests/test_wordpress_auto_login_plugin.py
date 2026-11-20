import os
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN_PATH = os.path.join(PROJECT_ROOT, "wp-auto-login-plugin.php")


class WordPressAutoLoginPluginTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(PLUGIN_PATH) as f:
            cls.source = f.read()

    def test_plugin_uses_one_time_transient_tokens(self):
        self.assertIn("set_transient", self.source)
        self.assertIn("delete_transient", self.source)
        self.assertIn("60", self.source)

    def test_plugin_sets_native_wordpress_cookie(self):
        self.assertIn("wp_set_auth_cookie", self.source)
        self.assertIn("wp_safe_redirect", self.source)

    def test_plugin_does_not_accept_passwords(self):
        self.assertNotIn("$_POST['pwd']", self.source)
        self.assertNotIn('$_POST["pwd"]', self.source)


if __name__ == "__main__":
    unittest.main()
