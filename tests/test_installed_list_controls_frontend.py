import os
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class InstalledListControlsFrontendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(PROJECT_ROOT, "index.html"), encoding="utf-8") as f:
            cls.html = f.read()

    def test_all_installed_lists_have_search_sort_clear_and_count_controls(self):
        for prefix in ["wordpress", "laravel", "codeigniter", "php-projects"]:
            for text in [
                f'id="{prefix}-list-search"',
                f'id="{prefix}-list-sort"',
                f'id="{prefix}-list-count"',
                f"clearAppListSearch('{prefix}')",
            ]:
                self.assertIn(text, self.html)

    def test_sort_options_exist(self):
        for value in ["newest", "oldest", "name_asc", "name_desc", "port_asc", "port_desc"]:
            self.assertIn(f'value="{value}"', self.html)

    def test_shared_list_control_functions_exist(self):
        for function_name in [
            "function renderAppListControls(",
            "function filterAndSortApps(",
            "function renderAppListCount(",
            "function clearAppListSearch(",
        ]:
            self.assertIn(function_name, self.html)


if __name__ == "__main__":
    unittest.main()
