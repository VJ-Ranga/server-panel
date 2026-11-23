import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MCP_DIR = PROJECT_ROOT / "mcp"

import panel
import sys
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))
import server_panel_mcp


class SecuritySecretsBackendTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config_path = Path(self.tmp.name) / "panel_config.json"
        patch = mock.patch.object(panel, "CONFIG_FILE", str(self.config_path))
        patch.start()
        self.addCleanup(patch.stop)

        self.session_token = "valid-session-token-123"
        self.mcp_key = "valid-mcp-key-456"
        self.config_data = {
            "username": "admin",
            "password_hash": hashlib.sha256(b"secret").hexdigest(),
            "session_tokens": {self.session_token: time.time()},
            "mcp_key": self.mcp_key,
            "default_install_location": "/var/www",
            "wp_admin_credentials": {
                "/var/www/wpsite": {
                    "username": "wpadmin",
                    "password": "wp_secret_pass",
                    "updated_at": 1234567,
                }
            },
        }
        self.config_path.write_text(json.dumps(self.config_data))

    def request(self, path, data=None, method="POST", bearer=None):
        handler = panel.Handler.__new__(panel.Handler)
        handler.path = path
        handler.read_body = lambda: data if data is not None else {}
        handler.headers = {"Authorization": f"Bearer {bearer}"} if bearer is not None else {}
        responses = []
        handler.send_json = lambda body, status=200: responses.append((body, status))
        handler.send_response = lambda code: None
        handler.send_header = lambda k, v: None
        handler.end_headers = lambda: None
        getattr(handler, "do_" + method)()
        self.assertEqual(len(responses), 1)
        return responses[0]

    def test_list_endpoints_contain_no_passwords_and_have_has_flags(self):
        # 1. WordPress
        wp_dir = Path(self.tmp.name) / "wpsite"
        wp_dir.mkdir(exist_ok=True)
        wp_cfg = wp_dir / "wp-config.php"
        wp_cfg.write_text("define('DB_NAME', 'wp_db');\ndefine('DB_USER', 'wp_user');\n")

        with mock.patch.object(panel.glob, "glob", side_effect=lambda p: [str(wp_cfg)] if p == "/var/www/*/wp-config.php" else []), \
             mock.patch.object(panel, "get_wp_admin_credential", return_value={"username": "wpadmin", "password": "wp_secret_pass"}), \
             mock.patch.object(panel, "find_nginx_site_for_path", return_value="wpsite"), \
             mock.patch.object(panel, "get_nginx_site_port", return_value=8090), \
             mock.patch.object(panel, "detect_wp_admin_users", return_value=["wpadmin"]):
            sites = panel.get_wp_sites()

        self.assertEqual(len(sites), 1)
        self.assertTrue(sites[0]["has_saved_admin_pass"])
        self.assertNotIn("wp_admin_pass", sites[0])
        for val in sites[0].values():
            self.assertNotEqual(val, "wp_secret_pass")

        # WordPress without saved password
        with mock.patch.object(panel.glob, "glob", side_effect=lambda p: [str(wp_cfg)] if p == "/var/www/*/wp-config.php" else []), \
             mock.patch.object(panel, "get_wp_admin_credential", return_value={}), \
             mock.patch.object(panel, "find_nginx_site_for_path", return_value="wpsite"), \
             mock.patch.object(panel, "get_nginx_site_port", return_value=8090), \
             mock.patch.object(panel, "detect_wp_admin_users", return_value=["wpadmin"]):
            sites_no_pass = panel.get_wp_sites()
        self.assertEqual(len(sites_no_pass), 1)
        self.assertFalse(sites_no_pass[0]["has_saved_admin_pass"])
        self.assertNotIn("wp_admin_pass", sites_no_pass[0])

        # 2. Laravel
        with mock.patch.object(panel.glob, "glob", return_value=["/var/www/larapp/artisan"]), \
             mock.patch.object(panel, "read_env_file", return_value={"DB_DATABASE": "lar_db", "DB_USERNAME": "lar_user", "DB_PASSWORD": "lar_secret_password"}), \
             mock.patch.object(panel, "find_nginx_site_for_path", return_value="larapp"), \
             mock.patch.object(panel, "get_nginx_site_port", return_value=8100), \
             mock.patch.object(panel, "run_cmd", return_value={"success": True, "stdout": "Laravel v12\n"}):
            lar_apps = panel.get_laravel_apps()

        self.assertEqual(len(lar_apps), 1)
        self.assertTrue(lar_apps[0]["has_db_pass"])
        self.assertNotIn("db_pass", lar_apps[0])
        for val in lar_apps[0].values():
            self.assertNotEqual(val, "lar_secret_password")

        # 3. CodeIgniter
        with mock.patch.object(panel.glob, "glob", return_value=["/var/www/ciapp/spark"]), \
             mock.patch.object(panel, "read_env_file", return_value={"database.default.database": "ci_db", "database.default.username": "ci_user", "database.default.password": "ci_secret_password"}), \
             mock.patch.object(panel, "find_nginx_site_for_path", return_value="ciapp"), \
             mock.patch.object(panel, "get_nginx_site_port", return_value=8200), \
             mock.patch.object(panel, "run_cmd", return_value={"success": True, "stdout": "CI v4\n", "stderr": ""}):
            ci_apps = panel.get_codeigniter_apps()

        self.assertEqual(len(ci_apps), 1)
        self.assertTrue(ci_apps[0]["has_db_pass"])
        self.assertNotIn("db_pass", ci_apps[0])
        for val in ci_apps[0].values():
            self.assertNotEqual(val, "ci_secret_password")

    def test_secrets_reveal_endpoint(self):
        fake_wp = [{"name": "wpsite", "path": "/var/www/wpsite", "wp_admin_user": "wpadmin"}]
        fake_lar = [{"name": "larapp", "path": "/var/www/larapp", "db_user": "lar_user"}]
        fake_ci = [{"name": "ciapp", "path": "/var/www/ciapp", "db_user": "ci_user"}]

        with mock.patch.object(panel, "get_wp_sites", return_value=fake_wp), \
             mock.patch.object(panel, "get_laravel_apps", return_value=fake_lar), \
             mock.patch.object(panel, "get_codeigniter_apps", return_value=fake_ci), \
             mock.patch.object(panel, "read_env_file", side_effect=lambda p: {"DB_PASSWORD": "lar_secret", "database.default.password": "ci_secret"}):

            # 1. Reveal wp_admin with session token
            body, status = self.request("/api/secrets/reveal", {"kind": "wp_admin", "path": "/var/www/wpsite"}, bearer=self.session_token)
            self.assertEqual(status, 200)
            self.assertTrue(body["success"])
            self.assertEqual(body["password"], "wp_secret_pass")
            self.assertEqual(body["username"], "wpadmin")

            # 2. Reveal laravel_db with session token
            body, status = self.request("/api/secrets/reveal", {"kind": "laravel_db", "path": "/var/www/larapp"}, bearer=self.session_token)
            self.assertEqual(status, 200)
            self.assertTrue(body["success"])
            self.assertEqual(body["password"], "lar_secret")
            self.assertEqual(body["username"], "lar_user")

            # 3. Reveal codeigniter_db with session token
            body, status = self.request("/api/secrets/reveal", {"kind": "codeigniter_db", "path": "/var/www/ciapp"}, bearer=self.session_token)
            self.assertEqual(status, 200)
            self.assertTrue(body["success"])
            self.assertEqual(body["password"], "ci_secret")
            self.assertEqual(body["username"], "ci_user")

            # 4. Unknown path -> 404
            body, status = self.request("/api/secrets/reveal", {"kind": "wp_admin", "path": "/var/www/unknown"}, bearer=self.session_token)
            self.assertEqual(status, 404)
            self.assertFalse(body["success"])

            # 5. Bad kind -> 400
            body, status = self.request("/api/secrets/reveal", {"kind": "bad_kind", "path": "/var/www/wpsite"}, bearer=self.session_token)
            self.assertEqual(status, 400)
            self.assertFalse(body["success"])

            # 6. MCP key gets 403
            body, status = self.request("/api/secrets/reveal", {"kind": "wp_admin", "path": "/var/www/wpsite"}, bearer=self.mcp_key)
            self.assertEqual(status, 403)
            self.assertIn("session", body["error"].lower())

            # 7. Unauthenticated gets 401
            body, status = self.request("/api/secrets/reveal", {"kind": "wp_admin", "path": "/var/www/wpsite"}, bearer="invalid-token")
            self.assertEqual(status, 401)

    def test_wordpress_credentials_endpoint_mcp_rejected(self):
        with mock.patch.object(panel, "find_discovered_wp_site", side_effect=lambda p: {"path": "/var/www/site"} if p == "/var/www/site" else None), \
             mock.patch.object(panel, "read_wp_config", return_value={"db_name": "db", "db_user": "u", "db_pass": "p"}):
            # MCP key -> 403
            body, status = self.request("/api/wordpress/credentials?path=/var/www/site", method="GET", bearer=self.mcp_key)
            self.assertEqual(status, 403)
            self.assertIn("session", body["error"].lower())

            # Session token -> 200
            body, status = self.request("/api/wordpress/credentials?path=/var/www/site", method="GET", bearer=self.session_token)
            self.assertEqual(status, 200)
            self.assertTrue(body["success"])
            self.assertEqual(body["db_pass"], "p")

            # Unknown path -> 404
            body, status = self.request("/api/wordpress/credentials?path=/var/www/unknown", method="GET", bearer=self.session_token)
            self.assertEqual(status, 404)
            self.assertFalse(body["success"])

            # Missing path -> 404
            body, status = self.request("/api/wordpress/credentials", method="GET", bearer=self.session_token)
            self.assertEqual(status, 404)
            self.assertFalse(body["success"])

    def test_change_credentials_endpoints_guards(self):
        with mock.patch.object(panel, "find_discovered_wp_site", side_effect=lambda p: {"path": "/var/www/site"} if p == "/var/www/site" else None):
            # 1. change_db_password
            # MCP key -> 403
            body, status = self.request(
                "/api/wordpress/change_db_password",
                {"install_path": "/var/www/site", "db_user": "u", "new_pass": "newpass"},
                bearer=self.mcp_key,
            )
            self.assertEqual(status, 403)
            self.assertIn("session", body["error"].lower())

            # Unknown path -> 404
            body, status = self.request(
                "/api/wordpress/change_db_password",
                {"install_path": "/var/www/unknown", "db_user": "u", "new_pass": "newpass"},
                bearer=self.session_token,
            )
            self.assertEqual(status, 404)
            self.assertFalse(body["success"])

            # 2. change_wp_admin
            # MCP key -> 403
            body, status = self.request(
                "/api/wordpress/change_wp_admin",
                {"install_path": "/var/www/site", "wp_admin_user": "admin", "new_pass": "newpass"},
                bearer=self.mcp_key,
            )
            self.assertEqual(status, 403)
            self.assertIn("session", body["error"].lower())

            # Unknown path -> 404
            body, status = self.request(
                "/api/wordpress/change_wp_admin",
                {"install_path": "/var/www/unknown", "wp_admin_user": "admin", "new_pass": "newpass"},
                bearer=self.session_token,
            )
            self.assertEqual(status, 404)
            self.assertFalse(body["success"])

    def test_job_status_redaction_mcp_vs_session(self):
        job_data = {
            "status": "done",
            "logs": [
                "▶ Step 1: installing...",
                "  Username : admin",
                "  Password : supersecretwpadminpass",
                "  DB Name  : testdb",
                "  DB Pass  : supersecretdbpass",
                "database.default.password=dbdefaultpass",
                "api_key: mysecretapikey",
            ],
            "result": {
                "site_name": "testsite",
                "url": "http://localhost:8090",
                "wp_admin_pass": "supersecretwpadminpass",
                "db_pass": "supersecretdbpass",
                "database.default.password": "dbdefaultpass",
                "api_key": "mysecretapikey",
                "has_db_pass": True,
                "has_saved_admin_pass": True,
            },
        }

        routes = [
            "/api/wordpress/install/job1",
            "/api/laravel/install/job1",
            "/api/codeigniter/install/job1",
            "/api/php-projects/install/job1",
        ]

        for route in routes:
            panel._jobs["job1"] = panel.deepcopy(job_data)

            # Session token caller gets unredacted data
            body, status = self.request(route, method="GET", bearer=self.session_token)
            self.assertEqual(status, 200)
            self.assertEqual(body["result"]["wp_admin_pass"], "supersecretwpadminpass")
            self.assertEqual(body["result"]["db_pass"], "supersecretdbpass")
            self.assertIn("supersecretwpadminpass", body["logs"][2])
            self.assertIn("supersecretdbpass", body["logs"][4])

            # MCP key caller gets redacted result and masked logs
            body_mcp, status_mcp = self.request(route, method="GET", bearer=self.mcp_key)
            self.assertEqual(status_mcp, 200)
            self.assertEqual(body_mcp["result"]["wp_admin_pass"], "[redacted]")
            self.assertEqual(body_mcp["result"]["db_pass"], "[redacted]")
            self.assertEqual(body_mcp["result"]["database.default.password"], "[redacted]")
            self.assertEqual(body_mcp["result"]["api_key"], "[redacted]")
            self.assertTrue(body_mcp["result"]["has_db_pass"])
            self.assertTrue(body_mcp["result"]["has_saved_admin_pass"])
            self.assertNotIn("supersecretwpadminpass", json.dumps(body_mcp))
            self.assertNotIn("supersecretdbpass", json.dumps(body_mcp))
            self.assertNotIn("dbdefaultpass", json.dumps(body_mcp))
            self.assertNotIn("mysecretapikey", json.dumps(body_mcp))
            self.assertIn("Password: [redacted]", body_mcp["logs"][2])
            self.assertIn("DB Pass: [redacted]", body_mcp["logs"][4])
            self.assertIn("database.default.password: [redacted]", body_mcp["logs"][5])
            self.assertIn("api_key: [redacted]", body_mcp["logs"][6])

            # Internal job dictionary must remain unmutated
            self.assertEqual(panel._jobs["job1"]["result"]["wp_admin_pass"], "supersecretwpadminpass")
            self.assertEqual(panel._jobs["job1"]["result"]["db_pass"], "supersecretdbpass")

    def test_mysql_cmd_contains_no_argv_password(self):
        executed_commands = []

        def fake_run_cmd(cmd, input_data=None, timeout=None):
            executed_commands.append(cmd)
            return {"success": True, "stdout": "1\n", "stderr": "", "returncode": 0}

        cfg = {"mysql_user": "appuser", "mysql_password": "supersecretpassword123"}
        with mock.patch.object(panel, "run_cmd", side_effect=fake_run_cmd):
            res = panel.mysql_cmd(cfg, "SELECT 1;", database="appdb")

        self.assertTrue(res["success"])
        self.assertTrue(len(executed_commands) >= 1)
        for cmd in executed_commands:
            # Must not contain -p<password> or -p <password>
            self.assertNotIn("-psupersecretpassword123", cmd)
            self.assertNotIn("-p supersecretpassword123", cmd)
            self.assertNotIn("-p'supersecretpassword123'", cmd)
            self.assertNotIn("-p\"supersecretpassword123\"", cmd)
            # Must pass password through MYSQL_PWD
            self.assertIn("MYSQL_PWD=", cmd)
            self.assertIn("supersecretpassword123", cmd)


