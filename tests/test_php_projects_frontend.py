import os
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class PhpProjectsFrontendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(PROJECT_ROOT, "index.html"), encoding="utf-8") as f:
            cls.html = f.read()

    def test_sidebar_page_and_titles_exist(self):
        for text in [
            "showPage('php-projects',this)",
            'id="page-php-projects"',
            "'php-projects':'PHP Projects'",
            "loadPhpProjects(); loadPhpProjectNextPort();",
        ]:
            self.assertIn(text, self.html)

    def test_create_form_fields_exist(self):
        for field_id in [
            "php-site-name",
            "php-install-path",
            "php-template",
            "php-port",
            "php-port-preview",
            "php-db-fields",
            "php-db-name",
            "php-db-user",
            "php-db-pass",
            "php-install-btn",
            "php-install-log",
            "php-install-result",
            "php-result-url",
            "php-projects-container",
        ]:
            self.assertIn(field_id, self.html)

    def test_javascript_api_functions_exist(self):
        for function_name in [
            "function phpProjectAutoFill()",
            "function togglePhpProjectDbFields()",
            "function genPhpProjectDbPass()",
            "async function loadPhpProjectNextPort()",
            "async function loadPhpProjects()",
            "async function startPhpProjectInstall()",
            "async function changePhpProjectPort(",
            "async function deletePhpProject(",
        ]:
            self.assertIn(function_name, self.html)

        for route in [
            "/api/php-projects/apps",
            "/api/php-projects/next_port",
            "/api/php-projects/install",
            "/api/php-projects/port",
            "/api/php-projects/delete/",
        ]:
            self.assertIn(route, self.html)


if __name__ == "__main__":
    unittest.main()
