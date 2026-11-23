import json
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from scripts.demo_server import create_server


def test_demo_serves_the_panel_and_refuses_changes(monkeypatch):
    monkeypatch.setenv("no_proxy", "*")
    monkeypatch.setenv("NO_PROXY", "*")
    with create_server(0) as server:
        worker = Thread(target=server.serve_forever)
        worker.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}"
            with urlopen(base + "/?theme=dark", timeout=5) as response:
                html = response.read()
                assert b"<head>\n<script>" in html
                assert b"localStorage.setItem('panel_token', 'demo')" in html
                assert b'id="login-screen"' in html

            with urlopen(base + "/assets/fonts/plus-jakarta-sans-latin.woff2", timeout=5) as response:
                assert response.headers.get_content_type() == "font/woff2"
                assert response.read(4) == b"wOF2"

            with pytest.raises(HTTPError) as error:
                urlopen(base + "/assets/%2e%2e/index.html", timeout=5)
            assert error.value.code == 404
            error.value.close()

            with urlopen(base + "/api/status", timeout=5) as response:
                status = json.load(response)
                assert set(status) == {"nginx", "mysql", "system"}
                assert status["system"]["hostname"] == "dev-laptop"

            # Demo projects route returns 2 fake projects
            with urlopen(base + "/api/projects", timeout=5) as response:
                projects_payload = json.load(response)
                assert "projects" in projects_payload
                projects = projects_payload["projects"]
                assert len(projects) == 2
                assert projects[0]["name"] == "Acme Shop"
                assert projects[1]["name"] == "Demo Blog"
                # Check parts on Acme Shop
                acme_parts = projects[0]["parts"]
                assert len(acme_parts) == 2
                roles = {p["role"] for p in acme_parts}
                assert roles == {"wordpress", "astro"}
                for p in acme_parts:
                    assert "example.com" in (p.get("live_url") or "")

            # Mutations are disabled
            request = Request(base + "/api/mysql/databases", data=b"{}", method="POST")
            with urlopen(request, timeout=5) as response:
                assert json.load(response) == {
                    "success": False,
                    "error": "Demo mode: changes are disabled.",
                }

            request = Request(base + "/api/projects", data=b"{}", method="POST")
            with urlopen(request, timeout=5) as response:
                assert json.load(response) == {
                    "success": False,
                    "error": "Demo mode: changes are disabled.",
                }

            request = Request(base + "/api/projects/a1b2c3d4", method="DELETE")
            with urlopen(request, timeout=5) as response:
                assert json.load(response) == {
                    "success": False,
                    "error": "Demo mode: changes are disabled.",
                }
        finally:
            server.shutdown()
            worker.join()
