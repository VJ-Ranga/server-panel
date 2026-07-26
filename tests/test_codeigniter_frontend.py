import os
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class CodeIgniterFrontendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(PROJECT_ROOT, "index.html"), encoding="utf-8") as f:
            cls.html = f.read()

    def test_hidden_page_title_and_loaders_exist(self):
        for text in [
            'id="page-codeigniter"',
            "codeigniter:'CodeIgniter'",
            "loadCodeIgniterApps(); loadCodeIgniterNextPort();",
        ]:
            self.assertIn(text, self.html)

    def test_create_form_fields_exist(self):
        for field_id in [
            "ci-site-name",
            "ci-install-path",
            "ci-port",
            "ci-port-preview",
            "ci-db-name",
            "ci-db-user",
            "ci-db-pass",
            "ci-install-btn",
            "ci-install-log",
            "ci-install-result",
            "ci-result-url",
            "codeigniter-apps-container",
        ]:
            self.assertIn(field_id, self.html)

    def test_javascript_api_functions_exist(self):
        for function_name in [
            "function codeIgniterAutoFill()",
            "function genCodeIgniterDbPass()",
            "async function loadCodeIgniterNextPort()",
            "async function loadCodeIgniterApps()",
            "async function startCodeIgniterInstall()",
            "async function changeCodeIgniterPort(",
            "async function deleteCodeIgniterApp(",
        ]:
            self.assertIn(function_name, self.html)

        for route in [
            "/api/codeigniter/apps",
            "/api/codeigniter/next_port",
            "/api/codeigniter/install",
            "/api/codeigniter/port",
            "/api/codeigniter/delete/",
        ]:
            self.assertIn(route, self.html)


if __name__ == "__main__":
    unittest.main()
