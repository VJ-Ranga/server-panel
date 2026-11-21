import os
import subprocess
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
            "`${panelSettings.home_dir}/local`",
            "`${base}/${name}`",
        ]:
            self.assertIn(text, self.html)

    def test_home_local_is_default_wordpress_install_location(self):
        self.assertIn('<option value="home-local" selected>~/local</option>', self.html)
        self.assertIn("const selected = locationEl ? locationEl.value : 'home-local';", self.html)
        self.assertIn("locationEl.value = panelSettings.default_install_location", self.html)
        self.assertIn("if (locationChanged) wpInstallLocationChanged = true;", self.html)
        self.assertIn("if (wpInstallLocationChanged) return;", self.html)
        self.assertEqual(self.html.count("api('/api/settings')"), 1)
        self.assertIn('id="default-install-location"', self.html)
        self.assertIn("api('/api/settings', 'POST', { default_install_location: location })", self.html)

    def test_wordpress_location_autofill_keeps_in_form_selection(self):
        start = self.html.index("function setWpInstallLocationDefault()")
        end = self.html.index("function _randPass(", start)
        script = self.html[start:end] + """
const assert = require('node:assert/strict');
const panelSettings = { home_dir: '/home/example', default_install_location: '/opt' };
let wpInstallLocationChanged = false;
const fields = {
  'wp-install-location': { value: 'home-local' },
  'wp-install-path': { value: '' },
  'wp-site-name': { value: 'demo' },
  'wp-db-name': { value: '' },
  'wp-db-user': { value: '' },
  'wp-admin-user': { value: 'admin' },
  'wp-site-title': { value: '' },
};
const document = { getElementById: id => fields[id] };
setWpInstallLocationDefault();
wpAutoFill();
assert.equal(fields['wp-install-path'].value, '/opt/demo');
fields['wp-install-location'].value = 'home-local';
wpAutoFill(true);
setWpInstallLocationDefault();
assert.equal(fields['wp-install-location'].value, 'home-local');
assert.equal(fields['wp-install-path'].value, '/home/example/local/demo');
delete panelSettings.home_dir;
assert.equal(getWpInstallBase(), '/var/www');
"""
        run = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=5)
        self.assertEqual(run.returncode, 0, run.stderr)


if __name__ == "__main__":
    unittest.main()
