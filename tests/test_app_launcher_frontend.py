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
        app_launcher_match = re.search(
            r'<div id="page-app-launcher"(?:\s|>)[^>]*>.*?(?=\s*<!--\s*──)',
            cls.html,
            re.S,
        )
        cls.app_launcher_page = app_launcher_match.group(0) if app_launcher_match else ""

    def assert_html_pattern(self, pattern):
        self.assertRegex(self.html, re.compile(pattern, re.S))

    def assert_render_summary_pattern(self, pattern):
        self.assert_html_pattern(
            r'function renderAppLauncherCardSummary\(type,\s*items\)\s*{'
            r'(?:(?!\nfunction\s+\w+\().)*?'
            + pattern
        )

    def assert_page_title_entry(self, page_name, title):
        escaped_page_name = re.escape(page_name)
        escaped_title = re.escape(title)

        self.assert_html_pattern(
            rf'const\s+pageTitles\s*=\s*{{'
            rf'(?:(?!;).)*?'
            rf'[\'\"]?{escaped_page_name}[\'\"]?\s*:\s*[\'\"]{escaped_title}[\'\"]'
        )

    def launcher_card_block(self, card_id):
        start = self.html.index(f'id="{card_id}"')
        next_card = re.search(
            r'id="launcher-(?:wordpress|laravel|codeigniter|php-projects)"',
            self.html[start + 1:],
        )
        app_end = self.html.index('id="launcher-recent-projects"')
        end = start + 1 + next_card.start() if next_card else app_end
        return self.html[start:end]

    def recent_projects_section(self):
        start = self.html.index('id="launcher-recent-projects"')
        end = self.html.index('<!-- ── NGINX', start)
        return self.html[start:end]

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

    def test_cards_keep_counts_and_recent_containers_move_below_cards(self):
        self.assertIn('id="launcher-recent-projects"', self.html)
        recent_section = self.recent_projects_section()

        for app_type, card_id, label, port, _, noun in self.LAUNCHER_APPS:
            card_block = self.launcher_card_block(card_id)

            self.assertIn(card_id, self.html)
            self.assertIn(label, card_block)
            self.assertIn(f"Starts near {port}", card_block)
            self.assertIn(f'id="launcher-{app_type}-count"', card_block)
            self.assertNotIn(f'id="launcher-{app_type}-recent"', card_block)
            self.assertIn(f'id="launcher-{app_type}-recent"', recent_section)
            self.assertIn(noun, self.html)

    def test_recent_projects_section_is_grouped_by_app_type(self):
        recent_section = self.recent_projects_section()

        for text in [
            "Recent Projects",
            "WordPress",
            "Laravel",
            "CodeIgniter",
            "PHP Projects",
            "No WordPress sites yet",
            "No Laravel apps yet",
            "No CodeIgniter apps yet",
            "No PHP projects yet",
        ]:
            self.assertIn(text, recent_section)

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

        self.assert_html_pattern(
            r'function appLauncherCreate\([^)]*\)\s*{'
            r'(?:(?!function appLauncherManage\().)*?'
            r'openAppLauncherTarget\(\s*type\s*,\s*[^)]*\)'
        )
        self.assert_html_pattern(
            r'function appLauncherManage\([^)]*\)\s*{'
            r'(?:(?!function\s+\w+\().)*?'
            r'openAppLauncherTarget\(\s*type\s*,\s*[^)]*\)'
        )

    def test_app_launcher_page_has_no_destructive_delete_actions(self):
        self.assertTrue(self.app_launcher_page, "App Launcher page block not found")

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

    def test_show_page_falls_back_to_app_launcher_for_hidden_app_routes(self):
        self.assert_html_pattern(
            r'const\s+appLauncherPageTypes\s*=\s*\[\s*'
            r'[\'\"]wordpress[\'\"]\s*,\s*'
            r'[\'\"]laravel[\'\"]\s*,\s*'
            r'[\'\"]codeigniter[\'\"]\s*,\s*'
            r'[\'\"]php-projects[\'\"]\s*\]'
        )
        self.assert_html_pattern(
            r'function isAppLauncherPage\(name\)\s*{\s*'
            r'return appLauncherPageTypes\.includes\(name\);\s*'
            r'}'
        )
        self.assert_html_pattern(
            r'function showPage\(name,\s*el\)\s*{'
            r'(?:(?!\nfunction\s+\w+\().)*?'
            r'const\s+link\s*=\s*document\.querySelector\(`\.sidebar-nav a\[href="#\$\{name\}"\]`\);'
            r'(?:(?!\nfunction\s+\w+\().)*?'
            r'if\s*\(link\)\s*link\.classList\.add\([\'\"]active[\'\"]\);'
            r'\s*else\s+if\s*\(isAppLauncherPage\(name\)\)\s*'
            r'appLauncherLink\(\)\?\.classList\.add\([\'\"]active[\'\"]\);'
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

    def test_app_launcher_summary_renders_counts_and_recent_item_details(self):
        function_body = r'(?:(?!\nfunction\s+\w+\().)*?'

        self.assert_html_pattern(
            r'function renderAppLauncherCardSummary\(type,\s*items\)\s*{'
            rf'(?={function_body}launcher-\$\{{type\}}-count`)'
            rf'(?={function_body}\.textContent)'
            rf'(?={function_body}items\.length)'
            rf'{function_body}'
        )
        self.assert_html_pattern(
            r'function renderAppLauncherCardSummary\(type,\s*items\)\s*{'
            rf'(?={function_body}\.slice\(\s*0\s*,\s*3\s*\))'
            rf'(?={function_body}item\.name)'
            rf'(?={function_body}launcherItemUrl\(\s*item\s*\))'
            rf'(?={function_body}launcherItemMeta\(\s*item\s*\))'
            rf'(?={function_body}recentEl\.innerHTML)'
            rf'{function_body}'
        )

    def test_launcher_recent_items_render_manage_actions(self):
        self.assert_render_summary_pattern(r'document\.getElementById\(`launcher-\$\{type\}-recent`\)')
        self.assert_render_summary_pattern(r'appLauncherManage\(type\)')
        self.assert_render_summary_pattern(r'\bManage\b')

        recent_section = self.recent_projects_section()
        for app_type, _, _, _, _, _ in self.LAUNCHER_APPS:
            self.assertIn(f'id="launcher-{app_type}-recent"', recent_section)

    def test_launcher_recent_open_links_use_noopener_noreferrer(self):
        self.assert_render_summary_pattern(
            r'target="_blank"\s+rel="noopener noreferrer">Open</a>'
        )


if __name__ == "__main__":
    unittest.main()
