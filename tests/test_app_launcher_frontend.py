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
        app_launcher_start = cls.html.index('<div id="page-app-launcher"')
        app_launcher_end = cls.html.index('<!-- ── NGINX', app_launcher_start)
        cls.app_launcher_page = cls.html[app_launcher_start:app_launcher_end]

    def assert_html_pattern(self, pattern):
        self.assertRegex(self.html, re.compile(pattern, re.S))

    def assert_page_title_entry(self, page_name, title):
        escaped_page_name = re.escape(page_name)
        escaped_title = re.escape(title)

        self.assert_html_pattern(
            rf'const\s+pageTitles\s*=\s*{{'
            rf'(?:(?!;).)*?'
            rf'[\'\"]?{escaped_page_name}[\'\"]?\s*:\s*[\'\"]{escaped_title}[\'\"]'
        )

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

        for app_type in ["wordpress", "laravel", "codeigniter", "php-projects"]:
            self.assertNotRegex(
                self.sidebar,
                re.compile(rf"showPage\(\s*['\"]{re.escape(app_type)}['\"]"),
            )

        nav_sections = re.findall(
            r'<div class="nav-section">\s*([^<]+?)\s*</div>',
            self.sidebar,
        )
        self.assertEqual(["Overview", "Server", "System"], nav_sections)
        self.assertNotIn("Services", nav_sections)
        self.assertNotIn("Applications", nav_sections)

        for page_name, title in [
            ("wordpress", "WordPress"),
            ("laravel", "Laravel"),
            ("codeigniter", "CodeIgniter"),
            ("php-projects", "PHP Projects"),
        ]:
            self.assert_page_title_entry(page_name, title)

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
                rf'(?:(?!function appLauncherManage\().)*?'
                rf'(?:const|let)\s+(?P<target_var>\w+)\s*=\s*\w+\s*\[\s*type\s*\]\s*;'
                rf'(?:(?!function appLauncherManage\().)*?'
                rf'openAppLauncherTarget\(\s*type\s*,\s*(?P=target_var)\s*\)'
            )
            self.assert_html_pattern(
                rf'function appLauncherManage\([^)]*\)\s*{{'
                rf'(?:(?!function\s+\w+\().)*?'
                rf'[\'\"]{escaped_app_type}[\'\"]\s*:\s*[\'\"]{escaped_manage_tab}[\'\"]'
                rf'(?:(?!function\s+\w+\().)*?'
                rf'(?:const|let)\s+(?P<target_var>\w+)\s*=\s*\w+\s*\[\s*type\s*\]\s*;'
                rf'(?:(?!function\s+\w+\().)*?'
                rf'openAppLauncherTarget\(\s*type\s*,\s*(?P=target_var)\s*\)'
            )

    def test_app_launcher_page_has_no_destructive_delete_actions(self):
        actions = re.findall(
            r'<(?:button|a)\b[^>]*>.*?</(?:button|a)>',
            self.app_launcher_page,
            re.S | re.I,
        )

        for action in actions:
            self.assertNotRegex(
                action,
                re.compile(r'\bdelete\b|apiDelete\(|btn-danger|bi-trash', re.I),
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

    def test_launcher_recent_items_render_manage_actions(self):
        self.assert_html_pattern(
            r'function renderAppLauncherCardSummary\(type,\s*items\)\s*{'
            r'(?:(?!function\s+\w+\().)*?'
            r'document\.getElementById\(`launcher-\$\{type\}-recent`\)'
            r'(?:(?!function\s+\w+\().)*?'
            r'appLauncherManage\(type\)'
            r'(?:(?!function\s+\w+\().)*?'
            r'\bManage\b'
        )

        for app_type, card_id, _, _, _, _ in self.LAUNCHER_APPS:
            escaped_app_type = re.escape(app_type)
            escaped_card_id = re.escape(card_id)

            self.assert_html_pattern(
                rf'id="{escaped_card_id}"{self.LAUNCHER_CARD_BOUNDARY}'
                rf'id="launcher-{escaped_app_type}-recent"'
            )


if __name__ == "__main__":
    unittest.main()