class MCPRedactionAndBlockTests(unittest.TestCase):
    def test_recursive_redaction_dict_and_booleans(self):
        data = {
            "name": "myapp",
            "password": "secret_password",
            "db_pass": "secret_db_pass",
            "wp_admin_pass": "secret_wp_pass",
            "mcp_key": "secret_mcp_key",
            "token": "secret_token",
            "secret": "secret_value",
            "DB_PASSWORD": "secret_caps",
            "db_password": "secret_db_pass2",
            "database.default.password": "secret_ci_db_pass",
            "api_key": "secret_api_key",
            "api-key": "secret_api_dash_key",
            "has_db_pass": True,
            "has_saved_admin_pass": False,
            "password_set": True,
            "nested": {
                "user": "root",
                "passwd": "secret_passwd",
                "has_something": True,
                "deep": {
                    "token": "nested_token",
                    "count": 42,
                },
            },
        }

        redacted = server_panel_mcp.redact_secrets(data)

        self.assertEqual(redacted["name"], "myapp")
        self.assertEqual(redacted["password"], "[redacted]")
        self.assertEqual(redacted["db_pass"], "[redacted]")
        self.assertEqual(redacted["wp_admin_pass"], "[redacted]")
        self.assertEqual(redacted["mcp_key"], "[redacted]")
        self.assertEqual(redacted["token"], "[redacted]")
        self.assertEqual(redacted["secret"], "[redacted]")
        self.assertEqual(redacted["DB_PASSWORD"], "[redacted]")
        self.assertEqual(redacted["db_password"], "[redacted]")
        self.assertEqual(redacted["database.default.password"], "[redacted]")
        self.assertEqual(redacted["api_key"], "[redacted]")
        self.assertEqual(redacted["api-key"], "[redacted]")

        # Booleans must NOT be redacted
        self.assertIs(redacted["has_db_pass"], True)
        self.assertIs(redacted["has_saved_admin_pass"], False)
        self.assertIs(redacted["password_set"], True)

        # Nested dicts
        self.assertEqual(redacted["nested"]["user"], "root")
        self.assertEqual(redacted["nested"]["passwd"], "[redacted]")
        self.assertIs(redacted["nested"]["has_something"], True)
        self.assertEqual(redacted["nested"]["deep"]["token"], "[redacted]")
        self.assertEqual(redacted["nested"]["deep"]["count"], 42)

    def test_log_string_redaction(self):
        log_text = (
            "▶ [7/7] All done!\n"
            "✔ WordPress installed at: http://localhost:8090\n"
            "  Username : admin\n"
            "  Password : mysecretpassword123\n"
            "  DB Name  : my_db\n"
            "  DB User  : my_user\n"
            "  DB Pass  : mydbpassword456\n"
            "Save these credentials!\n"
            "pass=inlinepassword789\n"
        )

        redacted = server_panel_mcp.redact_secrets(log_text)
        self.assertNotIn("mysecretpassword123", redacted)
        self.assertNotIn("mydbpassword456", redacted)
        self.assertNotIn("inlinepassword789", redacted)
        self.assertIn("Password: [redacted]", redacted)
        self.assertIn("DB Pass: [redacted]", redacted)
        self.assertIn("pass: [redacted]", redacted)
        self.assertIn("Username : admin", redacted)
        self.assertIn("DB Name  : my_db", redacted)

    def test_new_redaction_forms(self):
        keys = [
            "db_password",
            "db_pass",
            "wp_admin_pass",
            "database.default.password",
            "mcp_key",
            "secret",
            "token",
            "api_key",
            "api-key",
        ]

        # Test both KEY=VALUE and KEY: VALUE forms
        for key in keys:
            # 1. KEY=VALUE
            raw_eq = f"{key}=supersecretval_{key}"
            redacted_eq = server_panel_mcp.redact_secrets(raw_eq)
            self.assertNotIn(f"supersecretval_{key}", redacted_eq)
            self.assertIn("[redacted]", redacted_eq)
            self.assertIn(key, redacted_eq)

            # 2. KEY: VALUE
            raw_colon = f"  {key} : supersecretval_{key}"
            redacted_colon = server_panel_mcp.redact_secrets(raw_colon)
            self.assertNotIn(f"supersecretval_{key}", redacted_colon)
            self.assertIn("[redacted]", redacted_colon)
            self.assertIn(key, redacted_colon)

    def test_mcp_refuses_blocked_paths_via_panel_api(self):
        blocked_paths = [
            "/api/login",
            "/api/panel/open",
            "/api/panel/close",
            "/api/secrets/reveal",
            "/api/wordpress/credentials",
            "/api/wordpress/credentials?path=/var/www/site",
            "/api/wordpress/change_db_password",
            "/api/wordpress/change_wp_admin",
            # Case variants
            "/API/LOGIN",
            "/API/PANEL/OPEN",
            "/API/PANEL/CLOSE",
            "/API/SECRETS/REVEAL",
            "/api/Secrets/Reveal",
            "/API/WORDPRESS/CREDENTIALS",
            "/api/WORDPRESS/credentials?path=/var/www/site",
            "/API/WORDPRESS/CHANGE_DB_PASSWORD",
            "/API/WORDPRESS/CHANGE_WP_ADMIN",
            # Trailing slashes
            "/api/login/",
            "/api/secrets/reveal/",
            "/api/wordpress/credentials/",
            "/api/wordpress/change_db_password/",
            "/api/wordpress/change_wp_admin/",
            # Duplicate slashes
            "//api///login",
            "//api///secrets//reveal",
            "//api//wordpress//credentials",
            "//api//wordpress//change_db_password//",
            # Percent encoding
            "/%61pi/login",
            "/api/%73ecrets/reveal",
            "/api/wordpress/%63redentials",
            "/api/wordpress/change_%64b_password",
            "/api/wordpress/change_%77p_admin",
        ]

        for path in blocked_paths:
            with self.subTest(path=path):
                # safe_api_path must refuse it
                with self.assertRaises(server_panel_mcp.ToolError):
                    server_panel_mcp.safe_api_path(path)

        # PanelClient.request must also reject blocked paths
        client = server_panel_mcp.PanelClient()
        for path in blocked_paths:
            with self.subTest(client_path=path):
                with self.assertRaises(server_panel_mcp.ToolError):
                    client.request("GET", path)

        server = server_panel_mcp.MCPServer()
        with self.assertRaises(server_panel_mcp.ToolError):
            server.execute("panel_api", {"method": "POST", "path": "/api/secrets/reveal"})

        with self.assertRaises(server_panel_mcp.ToolError):
            server.execute("panel_api", {"method": "GET", "path": "/api/wordpress/credentials?path=/var/www/site"})

        with self.assertRaises(server_panel_mcp.ToolError):
            server.execute("panel_api", {"method": "POST", "path": "/api/wordpress/change_db_password"})

        with self.assertRaises(server_panel_mcp.ToolError):
            server.execute("panel_api", {"method": "POST", "path": "/api/wordpress/change_wp_admin"})


class SecurityFrontendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(PROJECT_ROOT / "index.html", encoding="utf-8") as f:
            cls.html = f.read()

    def test_cards_do_not_render_passwords_directly(self):
        # Must not directly evaluate/interpolate wp_admin_pass or db_pass in card templates
        self.assertNotIn("${esc(s.wp_admin_pass)}", self.html)
        self.assertNotIn("s.wp_admin_pass ?", self.html)
        self.assertNotIn("${esc(app.db_pass || '')}", self.html)
        self.assertNotIn("${esc(app.db_pass)}", self.html)

    def test_cards_render_masked_placeholders_and_show_button(self):
        # Element IDs must exist
        self.assertIn('id="wp-admin-pass-${i}"', self.html)
        self.assertIn('id="lv-db-pass-${i}"', self.html)
        self.assertIn('id="ci-db-pass-${i}"', self.html)

        # Masked dots and Show buttons
        self.assertIn("••••••••", self.html)
        self.assertIn("s.has_saved_admin_pass ?", self.html)
        self.assertIn("app.has_db_pass ?", self.html)

    def test_reveal_secret_function_exists(self):
        self.assertIn("function revealSecret(", self.html)
        self.assertIn("/api/secrets/reveal", self.html)


if __name__ == "__main__":
    unittest.main()
