import os
import re
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class AppLauncherFrontendTests(unittest.TestCase):
    LAUNCHER_APPS = [
        ("wordpress", "launcher-wordpress", "WordPress", "8090", "sites"),
        ("laravel", "launcher-laravel", "Laravel", "8100", "apps"),
        ("codeigniter", "launcher-codeigniter", "CodeIgniter", "8200", "apps"),
        ("php-projects", "launcher-php-projects", "PHP Project", "8300", "apps"),
    ]
    LAUNCHER_CARD_BOUNDARY = (
        r'(?:(?!id="launcher-(?:wordpress|laravel|codeigniter|php-projects)").)*?'
    )

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(PROJECT_ROOT, "index.html"), encoding="utf-8") as f:
            cls.html = f.read()

    def assert_html_pattern(self, pattern):
        self.assertRegex(self.html, re.compile(pattern, re.S))

    def test_sidebar_page_and_title_exist(self):
        for text in [
            "showPage('app-launcher',this)",
            'id="page-app-launcher"',
            "'app-launcher':'App Launcher'",
        ]:
            self.assertIn(text, self.html)

    def test_all_launcher_cards_exist(self):
        for _, card_id, _, _, _ in self.LAUNCHER_APPS:
            self.assertIn(card_id, self.html)

        for _, _, label, port, _ in self.LAUNCHER_APPS:
            self.assertIn(label, self.html)
            self.assertIn(f"Starts near {port}", self.html)

    def test_launcher_cards_have_create_and_manage_actions(self):
        for app_type, card_id, _, _, _ in self.LAUNCHER_APPS:
            escaped_app_type = re.escape(app_type)
            escaped_card_id = re.escape(card_id)

            self.assert_html_pattern(
                rf'id="{escaped_card_id}"{self.LAUNCHER_CARD_BOUNDARY}'
                rf'<button\b[^>]*onclick="appLauncherCreate\(\'{escaped_app_type}\'\)"[^>]*>'
                rf'.*?\bCreate\b.*?</button>'
            )
            self.assert_html_pattern(
                rf'id="{escaped_card_id}"{self.LAUNCHER_CARD_BOUNDARY}'
                rf'<button\b[^>]*onclick="appLauncherManage\(\'{escaped_app_type}\'\)"[^>]*>'
                rf'.*?\bManage\b.*?</button>'
            )

    def test_launcher_create_and_manage_mappings_target_expected_tabs(self):
        for app_type, _, _, _, manage_tab in self.LAUNCHER_APPS:
            escaped_app_type = re.escape(app_type)
            escaped_manage_tab = re.escape(manage_tab)

            self.assert_html_pattern(
                rf'function appLauncherCreate\([^)]*\)\s*{{'
                rf'(?:(?!function appLauncherManage\().)*?'
                rf'[\'\"]{escaped_app_type}[\'\"]\s*:\s*[\'\"]install[\'\"]'
            )
            self.assert_html_pattern(
                rf'function appLauncherManage\([^)]*\)\s*{{'
                rf'(?:(?!function\s+\w+\().)*?'
                rf'[\'\"]{escaped_app_type}[\'\"]\s*:\s*[\'\"]{escaped_manage_tab}[\'\"]'
            )

    def test_navigation_helpers_exist_and_target_existing_pages(self):
        for function_name in [
            "function openAppLauncherTarget(",
            "function appLauncherCreate(",
            "function appLauncherManage(",
        ]:
            self.assertIn(function_name, self.html)

        self.assert_html_pattern(
            r'function openAppLauncherTarget\(appType,\s*tabName\)\s*{'
            r'.*?showPage\(appType,'
            r'.*?switchTab\(appType,\s*tabName,'
        )


if __name__ == "__main__":
    unittest.main()
