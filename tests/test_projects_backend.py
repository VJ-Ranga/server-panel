import concurrent.futures
import datetime
import json
import os
from pathlib import Path
import re
import socket
import stat
import tempfile
import threading
import time
import unittest
from unittest import mock
import urllib.error
import urllib.parse
import urllib.request

import panel


class ProjectsBackendTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

        self.config_path = Path(self.tmp.name) / "panel_config.json"
        self.projects_path = Path(self.tmp.name) / "projects.json"

        # Mock paths
        patch_cfg = mock.patch.object(panel, "CONFIG_FILE", str(self.config_path))
        patch_proj = mock.patch.object(panel, "PROJECTS_FILE", str(self.projects_path))
        patch_env = mock.patch.dict(
            os.environ,
            {
                "SERVER_PANEL_CONFIG": str(self.config_path),
                "SERVER_PANEL_PROJECTS": str(self.projects_path),
                "no_proxy": "*",
                "NO_PROXY": "*",
            },
        )
        patch_cfg.start()
        patch_proj.start()
        patch_env.start()
        self.addCleanup(patch_cfg.stop)
        self.addCleanup(patch_proj.stop)
        self.addCleanup(patch_env.stop)

        # Write test config with session token and MCP key
        self.session_token = "test-session-token-12345"
        self.mcp_key = "test-mcp-key-67890"
        self.config_path.write_text(
            json.dumps(
                {
                    "username": "admin",
                    "password_hash": "dummy",
                    "session_tokens": {self.session_token: time.time()},
                    "mcp_key": self.mcp_key,
                }
            )
        )

        # Start ephemeral panel server on loopback port 0
        self.http_server = panel.ThreadingHTTPServer(("127.0.0.1", 0), panel.Handler)
        self.server_port = self.http_server.server_port
        self.server_thread = threading.Thread(target=self.http_server.serve_forever, daemon=True)
        self.server_thread.start()

        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def tearDown(self):
        self.http_server.shutdown()
        self.http_server.server_close()
        self.server_thread.join()

    def request(self, method, path, body=None, token="test-session-token-12345"):
        url = f"http://127.0.0.1:{self.server_port}{path}"
        headers = {}
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=5) as response:
                status = response.code
                raw = response.read()
                return status, json.loads(raw.decode("utf-8")) if raw else {}
        except urllib.error.HTTPError as exc:
            status = exc.code
            raw = exc.read()
            exc.close()
            try:
                body = json.loads(raw.decode("utf-8"))
            except Exception:
                body = {"raw": raw.decode("utf-8", errors="replace")}
            return status, body

    def test_crud_round_trip(self):
        # 1. Initially empty
        status, data = self.request("GET", "/api/projects")
        self.assertEqual(status, 200)
        self.assertEqual(data.get("projects"), [])

        # 2. Create a project
        create_payload = {
            "name": "Acme Portal",
            "client": "Acme Corp",
            "status": "building",
            "vault_path": "/home/demo/vault/acme",
            "notes": "Main portal site",
            "parts": [
                {
                    "role": "wordpress",
                    "label": "API Backend",
                    "local_url": "http://localhost:8080",
                    "local_path": "/var/www/acme-backend",
                    "live_url": "https://api.example.com",
                    "staging_url": "https://staging-api.example.com",
                    "hosting_url": "https://hosting.example.com/acme",
                    "git_url": "git@example.com:acme/backend.git",
                    "hosting_name": "Cloud Hosting",
                    "notes": "Backend service",
                }
            ],
        }
        status, data = self.request("POST", "/api/projects", create_payload)
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        project = data.get("project")
        self.assertIsNotNone(project)
        project_id = project.get("id")
        self.assertTrue(bool(re.fullmatch(r"[0-9a-f]{8}", project_id)))
        self.assertEqual(project.get("name"), "Acme Portal")
        self.assertEqual(project.get("client"), "Acme Corp")
        self.assertIn("created", project)
        self.assertIn("updated", project)
        self.assertEqual(len(project.get("parts", [])), 1)
        part = project["parts"][0]
        part_id = part.get("id")
        self.assertTrue(bool(re.fullmatch(r"[0-9a-f]{8}", part_id)))
        self.assertEqual(part.get("role"), "wordpress")

        # 3. GET returns the created project
        status, data = self.request("GET", "/api/projects")
        self.assertEqual(status, 200)
        self.assertEqual(len(data.get("projects", [])), 1)
        fetched = data["projects"][0]
        self.assertEqual(fetched["id"], project_id)
        self.assertEqual(fetched["name"], "Acme Portal")
        self.assertIn("local_running", fetched["parts"][0])

        # 4. Update the project
        created_timestamp = project["created"]
        time.sleep(0.01)  # small pause to ensure updated timestamp changes if tracked
        update_payload = {
            "name": "Acme Portal Updated",
            "client": "Acme Worldwide",
            "status": "live",
            "vault_path": "/home/demo/vault/acme-updated",
            "notes": "Updated notes",
            "parts": [
                {
                    "id": part_id,  # preserved
                    "role": "wordpress",
                    "label": "API Backend (v2)",
                    "local_url": "http://127.0.0.1:8080",
                    "local_path": "/var/www/acme-backend",
                    "git_url": "https://example.com/acme/backend.git",
                }
            ],
        }
        status, data = self.request("POST", f"/api/projects/{project_id}", update_payload)
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        updated = data.get("project")
        self.assertEqual(updated["id"], project_id)
        self.assertEqual(updated["name"], "Acme Portal Updated")
        self.assertEqual(updated["status"], "live")
        self.assertEqual(updated["created"], created_timestamp)  # created preserved
        self.assertEqual(updated["parts"][0]["id"], part_id)  # part id preserved
        self.assertEqual(updated["parts"][0]["label"], "API Backend (v2)")

        # 5. Delete the project
        status, data = self.request("DELETE", f"/api/projects/{project_id}")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))

        # 6. Verify deleted
        status, data = self.request("GET", "/api/projects")
        self.assertEqual(status, 200)
        self.assertEqual(data.get("projects"), [])

    def test_validation_urls_reject_userinfo(self):
        # local_url with userinfo
        for bad_url in (
            "http://user:pass@127.0.0.1:8080/",
            "http://user@localhost:8080/",
            "https://token@localhost:8080/",
        ):
            payload = {
                "name": "Test Project",
                "parts": [{"role": "other", "local_url": bad_url}],
            }
            status, data = self.request("POST", "/api/projects", payload)
            self.assertEqual(status, 400)
            self.assertFalse(data.get("success"))
            self.assertIn("local_url", data.get("error", "").lower())
            self.assertIn("user", data.get("error", "").lower())

        # live_url, staging_url, hosting_url with userinfo
        for field in ("live_url", "staging_url", "hosting_url"):
            for bad_url in ("https://user:pass@example.com", "https://token@example.com"):
                payload = {
                    "name": "Test Project",
                    "parts": [{"role": "other", field: bad_url}],
                }
                status, data = self.request("POST", "/api/projects", payload)
                self.assertEqual(status, 400)
                self.assertFalse(data.get("success"))
                self.assertIn(field, data.get("error", "").lower())

        # git_url with userinfo
        payload = {
            "name": "Test Project",
            "parts": [{"role": "other", "git_url": "https://token@github.com/org/repo"}],
        }
        status, data = self.request("POST", "/api/projects", payload)
        self.assertEqual(status, 400)
        self.assertFalse(data.get("success"))
        self.assertIn("git_url", data.get("error", "").lower())

    def test_validation_local_url_loopback_only(self):
        # Non-loopback addresses must be rejected
        for bad_url in (
            "http://example.com/",
            "http://192.168.1.100:8080/",
            "http://10.0.0.1:3000/",
            "http://8.8.8.8/",
            "ftp://localhost:8080/",
        ):
            payload = {
                "name": "Test Project",
                "parts": [{"role": "other", "local_url": bad_url}],
            }
            status, data = self.request("POST", "/api/projects", payload)
            self.assertEqual(status, 400)
            self.assertFalse(data.get("success"))
            self.assertIn("local_url", data.get("error", "").lower())

        # Valid loopback URLs
        for good_url in (
            "http://localhost:8080",
            "http://127.0.0.1:3000/app",
            "http://[::1]:8080",
            "https://localhost:8443",
        ):
            payload = {
                "name": "Test Project",
                "parts": [{"role": "other", "local_url": good_url}],
            }
            status, data = self.request("POST", "/api/projects", payload)
            self.assertEqual(status, 200, f"Failed for {good_url}: {data}")
            self.assertTrue(data.get("success"))
            # cleanup
            self.request("DELETE", f"/api/projects/{data['project']['id']}")

    def test_validation_git_url(self):
        # Invalid git URLs
        for bad_url in (
            "http://github.com/org/repo.git",  # http rejected
            "ssh://git@github.com/org/repo",   # ssh:// prefix not standard form
            "ftp://example.com/repo.git",
            "git@invalid",
            "git@host",
            "git@github.com",
        ):
            payload = {
                "name": "Test Project",
                "parts": [{"role": "other", "git_url": bad_url}],
            }
            status, data = self.request("POST", "/api/projects", payload)
            self.assertEqual(status, 400, f"Expected 400 for {bad_url}")
            self.assertFalse(data.get("success"))
            self.assertIn("git_url", data.get("error", "").lower())

        # Valid git URLs
        for good_url in (
            "https://github.com/org/repo.git",
            "https://gitlab.com/group/subgroup/repo",
            "git@github.com:org/repo.git",
            "git@gitlab.com:group/subgroup/repo",
            "git@example.com:user/project.git",
        ):
            payload = {
                "name": "Test Project",
                "parts": [{"role": "other", "git_url": good_url}],
            }
            status, data = self.request("POST", "/api/projects", payload)
            self.assertEqual(status, 200, f"Expected 200 for {good_url}: {data}")
            self.assertTrue(data.get("success"))
            self.request("DELETE", f"/api/projects/{data['project']['id']}")

    def test_validation_status_and_role(self):
        # Bad status
        payload = {"name": "Test Project", "status": "flying"}
        status, data = self.request("POST", "/api/projects", payload)
        self.assertEqual(status, 400)
        self.assertFalse(data.get("success"))
        self.assertIn("status", data.get("error", "").lower())

        # Valid statuses
        for valid_status in ("planning", "building", "review", "live", "maintenance", "archived"):
            payload = {"name": "Test Project", "status": valid_status}
            status, data = self.request("POST", "/api/projects", payload)
            self.assertEqual(status, 200)
            self.assertEqual(data["project"]["status"], valid_status)
            self.request("DELETE", f"/api/projects/{data['project']['id']}")

        # Bad role
        payload = {"name": "Test Project", "parts": [{"role": "superhero"}]}
        status, data = self.request("POST", "/api/projects", payload)
        self.assertEqual(status, 400)
        self.assertFalse(data.get("success"))
        self.assertIn("role", data.get("error", "").lower())

        # Valid roles
        for valid_role in ("wordpress", "astro", "laravel", "codeigniter", "php", "api", "frontend", "backend", "other"):
            payload = {"name": "Test Project", "parts": [{"role": valid_role}]}
            status, data = self.request("POST", "/api/projects", payload)
            self.assertEqual(status, 200)
            self.assertEqual(data["project"]["parts"][0]["role"], valid_role)
            self.request("DELETE", f"/api/projects/{data['project']['id']}")

    def test_validation_length_limits(self):
        # name empty or > 80
        for bad_name in ("", "   ", "a" * 81):
            payload = {"name": bad_name}
            status, data = self.request("POST", "/api/projects", payload)
            self.assertEqual(status, 400)
            self.assertIn("name", data.get("error", "").lower())

        # client > 80
        payload = {"name": "Test Project", "client": "c" * 81}
        status, data = self.request("POST", "/api/projects", payload)
        self.assertEqual(status, 400)
        self.assertIn("client", data.get("error", "").lower())

        # vault_path > 300 or relative
        payload = {"name": "Test Project", "vault_path": "/valid/" + "a" * 300}
        status, data = self.request("POST", "/api/projects", payload)
        self.assertEqual(status, 400)
        self.assertIn("vault_path", data.get("error", "").lower())

        payload = {"name": "Test Project", "vault_path": "relative/path"}
        status, data = self.request("POST", "/api/projects", payload)
        self.assertEqual(status, 400)
        self.assertIn("vault_path", data.get("error", "").lower())

        # notes > 2000
        payload = {"name": "Test Project", "notes": "n" * 2001}
        status, data = self.request("POST", "/api/projects", payload)
        self.assertEqual(status, 400)
        self.assertIn("notes", data.get("error", "").lower())

        # part label > 80
        payload = {"name": "Test Project", "parts": [{"role": "other", "label": "l" * 81}]}
        status, data = self.request("POST", "/api/projects", payload)
        self.assertEqual(status, 400)
        self.assertIn("label", data.get("error", "").lower())

        # part local_path > 300 or relative
        payload = {"name": "Test Project", "parts": [{"role": "other", "local_path": "/var/" + "p" * 300}]}
        status, data = self.request("POST", "/api/projects", payload)
        self.assertEqual(status, 400)
        self.assertIn("local_path", data.get("error", "").lower())

        payload = {"name": "Test Project", "parts": [{"role": "other", "local_path": "relative/path"}]}
        status, data = self.request("POST", "/api/projects", payload)
        self.assertEqual(status, 400)
        self.assertIn("local_path", data.get("error", "").lower())

        # URL > 500
        long_url = "http://localhost:8080/" + "u" * 500
        payload = {"name": "Test Project", "parts": [{"role": "other", "local_url": long_url}]}
        status, data = self.request("POST", "/api/projects", payload)
        self.assertEqual(status, 400)
        self.assertIn("local_url", data.get("error", "").lower())

        # hosting_name > 80
        payload = {"name": "Test Project", "parts": [{"role": "other", "hosting_name": "h" * 81}]}
        status, data = self.request("POST", "/api/projects", payload)
        self.assertEqual(status, 400)
        self.assertIn("hosting_name", data.get("error", "").lower())

        # part notes > 1000
        payload = {"name": "Test Project", "parts": [{"role": "other", "notes": "n" * 1001}]}
        status, data = self.request("POST", "/api/projects", payload)
        self.assertEqual(status, 400)
        self.assertIn("notes", data.get("error", "").lower())

    def test_validation_max_12_parts(self):
        # 12 parts is OK
        payload_12 = {
            "name": "12 Parts Project",
            "parts": [{"role": "other", "label": f"Part {i}"} for i in range(12)],
        }
        status, data = self.request("POST", "/api/projects", payload_12)
        self.assertEqual(status, 200)
        self.assertEqual(len(data["project"]["parts"]), 12)
        proj_id = data["project"]["id"]

        # 13 parts is rejected
        payload_13 = {
            "name": "13 Parts Project",
            "parts": [{"role": "other", "label": f"Part {i}"} for i in range(13)],
        }
        status, data = self.request("POST", "/api/projects", payload_13)
        self.assertEqual(status, 400)
        self.assertFalse(data.get("success"))
        self.assertIn("parts", data.get("error", "").lower())

        # Cleanup
        self.request("DELETE", f"/api/projects/{proj_id}")

    def test_unknown_fields_dropped_and_strings_trimmed(self):
        payload = {
            "name": "   Padded Name   ",
            "client": "   Padded Client   ",
            "unknown_project_field": "drop_me",
            "parts": [
                {
                    "role": "astro",
                    "label": "   Padded Label   ",
                    "unknown_part_field": 12345,
                }
            ],
        }
        status, data = self.request("POST", "/api/projects", payload)
        self.assertEqual(status, 200)
        proj = data["project"]
        self.assertEqual(proj["name"], "Padded Name")
        self.assertEqual(proj["client"], "Padded Client")
        self.assertNotIn("unknown_project_field", proj)
        self.assertEqual(proj["parts"][0]["label"], "Padded Label")
        self.assertNotIn("unknown_part_field", proj["parts"][0])

        # Also verify raw saved JSON
        file_data = json.loads(self.projects_path.read_text(encoding="utf-8"))
        saved_proj = file_data["projects"][0]
        self.assertEqual(saved_proj["name"], "Padded Name")
        self.assertNotIn("unknown_project_field", saved_proj)
        self.assertNotIn("unknown_part_field", saved_proj["parts"][0])
        # local_running is not stored in file
        self.assertNotIn("local_running", saved_proj["parts"][0])

    def test_part_id_preserved_on_update(self):
        payload = {
            "name": "Multi Part Project",
            "parts": [
                {"role": "wordpress", "label": "Part 1"},
                {"role": "astro", "label": "Part 2"},
            ],
        }
        status, data = self.request("POST", "/api/projects", payload)
        self.assertEqual(status, 200)
        p = data["project"]
        id1 = p["parts"][0]["id"]
        id2 = p["parts"][1]["id"]

        # Update: keep Part 1, replace Part 2 with Part 3 (no id)
        update_payload = {
            "name": "Multi Part Project Updated",
            "parts": [
                {"id": id1, "role": "wordpress", "label": "Part 1 Updated"},
                {"role": "frontend", "label": "Part 3 New"},
            ],
        }
        status, data = self.request("POST", f"/api/projects/{p['id']}", update_payload)
        self.assertEqual(status, 200)
        updated_parts = data["project"]["parts"]
        self.assertEqual(len(updated_parts), 2)
        self.assertEqual(updated_parts[0]["id"], id1)
        self.assertEqual(updated_parts[0]["label"], "Part 1 Updated")
        id3 = updated_parts[1]["id"]
        self.assertTrue(bool(re.fullmatch(r"[0-9a-f]{8}", id3)))
        self.assertNotIn(id3, (id1, id2))

    def test_404_on_unknown_id(self):
        status, data = self.request("POST", "/api/projects/deadbeef", {"name": "No Exist"})
        self.assertEqual(status, 404)
        self.assertFalse(data.get("success"))

        status, data = self.request("DELETE", "/api/projects/deadbeef")
        self.assertEqual(status, 404)
        self.assertFalse(data.get("success"))

        status, data = self.request("POST", "/api/projects/", {"name": "No Exist"})
        self.assertEqual(status, 404)

        status, data = self.request("DELETE", "/api/projects/")
        self.assertEqual(status, 404)

    def test_401_without_token_or_invalid_token(self):
        # Unauthenticated
        status, _ = self.request("GET", "/api/projects", token=None)
        self.assertEqual(status, 401)

        status, _ = self.request("POST", "/api/projects", {"name": "Test"}, token=None)
        self.assertEqual(status, 401)

        status, _ = self.request("DELETE", "/api/projects/abc", token=None)
        self.assertEqual(status, 401)

        # Invalid token
        status, _ = self.request("GET", "/api/projects", token="wrong-token")
        self.assertEqual(status, 401)

    def test_mcp_key_allowed(self):
        # All projects routes work with the MCP key
        status, data = self.request("GET", "/api/projects", token=self.mcp_key)
        self.assertEqual(status, 200)

        payload = {"name": "MCP Project", "parts": [{"role": "api"}]}
        status, data = self.request("POST", "/api/projects", payload, token=self.mcp_key)
        self.assertEqual(status, 200)
        proj_id = data["project"]["id"]

        status, data = self.request("POST", f"/api/projects/{proj_id}", {"name": "MCP Project 2"}, token=self.mcp_key)
        self.assertEqual(status, 200)

        status, data = self.request("DELETE", f"/api/projects/{proj_id}", token=self.mcp_key)
        self.assertEqual(status, 200)

    def test_file_permissions_mode_0600(self):
        payload = {"name": "Permissions Test Project"}
        status, data = self.request("POST", "/api/projects", payload)
        self.assertEqual(status, 200)

        # Check projects.json mode is 0600
        mode = stat.S_IMODE(self.projects_path.stat().st_mode)
        self.assertEqual(mode, 0o600)

        # Check lock file mode is 0600
        lock_path = Path(str(self.projects_path) + ".lock")
        self.assertTrue(lock_path.exists())
        lock_mode = stat.S_IMODE(lock_path.stat().st_mode)
        self.assertEqual(lock_mode, 0o600)

    def test_local_running_socket_checks(self):
        # Start a local socket listening on loopback
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        sock.listen(5)
        open_port = sock.getsockname()[1]

        # Find an unused closed port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as dummy:
            dummy.bind(("127.0.0.1", 0))
            closed_port = dummy.getsockname()[1]

        try:
            payload = {
                "name": "Health Check Test",
                "parts": [
                    {"role": "wordpress", "local_url": f"http://127.0.0.1:{open_port}"},
                    {"role": "astro", "local_url": f"http://localhost:{closed_port}"},
                    {"role": "other"},  # no local_url
                ],
            }
            status, data = self.request("POST", "/api/projects", payload)
            self.assertEqual(status, 200)
            proj_id = data["project"]["id"]

            status, data = self.request("GET", "/api/projects")
            self.assertEqual(status, 200)
            parts = data["projects"][0]["parts"]
            self.assertEqual(parts[0]["local_running"], True)
            self.assertEqual(parts[1]["local_running"], False)
            self.assertIsNone(parts[2]["local_running"])
        finally:
            sock.close()

        # After closing the listening socket, part 0 should now be False
        status, data = self.request("GET", "/api/projects")
        self.assertEqual(status, 200)
        parts = data["projects"][0]["parts"]
        self.assertEqual(parts[0]["local_running"], False)

    def test_corrupt_file_handling(self):
        # Corrupt the projects file
        corrupt_content = b"{invalid json corrupt content"
        self.projects_path.write_bytes(corrupt_content)

        # GET should return 500
        status, data = self.request("GET", "/api/projects")
        self.assertEqual(status, 500)
        self.assertFalse(data.get("success"))
        self.assertIn("corrupt", data.get("error", "").lower())

        # POST create should return 500
        status, data = self.request("POST", "/api/projects", {"name": "Should Fail"})
        self.assertEqual(status, 500)
        self.assertFalse(data.get("success"))

        # POST update should return 500
        status, data = self.request("POST", "/api/projects/a1b2c3d4", {"name": "Should Fail"})
        self.assertEqual(status, 500)
        self.assertFalse(data.get("success"))

        # DELETE should return 500
        status, data = self.request("DELETE", "/api/projects/a1b2c3d4")
        self.assertEqual(status, 500)
        self.assertFalse(data.get("success"))

        # Crucial requirement: never overwrite a corrupt file
        self.assertEqual(self.projects_path.read_bytes(), corrupt_content)


    def test_duplicate_part_ids_in_update_get_unique_ids(self):
        status, data = self.request("POST", "/api/projects", {"name": "Dup", "parts": [{"role": "wordpress"}]})
        self.assertEqual(status, 200)
        project = data["project"]
        pid = project["parts"][0]["id"]
        status, data = self.request("POST", f"/api/projects/{project['id']}", {
            "name": "Dup",
            "parts": [{"id": pid, "role": "wordpress"}, {"id": pid, "role": "astro"}],
        })
        self.assertEqual(status, 200)
        ids = [part["id"] for part in data["project"]["parts"]]
        self.assertEqual(ids[0], pid)
        self.assertEqual(len(set(ids)), 2)

    def test_non_object_entries_in_file_are_reported_as_corrupt(self):
        for content in ({"version": 1, "projects": ["text"]},
                        {"version": 1, "projects": [{"id": "a1b2c3d4", "name": "x", "parts": [1]}]}):
            raw = json.dumps(content).encode()
            self.projects_path.write_bytes(raw)
            status, data = self.request("GET", "/api/projects")
            self.assertEqual(status, 500)
            self.assertIn("corrupt", data.get("error", "").lower())
            self.assertEqual(self.projects_path.read_bytes(), raw)

    def test_existing_lock_file_is_tightened_to_0600(self):
        lock_path = Path(str(self.projects_path) + ".lock")
        lock_path.write_text("")
        os.chmod(lock_path, 0o644)
        status, _ = self.request("POST", "/api/projects", {"name": "Lock"})
        self.assertEqual(status, 200)
        self.assertEqual(lock_path.stat().st_mode & 0o777, 0o600)

if __name__ == "__main__":
    unittest.main()
