# Plain PHP Projects Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add plain PHP project creation and management with optional MySQL database support.

**Architecture:** Follow the existing Laravel and CodeIgniter patterns: a dedicated helper script for privileged file/Nginx work, backend discovery/jobs/routes in `panel.py`, and a dedicated frontend page in `index.html`. Panel-created PHP projects are discovered through `.server-panel-project.json` metadata to avoid touching arbitrary PHP folders.

**Tech Stack:** Python `ThreadingHTTPServer`, shell helper scripts, Nginx, PHP-FPM, MySQL, vanilla JavaScript, Bootstrap 5 UI, Python `unittest`.

## Global Constraints

- Add a new **PHP Projects** section to the sidebar.
- Support panel-created plain PHP projects only for reliable discovery and safe deletion.
- Support three starter templates: `blank`, `php`, and `php_db`.
- Database creation is optional and only enabled for `php_db` projects.
- Auto-suggest the next available port starting from `8300`.
- Do not add Composer, framework scaffolding, or external dependencies for plain PHP projects.
- Store metadata at `<install_path>/.server-panel-project.json`.
- Missing metadata during delete prevents accidental deletion of arbitrary folders.
- Delete removes the database and user only when metadata confirms the panel created them.

---

## File Structure

- Create `php-project-helper.sh`: privileged install/delete/set-port operations for plain PHP projects.
- Modify `setup-sudo.sh`: add passwordless sudo rule for `php-project-helper.sh`.
- Modify `panel.py`: add metadata parsing, discovery, template generation, install/delete jobs, and API routes.
- Modify `index.html`: add PHP Projects page, template selector, optional DB fields, and JS actions.
- Create `tests/test_php_projects_backend.py`: backend tests for metadata discovery and route registration.
- Create `tests/test_php_projects_frontend.py`: frontend structure tests for page fields and JS routes.
- Modify `CLAUDE.md`: document helper, feature, and API routes after implementation.

---

### Task 1: Add PHP Project Helper Script

**Files:**
- Create: `php-project-helper.sh`
- Modify: `setup-sudo.sh`

**Interfaces:**
- Consumes: `sudo php-project-helper.sh install <src_path> <install_path> <site_name> <php_ver> <port>`.
- Consumes: `sudo php-project-helper.sh delete <install_path> <site_name>`.
- Consumes: `sudo php-project-helper.sh set-port <site_name> <port>`.
- Produces: safe privileged file and Nginx operations.

- [ ] **Step 1: Verify helper is missing**

Run: `bash -n php-project-helper.sh`

Expected: FAIL with `No such file or directory`.

- [ ] **Step 2: Create `php-project-helper.sh`**

