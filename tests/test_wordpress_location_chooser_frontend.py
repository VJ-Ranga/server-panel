import os
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class WordpressLocationChooserFrontendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(PROJECT_ROOT, "index.html"), encoding="utf-8") as f:
            cls.html = f.read()

    def test_wordpress_install_location_chooser_exists(self):
        for text in [
            'id="wp-install-location"',
            'value="/var/www"',
            'value="/opt"',
            'value="home-local"',
            '~/local',
        ]:
            self.assertIn(text, self.html)

    def test_wordpress_path_generation_uses_selected_location(self):
        for text in [
            'function getWpInstallBase()',
            "wp-install-location",
            "home-local",
            "/home/vjranga/local",
            "`${base}/${name}`",
        ]:
            self.assertIn(text, self.html)

    def test_home_local_is_default_wordpress_install_location(self):
        self.assertIn('<option value="home-local" selected>~/local</option>', self.html)
        self.assertIn("const selected = locationEl ? locationEl.value : 'home-local';", self.html)
        self.assertIn("document.getElementById('wp-install-location').value = 'home-local';", self.html)


if __name__ == "__main__":
    unittest.main()
