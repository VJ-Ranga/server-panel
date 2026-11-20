import os
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class WordPressAutoLoginFrontendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(PROJECT_ROOT, "index.html")) as f:
            cls.source = f.read()

    def test_site_cards_have_plugin_lifecycle_controls(self):
        self.assertIn("setWpAutoLogin", self.source)
        self.assertIn("Enable Auto Login", self.source)
        self.assertIn("Disable Auto Login", self.source)
        self.assertIn("Remove Login Plugin", self.source)

    def test_auto_login_requests_one_time_token_without_password(self):
        body = self.source.split("async function autoLoginWP(index)")[1].split("function setWpLoginUser", 1)[0]
        self.assertIn("/api/wordpress/auto-login/token", body)
        self.assertIn("install_path: creds.path", body)
        self.assertNotIn("password", body)


if __name__ == "__main__":
    unittest.main()