```bash
#!/bin/bash
# Called by the panel with sudo. Handles privileged plain PHP project file/nginx operations.
# Usage:
#   sudo php-project-helper.sh install <src_path> <install_path> <site_name> <php_ver> <port>
#   sudo php-project-helper.sh delete <install_path> <site_name>
#   sudo php-project-helper.sh set-port <site_name> <port>
set -e

ACTION="$1"
ARG2="$2"
ARG3="$3"
ARG4="$4"
ARG5="$5"
ARG6="$6"

is_safe_path() {
    case "$1" in
        /var/www/*|/opt/*) return 0 ;;
        *) return 1 ;;
    esac
}

is_safe_site() {
    case "$1" in
        *[!A-Za-z0-9._-]*|"") return 1 ;;
        *) return 0 ;;
    esac
}

set_php_project_perms() {
    APP_PATH="$1"
    chown -R www-data:www-data "$APP_PATH"
    find "$APP_PATH" -type d -exec chmod 2775 {} \;
    find "$APP_PATH" -type f -exec chmod 664 {} \;
    if [ -f "$APP_PATH/config.php" ]; then chmod 660 "$APP_PATH/config.php"; fi
    if [ -f "$APP_PATH/.server-panel-project.json" ]; then chmod 660 "$APP_PATH/.server-panel-project.json"; fi
}

reload_or_start_nginx() {
    if systemctl is-active --quiet nginx; then
        systemctl reload nginx
    else
        systemctl start nginx
    fi
}

case "$ACTION" in
  install)
    SRC_PATH="$ARG2"
    INSTALL_PATH="$ARG3"
    SITE_NAME="$ARG4"
    PHP_VER="$ARG5"
    PORT="$ARG6"

    is_safe_path "$INSTALL_PATH" || { echo "Error: unsafe install path"; exit 1; }
    is_safe_site "$SITE_NAME" || { echo "Error: bad site name"; exit 1; }
    [ -d "$SRC_PATH" ] || { echo "Error: source path not found"; exit 1; }

    mkdir -p "$INSTALL_PATH"
    cp -a "$SRC_PATH/." "$INSTALL_PATH/"
    set_php_project_perms "$INSTALL_PATH"

    cat > "/etc/nginx/sites-available/$SITE_NAME" <<EOF
server {
    listen $PORT;
    server_name localhost;
    root $INSTALL_PATH;
    index index.php index.html;

    location / {
        try_files \$uri \$uri/ /index.php?\$query_string;
    }

    location ~ \.php$ {
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:/run/php/php$PHP_VER-fpm.sock;
    }

    location ~ /\. {
        deny all;
    }
}
EOF
    ln -sf "/etc/nginx/sites-available/$SITE_NAME" "/etc/nginx/sites-enabled/$SITE_NAME"
    nginx -t
    reload_or_start_nginx
    echo "[helper] PHP project installed at $INSTALL_PATH"
    ;;

  delete)
    INSTALL_PATH="$ARG2"
    SITE_NAME="$ARG3"
    is_safe_path "$INSTALL_PATH" || { echo "Error: unsafe install path"; exit 1; }
    is_safe_site "$SITE_NAME" || { echo "Error: bad site name"; exit 1; }
    [ -f "$INSTALL_PATH/.server-panel-project.json" ] || { echo "Error: missing project metadata"; exit 1; }
    rm -f "/etc/nginx/sites-enabled/$SITE_NAME" "/etc/nginx/sites-available/$SITE_NAME"
    rm -rf "$INSTALL_PATH"
    nginx -t
    reload_or_start_nginx
    echo "[helper] PHP project deleted: $INSTALL_PATH"
    ;;

  set-port)
    SITE_NAME="$ARG2"
    PORT="$ARG3"
    is_safe_site "$SITE_NAME" || { echo "Error: bad site name"; exit 1; }
    case "$PORT" in ''|*[!0-9]*) echo "Error: bad port"; exit 1 ;; esac
    SITE_CONF="/etc/nginx/sites-available/$SITE_NAME"
    [ -f "$SITE_CONF" ] || { echo "Error: nginx site not found"; exit 1; }
    python3 - "$SITE_CONF" "$PORT" <<'PY'
import re, sys
path, port = sys.argv[1:3]
content = open(path).read()
content, count = re.subn(r'(?m)^(\s*listen\s+)(?:\[::\]:)?\d+((?:\s+[^;]*)?;)', rf'\g<1>{port}\2', content, count=1)
if not count:
    raise SystemExit('Error: no listen directive found')
open(path, 'w').write(content)
PY
    nginx -t
    reload_or_start_nginx
    echo "[helper] Changed $SITE_NAME to port $PORT"
    ;;

  *)
    echo "Usage: php-project-helper.sh install|delete|set-port ..."
    exit 1
    ;;
esac
```

- [ ] **Step 3: Add sudoers rule**

Modify `setup-sudo.sh` after the CodeIgniter helper rule:

```bash
$USER ALL=(ALL) NOPASSWD: /home/$USER/Documents/server-panel/php-project-helper.sh *
```

- [ ] **Step 4: Verify helper syntax**

Run: `chmod +x php-project-helper.sh && bash -n php-project-helper.sh setup-sudo.sh`

Expected: exit code `0` with no output.

---

### Task 2: Add Backend PHP Project Support

**Files:**
- Modify: `panel.py`
- Create: `tests/test_php_projects_backend.py`

**Interfaces:**
- Produces: `PHP_PROJECT_META = ".server-panel-project.json"`.
- Produces: `read_php_project_metadata(project_path: str) -> dict`.
- Produces: `get_php_projects() -> list[dict]`.
- Produces: `write_php_project_files(src_dir: str, metadata: dict, db_pass: str = "") -> None`.
- Produces: `install_php_project_job(job_id: str, params: dict, cfg: dict) -> None`.
- Produces: `delete_php_project_job(job_id: str, app_path: str, db_name: str, db_user: str, nginx_site: str, cfg: dict) -> None`.

