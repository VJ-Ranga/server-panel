import hashlib
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import panel


class LoginBackendTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config = Path(self.tmp.name) / "panel_config.json"
        patch = mock.patch.object(panel, "CONFIG_FILE", str(self.config))
        patch.start()
        self.addCleanup(patch.stop)
        # These tests must never bind a socket or execute a service command.
        for name in ("ThreadingHTTPServer", "run_cmd"):
            guard = mock.patch.object(panel, name, side_effect=AssertionError("Unexpected server/service call"))
            guard.start()
            self.addCleanup(guard.stop)
        self.write_config({"password_hash": self.password_hash("secret"),
                           "session_tokens": {"old": 123}, "mysql_password": "keep-me",
                           "custom_setting": {"preserve": [1, 2]}})

    @staticmethod
    def password_hash(password):
        return hashlib.sha256(password.encode()).hexdigest()

    def write_config(self, data):
        self.config.write_text(json.dumps(data))

    def request(self, path, data=None, authenticated=True, method="POST"):
        handler = panel.Handler.__new__(panel.Handler)
        handler.path = path
        handler.read_body = lambda: data
        handler.authed = lambda: authenticated
        responses = []
        handler.send_json = lambda body, status=200: responses.append((body, status))
        getattr(handler, "do_" + method)()
        self.assertEqual(len(responses), 1)
        return responses[0]

    def test_loading_legacy_config_does_not_rewrite_file(self):
        before = self.config.read_bytes()
        self.assertEqual(panel.load_config()["username"], "admin")
        self.assertEqual(self.config.read_bytes(), before)

    def test_legacy_login_accepts_admin_or_omitted_username(self):
        for data in ({"username": "admin", "password": "secret"}, {"password": "secret"}):
            body, status = self.request("/api/login", data)
            self.assertEqual(status, 200)
            self.assertTrue(body["success"])
            self.assertIn(body["token"], panel.load_config()["session_tokens"])

    def test_wrong_username_and_password_have_same_error(self):
        before = self.config.read_bytes()
        wrong_user = self.request("/api/login", {"username": "other", "password": "secret"})
        wrong_password = self.request("/api/login", {"username": "admin", "password": "wrong"})
        self.assertEqual(wrong_user, wrong_password)
        self.assertEqual(wrong_user[1], 401)
        self.assertFalse(wrong_user[0]["success"])
        self.assertEqual(self.config.read_bytes(), before)

    def test_custom_username_is_trimmed_and_case_sensitive(self):
        cfg = panel.load_config()
        cfg["username"] = "Admin.1_-"
        self.write_config(cfg)
        body, status = self.request("/api/login", {"username": "  Admin.1_- ", "password": "secret"})
        self.assertTrue(body["success"])
        for username in ("admin.1_-", "admin", "", None, 123):
            self.assertEqual(self.request("/api/login", {"username": username, "password": "secret"})[1], 401)
        self.assertEqual(self.request("/api/login", {"password": "secret"})[1], 401)

    def test_username_change_requires_current_password_and_is_atomic(self):
        before = self.config.read_bytes()
        for password in (None, "wrong"):
            body, _ = self.request("/api/settings", {"new_username": "owner", "current_password": password,
                                                      "new_password": "changed", "mysql_user": "changed"})
            self.assertFalse(body["success"])
            self.assertIn("password", body["error"].lower())
            self.assertEqual(self.config.read_bytes(), before)

    def test_username_validation_rejects_invalid_values(self):
        before = self.config.read_bytes()
        for username in ("bad name", "", "a" * 33, "ümlaut", "bad\n", None, 42):
            body, _ = self.request("/api/settings", {"new_username": username, "current_password": "secret"})
            self.assertFalse(body["success"], repr(username))
            self.assertIn("Username", body["error"])
            self.assertEqual(self.config.read_bytes(), before)

    def test_username_change_preserves_password_and_other_keys_and_clears_tokens(self):
        login, _ = self.request("/api/login", {"password": "secret"})
        handler = panel.Handler.__new__(panel.Handler)
        self.assertTrue(handler.valid_token(login["token"]))
        body, _ = self.request("/api/settings", {"new_username": "Owner.1_-", "current_password": "secret"})
        self.assertTrue(body["success"])
        cfg = panel.load_config()
        self.assertEqual(cfg["username"], "Owner.1_-")
        self.assertEqual(cfg["password_hash"], self.password_hash("secret"))
        self.assertEqual(cfg["mysql_password"], "keep-me")
        self.assertEqual(cfg["session_tokens"], {})
        self.assertFalse(handler.valid_token(login["token"]))

    def test_username_validation_accepts_one_and_32_characters(self):
        for username in ("a", "a" * 32):
            with self.subTest(username=username):
                body, _ = self.request("/api/settings", {"new_username": username, "current_password": "secret"})
                self.assertTrue(body["success"])
                self.assertEqual(panel.load_config()["username"], username)

    def test_password_change_keeps_existing_contract(self):
        body, _ = self.request("/api/settings", {"new_password": "new-secret"})
        self.assertTrue(body["success"])
        self.assertEqual(panel.load_config()["password_hash"], self.password_hash("new-secret"))
        self.assertEqual(panel.load_config()["session_tokens"], {})

    def test_settings_get_returns_only_username_and_requires_auth(self):
        self.assertEqual(self.request("/api/settings", method="GET"), ({"username": "admin"}, 200))
        self.assertEqual(self.request("/api/settings", method="GET", authenticated=False)[1], 401)

    def run_set_login(self, lines):
        output = io.StringIO()
        with mock.patch.object(sys, "stdin", io.StringIO(lines)), mock.patch.object(sys, "stdout", output):
            result = panel.main(["--set-login"])
        return result, output.getvalue()

    def test_set_login_defaults_preserves_keys_clears_tokens_and_secures_config(self):
        result, output = self.run_set_login("\n\n")
        self.assertEqual(result, 0)
        self.assertEqual(output, "Login saved for user admin.\n")
        cfg = json.loads(self.config.read_text())
        self.assertEqual(cfg["username"], "admin")
        self.assertEqual(cfg["password_hash"], self.password_hash("admin"))
        self.assertEqual(cfg["mysql_password"], "keep-me")
        self.assertEqual(cfg["custom_setting"], {"preserve": [1, 2]})
        self.assertEqual(cfg["session_tokens"], {})
        self.assertEqual(stat.S_IMODE(self.config.stat().st_mode), 0o600)

    def test_set_login_new_config_uses_defaults_and_custom_login(self):
        self.config.unlink()
        result, output = self.run_set_login("owner\np a s s\n")
        self.assertEqual(result, 0)
        cfg = json.loads(self.config.read_text())
        self.assertEqual(cfg["username"], "owner")
        self.assertEqual(cfg["password_hash"], self.password_hash("p a s s"))
        self.assertEqual(cfg["mysql_user"], "root")

    def test_set_login_rejects_invalid_username_without_writing(self):
        before = self.config.read_bytes()
        for username in ("bad name", "a" * 33):
            with mock.patch.object(sys, "stderr", io.StringIO()):
                result, _ = self.run_set_login(username + "\nsecret\n")
            self.assertNotEqual(result, 0)
            self.assertEqual(self.config.read_bytes(), before)


class InstallerStaticTests(unittest.TestCase):
    def test_sudo_helper_paths_use_configurable_directory_with_legacy_default(self):
        source = (PROJECT_ROOT / "setup-sudo.sh").read_text()
        self.assertIn('PANEL_DIR="${2:-/home/$USER/Documents/server-panel}"', source)
        rules = source.split("cat > /etc/sudoers.d/server-panel << EOF\n", 1)[1].split("\nEOF", 1)[0]
        for helper in ("wp-install", "wp-delete", "laravel", "codeigniter", "php-project", "perf"):
            rule = '$USER ALL=(ALL) NOPASSWD: $PANEL_DIR/' + helper + '-helper.sh *'
            self.assertIn(rule, rules)
            self.assertIn('/tmp/fake-panel/' + helper + '-helper.sh *',
                          rules.replace('$PANEL_DIR', '/tmp/fake-panel'))

    def test_install_script_has_valid_bash_syntax_and_is_executable(self):
        path = PROJECT_ROOT / "install.sh"
        result = subprocess.run(["bash", "-n", str(path)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(path.stat().st_mode & stat.S_IXUSR)


if __name__ == "__main__":
    unittest.main()
