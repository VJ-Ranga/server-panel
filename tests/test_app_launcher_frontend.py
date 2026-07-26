import os
import re
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class AppLauncherFrontendTests(unittest.TestCase):
    LAUNCHER_APPS = [
        ("wordpress", "launcher-wordpress", "WordPress", "8090", "sites", "sites"),
        ("laravel", "launcher-laravel", "Laravel", "8100", "apps", "apps"),
        ("codeigniter", "launcher-codeigniter", "CodeIgniter", "8200", "apps", "apps"),
        ("php-projects", "launcher-php-projects", "PHP Project", "8300", "apps", "projects"),
    ]
    LAUNCHER_CARD_BOUNDARY = (
        r'(?:(?!id="launcher-(?:wordpress|laravel|codeigniter|php-projects)").)*?'
    )

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(PROJECT_ROOT, "index.html"), encoding="utf-8") as f:
            cls.html = f.read()
        sidebar_start = cls.html.index('<nav class="sidebar-nav')
        sidebar_end = cls.html.index('</nav>', sidebar_start)
        cls.sidebar = cls.html[sidebar_start:sidebar_end]

    def assert_html_pattern(self, pattern):
        self.assertRegex(self.html, re.compile(pattern, re.S))

    def test_sidebar_keeps_app_launcher_and_hides_app_pages(self):
        for text in [
            "showPage('app-launcher',this)",
            'id="page-app-launcher"',
            "'app-launcher':'App Launcher'",
        ]:
            self.assertIn(text, self.html)

        for hidden_href in [
            'href="#wordpress"',
            'href="#laravel"',
            'href="#codeigniter"',
            'href="#php-projects"',
        ]:
            self.assertNotIn(hidden_href, self.sidebar)

        for text in ["Server", "Nginx", "MySQL", "phpMyAdmin", "Performance", "System", "Settings"]:
            self.assertIn(text, self.sidebar)

    def test_all_launcher_cards_have_dashboard_placeholders(self):
        for app_type, card_id, label, port, _, noun in self.LAUNCHER_APPS:
            self.assertIn(card_id, self.html)
            self.assertIn(label, self.html)
            self.assertIn(f"Starts near {port}", self.html)
            self.assertIn(f'id="launcher-{app_type}-count"', self.html)
            self.assertIn(f'id="launcher-{app_type}-recent"', self.html)
            self.assertIn(noun, self.html)

    def test_launcher_cards_have_create_and_view_all_actions(self):
        for app_type, card_id, _, _, _, _ in self.LAUNCHER_APPS:
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
                rf'.*?\bView All\b.*?</button>'
            )

    def test_launcher_create_and_manage_mappings_target_expected_tabs(self):
        for app_type, _, _, _, manage_tab, _ in self.LAUNCHER_APPS:
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

    def test_navigation_helpers_do_not_require_hidden_sidebar_links(self):
        for function_name in [
            "function appLauncherLink(",
            "function openAppLauncherTarget(",
            "function appLauncherCreate(",
            "function appLauncherManage(",
        ]:
            self.assertIn(function_name, self.html)

        self.assert_html_pattern(
            r'function openAppLauncherTarget\(appType,\s*tabName\)\s*{'
            r'.*?showPage\(appType,\s*appLauncherLink\(\)\)'
            r'.*?switchTab\(appType,\s*tabName,'
        )

    def test_app_launcher_summary_functions_use_existing_apis(self):
        for function_name in [
            "async function loadAppLauncherSummary(",
            "function renderAppLauncherCardSummary(",
            "function launcherItemUrl(",
            "function launcherItemMeta(",
        ]:
            self.assertIn(function_name, self.html)

        for api_path in [
            "/api/wordpress/sites",
            "/api/laravel/apps",
            "/api/codeigniter/apps",
            "/api/php-projects/apps",
        ]:
            self.assertIn(api_path, self.html)

        self.assertIn(".slice(0, 3)", self.html)
        self.assertIn("appLauncherManage(type)", self.html)


if __name__ == "__main__":
    unittest.main()