- [ ] **Step 1: Write failing backend tests**

Create `tests/test_php_projects_backend.py`:

```python
import inspect
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import panel


class PhpProjectsBackendTests(unittest.TestCase):
    def test_discovers_panel_created_php_project_from_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            app_path = os.path.join(tmp, "plainphp")
            os.makedirs(app_path)
            meta_path = os.path.join(app_path, ".server-panel-project.json")
            with open(meta_path, "w") as f:
                json.dump({
                    "type": "php",
                    "name": "plainphp",
                    "template": "php_db",
                    "install_path": app_path,
                    "nginx_site": "plainphp",
                    "port": 8300,
                    "db_name": "plainphp_db",
                    "db_user": "plainphp_user",
                    "db_created": True,
                    "created_at": 123,
                }, f)

            with mock.patch.object(panel.glob, "glob", return_value=[meta_path]), \
                 mock.patch.object(panel, "find_nginx_site_for_path", return_value="plainphp"), \
                 mock.patch.object(panel, "get_nginx_site_port", return_value=8300):
                apps = panel.get_php_projects()

        self.assertEqual(len(apps), 1)
        self.assertEqual(apps[0]["name"], "plainphp")
        self.assertEqual(apps[0]["template"], "php_db")
        self.assertEqual(apps[0]["path"], app_path)
        self.assertEqual(apps[0]["db_name"], "plainphp_db")
        self.assertEqual(apps[0]["db_user"], "plainphp_user")
        self.assertTrue(apps[0]["db_created"])
        self.assertEqual(apps[0]["nginx_site"], "plainphp")
        self.assertEqual(apps[0]["port"], 8300)

    def test_template_generation_for_php_db_contains_config_and_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            metadata = {
                "type": "php",
                "name": "plainphp",
                "template": "php_db",
                "install_path": "/var/www/plainphp",
                "nginx_site": "plainphp",
                "port": 8300,
                "db_name": "plainphp_db",
                "db_user": "plainphp_user",
                "db_created": True,
                "created_at": 123,
            }
            panel.write_php_project_files(tmp, metadata, "secretpass")
            self.assertTrue(os.path.exists(os.path.join(tmp, "index.php")))
            self.assertTrue(os.path.exists(os.path.join(tmp, "config.php")))
            self.assertTrue(os.path.exists(os.path.join(tmp, ".server-panel-project.json")))
            config = open(os.path.join(tmp, "config.php")).read()
            self.assertIn("plainphp_db", config)
            self.assertIn("plainphp_user", config)
            self.assertIn("secretpass", config)

    def test_handler_declares_php_project_routes(self):
        source = inspect.getsource(panel.Handler)
        for route in [
            "/api/php-projects/apps",
            "/api/php-projects/next_port",
            "/api/php-projects/install",
            "/api/php-projects/port",
            "/api/php-projects/install/",
            "/api/php-projects/delete/",
        ]:
            self.assertIn(route, source)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run backend tests to verify failure**

Run: `python3 -m unittest tests.test_php_projects_backend -v`

Expected: FAIL because `get_php_projects` and `write_php_project_files` do not exist and routes are missing.

- [ ] **Step 3: Implement backend functions in `panel.py` after CodeIgniter functions**

Add `PHP_PROJECT_META`, `read_php_project_metadata`, `get_php_projects`, `php_export`, `write_php_project_files`, `install_php_project_job`, and `delete_php_project_job`. Use the same sanitization patterns as Laravel and CodeIgniter, `find_next_port(8300)`, and `php-project-helper.sh`.

- [ ] **Step 4: Add routes**

Add GET, POST, DELETE, and job polling routes for `/api/php-projects/...` next to the CodeIgniter routes.

- [ ] **Step 5: Verify backend**

Run:

```bash
python3 -m py_compile panel.py
python3 -m unittest tests.test_php_projects_backend -v
```

Expected: both commands exit `0`; tests report `OK`.

---

### Task 3: Add PHP Projects Frontend

**Files:**
- Modify: `index.html`
- Create: `tests/test_php_projects_frontend.py`

**Interfaces:**
- Consumes backend routes from Task 2.
- Produces page id `page-php-projects`.
- Produces JS functions `phpProjectAutoFill`, `loadPhpProjectNextPort`, `loadPhpProjects`, `togglePhpProjectDbFields`, `genPhpProjectDbPass`, `startPhpProjectInstall`, `changePhpProjectPort`, `deletePhpProject`.

- [ ] **Step 1: Write failing frontend tests**

Create `tests/test_php_projects_frontend.py`:

```python
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
```

- [ ] **Step 2: Run frontend tests to verify failure**

Run: `python3 -m unittest tests.test_php_projects_frontend -v`

Expected: FAIL because the page, fields, functions, and routes are not in `index.html`.

- [ ] **Step 3: Add sidebar and page markup**

Add a **PHP Projects** sidebar item under CodeIgniter. Add a page after CodeIgniter with installed projects and create tabs. Include the template selector with `blank`, `php`, and `php_db`; show DB fields only when `php_db` is selected.

- [ ] **Step 4: Add JavaScript functions**

Add JS functions listed in Interfaces. Follow the CodeIgniter section style, use `/api/php-projects/...`, default port `8300`, and include phpMyAdmin action only when a DB exists.

- [ ] **Step 5: Verify frontend**

Run:

```bash
python3 -m unittest tests.test_php_projects_frontend -v
python3 - <<'PY'
from pathlib import Path
html = Path('index.html').read_text()
start = html.index('<script>') + len('<script>')
end = html.rindex('</script>')
Path('/tmp/opencode/server-panel-inline.js').write_text(html[start:end])
PY
node --check "/tmp/opencode/server-panel-inline.js"
```

Expected: tests report `OK`; Node exits `0` with no output.

---

### Task 4: Documentation, Verification, Commit, Push

**Files:**
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes completed helper, backend, and frontend tasks.
- Produces documented and pushed PHP Projects feature.

- [ ] **Step 1: Update docs**

Add `php-project-helper.sh` to the file table. Add a **PHP Projects** feature section and these API routes:

```markdown
| GET | `/api/php-projects/apps` | List panel-created PHP projects |
| GET | `/api/php-projects/next_port` | Find next available suggested PHP project port |
| POST | `/api/php-projects/install` | Start plain PHP project install job |
| GET | `/api/php-projects/install/<job_id>` | Poll PHP project install progress |
| POST | `/api/php-projects/port` | Change a PHP project Nginx site listen port |
| DELETE | `/api/php-projects/apps` | Start PHP project delete job |
| GET | `/api/php-projects/delete/<job_id>` | Poll PHP project delete progress |
```

- [ ] **Step 2: Run final verification**

Run:

```bash
python3 -m py_compile panel.py
python3 -m unittest discover -s tests -v
bash -n setup-sudo.sh wp-install-helper.sh wp-delete-helper.sh laravel-helper.sh codeigniter-helper.sh php-project-helper.sh perf-helper.sh start-panel.sh
node --check "/tmp/opencode/server-panel-inline.js"
git diff --check
git status --short
```

Expected:

```text
panel.py compiles
all unittest tests pass
all shell scripts pass bash -n
inline frontend JS passes node --check
```

- [ ] **Step 3: Commit and push**

Run:

```bash
git status --short
git diff
git log --oneline -10
git add panel.py index.html setup-sudo.sh php-project-helper.sh CLAUDE.md tests/test_php_projects_backend.py tests/test_php_projects_frontend.py docs/superpowers/plans/2026-07-25-plain-php-projects.md
git commit -m "Add plain PHP project management"
git push
```

Expected: push updates `origin/main` with the spec commit and implementation commit.

---

## Self-Review

- Spec coverage: this plan covers sidebar/page, three templates, optional DB only for `php_db`, metadata discovery, helper script, API routes, delete safety, sudoers, tests, docs, commit, and push.
- Placeholder scan: no TBD/TODO/fill-in-later steps remain.
- Type consistency: backend function names, JS function names, metadata keys, and API paths are consistent across tasks.
