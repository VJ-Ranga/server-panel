import os
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class AppLauncherFrontendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(PROJECT_ROOT, "index.html"), encoding="utf-8") as f:
            cls.html = f.read()

    def test_sidebar_page_and_title_exist(self):
        for text in [
            "showPage('app-launcher',this)",
            'id="page-app-launcher"',
            "'app-launcher':'App Launcher'",
        ]:
            self.assertIn(text, self.html)

    def test_all_launcher_cards_exist(self):
        for card_id in [
            "launcher-wordpress",
            "launcher-laravel",
            "launcher-codeigniter",
            "launcher-php-projects",
        ]:
            self.assertIn(card_id, self.html)

        for label in [
            "WordPress",
            "Laravel",
            "CodeIgniter",
            "PHP Project",
            "Starts near 8090",
            "Starts near 8100",
            "Starts near 8200",
            "Starts near 8300",
        ]:
            self.assertIn(label, self.html)

    def test_navigation_helpers_exist_and_target_existing_pages(self):
        for function_name in [
            "function openAppLauncherTarget(",
            "function appLauncherCreate(",
            "function appLauncherManage(",
        ]:
            self.assertIn(function_name, self.html)

        for target in [
            "wordpress",
            "laravel",
            "codeigniter",
            "php-projects",
            "install",
            "sites",
            "apps",
        ]:
            self.assertIn(target, self.html)


if __name__ == "__main__":
    unittest.main()
