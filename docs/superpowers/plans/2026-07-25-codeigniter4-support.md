# CodeIgniter 4 Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add CodeIgniter 4 app creation and management to the local server panel.

**Architecture:** Mirror the existing Laravel flow with a dedicated backend module section in `panel.py`, a dedicated sudo helper script, and a dedicated frontend page in `index.html`. CodeIgniter apps are Composer-created in a temporary directory, configured with `.env`, installed into `/var/www` or `/opt`, and served through Nginx with `public/` as the webroot.

**Tech Stack:** Python `ThreadingHTTPServer`, shell helper scripts, Nginx, PHP-FPM, MySQL, Composer, CodeIgniter 4, vanilla JS, Bootstrap 5 UI.

## Global Constraints

- Support CodeIgniter 4 only.
- Create new apps with Composer using `codeigniter4/appstarter`.
- Detect existing CodeIgniter 4 apps in `/var/www`, `/opt`, and one nested `/opt/*/*` level.
- Manage Nginx virtual hosts for local ports.
- Create and delete the app database and database user.
- Do not support CodeIgniter 3 creation or migration in this version.
- Keep `panel_config.json`, cache files, local editor files, pycache, and plugin zip files untracked.
- Do not add external Python dependencies.

---

## File Structure

- Create `codeigniter-helper.sh`: privileged file, permissions, Nginx install/delete/set-port operations for CodeIgniter apps.
- Modify `panel.py`: add CodeIgniter discovery, install/delete jobs, port change API, and job polling routes.
- Modify `index.html`: add sidebar entry, page markup, and JavaScript for listing, creating, changing port, and deleting CodeIgniter apps.
- Modify `setup-sudo.sh`: allow passwordless sudo for `codeigniter-helper.sh` with arguments.
- Modify `CLAUDE.md`: document the new helper and CodeIgniter API routes/features after implementation.

---

### Task 1: Add CodeIgniter Helper Script

**Files:**
- Create: `codeigniter-helper.sh`
- Modify: `setup-sudo.sh`

**Interfaces:**
- Consumes: `sudo codeigniter-helper.sh install <src_path> <install_path> <site_name> <php_ver> <port>` from `panel.py`.
- Consumes: `sudo codeigniter-helper.sh delete <install_path> <site_name>` from `panel.py`.
- Consumes: `sudo codeigniter-helper.sh set-port <site_name> <port>` from `panel.py`.
- Produces: safe privileged operations with Nginx validation and reload.

- [ ] **Step 1: Write the helper script**

Create `codeigniter-helper.sh` with this structure:

```bash
#!/bin/bash
# Called by the panel with sudo. Handles privileged CodeIgniter file/nginx operations.
# Usage:
#   sudo codeigniter-helper.sh install <src_path> <install_path> <site_name> <php_ver> <port>
#   sudo codeigniter-helper.sh delete <install_path> <site_name>
#   sudo codeigniter-helper.sh set-port <site_name> <port>
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

set_codeigniter_perms() {
    APP_PATH="$1"
    chown -R www-data:www-data "$APP_PATH"
    find "$APP_PATH" -type d -exec chmod 2775 {} \;
    find "$APP_PATH" -type f -exec chmod 664 {} \;
    if [ -d "$APP_PATH/writable" ]; then chmod -R 2775 "$APP_PATH/writable"; fi
    if [ -f "$APP_PATH/.env" ]; then chmod 660 "$APP_PATH/.env"; fi
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
    set_codeigniter_perms "$INSTALL_PATH"

    cat > "/etc/nginx/sites-available/$SITE_NAME" <<EOF
server {
    listen $PORT;
    server_name localhost;
    root $INSTALL_PATH/public;
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
    echo "[helper] CodeIgniter installed at $INSTALL_PATH"
    ;;

  delete)
    INSTALL_PATH="$ARG2"
    SITE_NAME="$ARG3"
    is_safe_path "$INSTALL_PATH" || { echo "Error: unsafe install path"; exit 1; }
    is_safe_site "$SITE_NAME" || { echo "Error: bad site name"; exit 1; }
    rm -f "/etc/nginx/sites-enabled/$SITE_NAME" "/etc/nginx/sites-available/$SITE_NAME"
    rm -rf "$INSTALL_PATH"
    nginx -t
    reload_or_start_nginx
    echo "[helper] CodeIgniter deleted: $INSTALL_PATH"
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
    echo "Usage: codeigniter-helper.sh install|delete|set-port ..."
    exit 1
    ;;
esac
```

- [ ] **Step 2: Add sudoers rule**

Modify `setup-sudo.sh` after the Laravel helper rule:

```bash
$USER ALL=(ALL) NOPASSWD: /home/$USER/Documents/server-panel/codeigniter-helper.sh *
```

- [ ] **Step 3: Validate shell syntax**

Run: `bash -n codeigniter-helper.sh setup-sudo.sh`

Expected: exit code `0` with no output.

---

### Task 2: Add Backend CodeIgniter APIs

**Files:**
- Modify: `panel.py`

**Interfaces:**
- Produces: `get_codeigniter_apps() -> list[dict]`.
- Produces: `install_codeigniter_job(job_id: str, params: dict, cfg: dict) -> None`.
- Produces: `delete_codeigniter_job(job_id: str, app_path: str, db_name: str, db_user: str, nginx_site: str, cfg: dict) -> None`.
- Produces API routes listed in the design spec.

- [ ] **Step 1: Add discovery and job functions after Laravel functions**

Insert after `delete_laravel_job`:

```python
def get_codeigniter_apps():
    apps = []
    patterns = ["/var/www/*/spark", "/opt/*/spark", "/opt/*/*/spark"]
    found = []
    for p in patterns:
        found.extend(glob.glob(p))
    for spark in sorted(set(found)):
        app_path = os.path.dirname(spark)
        name = os.path.basename(app_path)
        env = read_env_file(os.path.join(app_path, ".env"))
        nginx_site = find_nginx_site_for_path(os.path.join(app_path, "public")) or find_nginx_site_for_path(app_path) or name
        version = ""
        r = run_cmd(f"cd {shell_quote(app_path)} && php spark --version", timeout=10)
        if r["success"]:
            version = r["stdout"].strip() or r["stderr"].strip()
        apps.append({
            "name": name,
            "path": app_path,
            "app_url": env.get("app.baseURL", ""),
            "db_name": env.get("database.default.database", ""),
            "db_user": env.get("database.default.username", ""),
            "db_pass": env.get("database.default.password", ""),
            "nginx_site": nginx_site,
            "port": get_nginx_site_port(nginx_site),
            "version": version,
        })
    return apps


def install_codeigniter_job(job_id, params, cfg):
    job = _jobs[job_id]

    def log(msg):
        job["logs"].append(msg)
        print(msg)

    created = {"src": "", "dir": False, "db": False, "db_user": False, "nginx": False}
    site_name = install_path = db_name = db_user = None
    try:
        site_name = re.sub(r"[^\w\-]", "", params.get("site_name", "codeigniter"))
        if not site_name:
            raise ValueError("Site name is invalid")
        install_path = validate_install_path(params.get("install_path", f"/var/www/{site_name}"))
        db_name = re.sub(r"[^\w\-]", "", params.get("db_name", f"{site_name}_db"))
        db_user = re.sub(r"[^\w\-]", "", params.get("db_user", f"{site_name[:16]}_user"))
        db_pass = params.get("db_pass") or secrets.token_urlsafe(14)
        if not db_name or not db_user:
            raise ValueError("Database name or user is invalid")
        if "'" in db_pass or "\\" in db_pass:
            raise ValueError("Database password cannot contain single quotes or backslashes")
        port = parse_port(params.get("port", 8200), 8200)
        php_ver, _ = detect_php_fpm()

        r = run_cmd("command -v composer")
        if not r["success"]:
            raise Exception("Composer is not installed. Install Composer first to create CodeIgniter apps.")

        tmp_src = f"/tmp/_panel_codeigniter_{site_name}_{secrets.token_hex(4)}"
        created["src"] = tmp_src

        log("▶ [1/6] Creating CodeIgniter 4 project with Composer…")
        r = run_cmd(f"composer create-project codeigniter4/appstarter {shell_quote(tmp_src)} --no-interaction", timeout=1800)
        if not r["success"]:
            raise Exception("Composer create-project failed:\n" + (r["stderr"] or r["stdout"]))
        log("  CodeIgniter project created")

        log(f"▶ [2/6] Creating database '{db_name}' and user '{db_user}'…")
        sql = f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
        r = mysql_cmd(cfg, sql)
        if r.get("stderr") and "ERROR" in r["stderr"]:
            raise Exception("MySQL error (create db): " + r["stderr"])
        created["db"] = True
        sql = (
            f"CREATE USER IF NOT EXISTS '{db_user}'@'localhost' IDENTIFIED WITH mysql_native_password BY '{db_pass}';\n"
            f"GRANT ALL PRIVILEGES ON `{db_name}`.* TO '{db_user}'@'localhost';\nFLUSH PRIVILEGES;"
        )
        r = mysql_cmd(cfg, sql)
        if r.get("stderr") and "ERROR" in r["stderr"]:
            raise Exception("MySQL error (create user): " + r["stderr"])
        created["db_user"] = True

        log("▶ [3/6] Writing CodeIgniter .env…")
        env_path = os.path.join(tmp_src, ".env")
        env_content = open(env_path).read() if os.path.exists(env_path) else ""
        for key, value in {
            "CI_ENVIRONMENT": "development",
            "app.baseURL": f"http://localhost:{port}/",
            "database.default.hostname": "127.0.0.1",
            "database.default.database": db_name,
            "database.default.username": db_user,
            "database.default.password": db_pass,
            "database.default.DBDriver": "MySQLi",
            "database.default.port": "3306",
        }.items():
            env_content = set_env_value(env_content, key, value)
        open(env_path, "w").write(env_content)

        log("▶ [4/6] Preparing CodeIgniter app…")
        writable = os.path.join(tmp_src, "writable")
        os.makedirs(writable, exist_ok=True)

        log("▶ [5/6] Installing files and Nginx site…")
        helper = os.path.join(SCRIPT_DIR, "codeigniter-helper.sh")
        r = run_cmd(
            f"sudo {shell_quote(helper)} install {shell_quote(tmp_src)} {shell_quote(install_path)} {shell_quote(site_name)} {shell_quote(php_ver)} {shell_quote(port)}",
            timeout=120,
        )
        if not r["success"]:
            raise Exception("System setup failed:\n" + r["stdout"] + r["stderr"])
        created["dir"] = True
        created["nginx"] = True
        log(r["stdout"].strip())

        log("▶ [6/6] Done!")
        log(f"  URL: http://localhost:{port}")
        job["status"] = "done"
        job["result"] = {"success": True, "url": f"http://localhost:{port}", "install_path": install_path, "db_name": db_name, "db_user": db_user, "db_pass": db_pass, "nginx_site": site_name}
    except Exception as e:
        log(f"\n✖ Error: {e}")
        log("↩ Rolling back what was created…")
        if created.get("db_user") and db_user:
            mysql_cmd(cfg, f"DROP USER IF EXISTS '{db_user}'@'localhost'; FLUSH PRIVILEGES;")
        if created.get("db") and db_name:
            mysql_cmd(cfg, f"DROP DATABASE IF EXISTS `{db_name}`;")
        if created.get("dir") or created.get("nginx"):
            helper = os.path.join(SCRIPT_DIR, "codeigniter-helper.sh")
            run_cmd(f"sudo {shell_quote(helper)} delete {shell_quote(install_path or '')} {shell_quote(site_name or '')}", timeout=60)
        job["status"] = "error"
        job["result"] = {"success": False, "error": str(e)}
    finally:
        if created.get("src"):
            run_cmd(f"rm -rf {shell_quote(created['src'])}")


def delete_codeigniter_job(job_id, app_path, db_name, db_user, nginx_site, cfg):
    job = _jobs[job_id]
    def log(msg):
        job["logs"].append(msg); print(msg)
    try:
        if db_name and re.fullmatch(r"[\w\-]+", db_name):
            log(f"▶ Dropping database '{db_name}'…")
            mysql_cmd(cfg, f"DROP DATABASE IF EXISTS `{db_name}`;")
        if db_user and db_user not in ("root", "—") and re.fullmatch(r"[\w\-]+", db_user):
            log(f"▶ Dropping user '{db_user}'…")
            mysql_cmd(cfg, f"DROP USER IF EXISTS '{db_user}'@'localhost'; FLUSH PRIVILEGES;")
        log("▶ Removing files and Nginx site…")
        helper = os.path.join(SCRIPT_DIR, "codeigniter-helper.sh")
        r = run_cmd(f"sudo {shell_quote(helper)} delete {shell_quote(app_path)} {shell_quote(nginx_site)}", timeout=60)
        log((r["stdout"] + r["stderr"]).strip())
        job["status"] = "done"
        job["result"] = {"success": True}
    except Exception as e:
        log(f"✖ Error: {e}")
        job["status"] = "error"
        job["result"] = {"success": False, "error": str(e)}
```

- [ ] **Step 2: Add GET routes**

In `do_GET`, add:

```python
        elif path == "/api/codeigniter/apps":
            self.send_json({"success": True, "apps": get_codeigniter_apps()})

        elif path == "/api/codeigniter/next_port":
            self.send_json({"success": True, "port": find_next_port(8200)})
```

Extend the job polling condition:

```python
        elif path.startswith("/api/codeigniter/install/") or path.startswith("/api/codeigniter/delete/"):
            job_id = path.split("/")[-1]
            if job_id in _jobs:
                self.send_json(_jobs[job_id])
            else:
                self.send_json({"error": "Job not found"}, 404)
```

- [ ] **Step 3: Add POST routes**

In `do_POST`, add:

```python
        elif path == "/api/codeigniter/install":
            job_id = secrets.token_hex(8)
            _jobs[job_id] = {"status": "running", "logs": [], "result": {}}
            t = threading.Thread(target=install_codeigniter_job, args=(job_id, data, cfg), daemon=True)
            t.start()
            self.send_json({"success": True, "job_id": job_id})

        elif path == "/api/codeigniter/port":
            nginx_site = data.get("nginx_site", "")
            try:
                port = parse_port(data.get("port"), None)
            except ValueError as e:
                self.send_json({"success": False, "error": str(e)}); return
            helper = os.path.join(SCRIPT_DIR, "codeigniter-helper.sh")
            r = run_cmd(f"sudo {shell_quote(helper)} set-port {shell_quote(nginx_site)} {shell_quote(port)}", timeout=30)
            self.send_json({**r, "port": port})
```

- [ ] **Step 4: Add DELETE route**

In `do_DELETE`, add:

```python
        elif path == "/api/codeigniter/apps":
            app_path   = data.get("path", "")
            db_name    = data.get("db_name", "")
            db_user    = data.get("db_user", "")
            nginx_site = data.get("nginx_site", "")
            job_id     = secrets.token_hex(8)
            _jobs[job_id] = {"status": "running", "logs": [], "result": {}}
            t = threading.Thread(
                target=delete_codeigniter_job,
                args=(job_id, app_path, db_name, db_user, nginx_site, cfg),
                daemon=True,
            )
            t.start()
            self.send_json({"success": True, "job_id": job_id})
```

- [ ] **Step 5: Validate Python syntax**

Run: `python3 -m py_compile panel.py`

Expected: exit code `0` with no output.

---

### Task 3: Add CodeIgniter Frontend Page

**Files:**
- Modify: `index.html`

**Interfaces:**
- Consumes: `/api/codeigniter/apps`, `/api/codeigniter/next_port`, `/api/codeigniter/install`, `/api/codeigniter/install/<job_id>`, `/api/codeigniter/port`, `/api/codeigniter/apps` DELETE, `/api/codeigniter/delete/<job_id>`.
- Produces: sidebar page `codeigniter`, form fields with `ci-*` IDs, and JS functions named `loadCodeIgniterApps`, `loadCodeIgniterNextPort`, `codeIgniterAutoFill`, `genCodeIgniterDbPass`, `startCodeIgniterInstall`, `changeCodeIgniterPort`, `deleteCodeIgniterApp`.

- [ ] **Step 1: Add sidebar entry and page title**

Add under Laravel in the sidebar:

```html
<a href="#codeigniter" onclick="showPage('codeigniter',this); return false;"><i class="bi bi-braces"></i> CodeIgniter</a>
```

Add to `pageTitles`:

```javascript
codeigniter:'CodeIgniter'
```

Add to `showPage` loading logic:

```javascript
if (name === 'codeigniter') { loadCodeIgniterApps(); loadCodeIgniterNextPort(); }
```

- [ ] **Step 2: Add page markup after Laravel page**

Create `page-codeigniter` mirroring Laravel with `ci-*` IDs: `ci-site-name`, `ci-install-path`, `ci-port`, `ci-port-preview`, `ci-db-name`, `ci-db-user`, `ci-db-pass`, `ci-install-btn`, `ci-install-log`, `ci-install-result`, `ci-result-url`, and `codeigniter-apps-container`.

- [ ] **Step 3: Add JavaScript functions**

Add a CodeIgniter section near the Laravel JavaScript section with:

```javascript
let codeIgniterPollInterval = null;
let codeIgniterDeletePollInterval = null;

function codeIgniterAutoFill() {
  const raw = document.getElementById('ci-site-name').value.toLowerCase().replace(/[^a-z0-9-]/g,'');
  document.getElementById('ci-site-name').value = raw;
  document.getElementById('ci-install-path').value = raw ? `/var/www/${raw}` : '';
  document.getElementById('ci-db-name').value = raw ? `${raw.replace(/-/g,'_')}_db` : '';
  document.getElementById('ci-db-user').value = raw ? `${raw.replace(/-/g,'_').slice(0,16)}_user` : '';
}

function genCodeIgniterDbPass() {
  document.getElementById('ci-db-pass').value = Math.random().toString(36).slice(2) + Math.random().toString(36).slice(2);
}

async function loadCodeIgniterNextPort() {
  const r = await api('/api/codeigniter/next_port');
  if (r.success) {
    document.getElementById('ci-port').value = r.port;
    document.getElementById('ci-port-preview').textContent = r.port;
  }
}

async function loadCodeIgniterApps() {
  const container = document.getElementById('codeigniter-apps-container');
  const r = await api('/api/codeigniter/apps');
  if (!r.success || !r.apps.length) {
    container.innerHTML = `<div class="empty-state"><i class="bi bi-braces"></i>No CodeIgniter apps found<br><small style="color:#585b70">Searched in /var/www and /opt</small></div>`;
    return;
  }
  container.innerHTML = r.apps.map(app => {
    const url = app.port ? `http://localhost:${app.port}` : (app.app_url || '#');
    const pma = app.db_name ? `http://localhost:8081/index.php?route=/database/structure&db=${encodeURIComponent(app.db_name)}` : '#';
    return `<div class="service-card mb-3">
      <div class="d-flex justify-content-between align-items-start">
        <div>
          <div class="section-title mb-1"><i class="bi bi-braces"></i> ${esc(app.name)}</div>
          <div style="font-size:.8rem;color:#6c7086;"><code>${esc(app.path)}</code></div>
          <div style="font-size:.75rem;color:#585b70;margin-top:4px;">${esc(app.version || 'CodeIgniter 4')}</div>
        </div>
        <button class="btn btn-sm btn-outline-danger" style="padding:2px 8px;font-size:.72rem;" onclick="deleteCodeIgniterApp('${esc(app.name)}','${esc(app.path)}','${esc(app.db_name||'')}','${esc(app.db_user||'')}','${esc(app.nginx_site||app.name)}')"><i class="bi bi-trash"></i> Delete</button>
      </div>
      <hr style="border-color:#2d3158;margin:12px 0;">
      <div class="row g-2" style="font-size:.82rem;">
        <div class="col-md-3"><span style="color:#585b70;">Port</span><br><b>${esc(app.port || '—')}</b></div>
        <div class="col-md-3"><span style="color:#585b70;">Database</span><br><b>${esc(app.db_name || '—')}</b></div>
        <div class="col-md-3"><span style="color:#585b70;">DB User</span><br><b>${esc(app.db_user || '—')}</b></div>
        <div class="col-md-3"><span style="color:#585b70;">Nginx Site</span><br><b>${esc(app.nginx_site || '—')}</b></div>
      </div>
      <div class="d-flex gap-2 flex-wrap mt-3">
        <a class="btn btn-sm btn-outline-primary" href="${url}" target="_blank"><i class="bi bi-globe"></i> Open App</a>
        <a class="btn btn-sm btn-outline-warning ${app.db_name ? '' : 'disabled'}" href="${pma}" target="_blank"><i class="bi bi-database"></i> phpMyAdmin</a>
        <button class="btn btn-sm btn-outline-secondary" onclick="changeCodeIgniterPort('${esc(app.name)}','${esc(app.nginx_site||app.name)}','${esc(app.port||'')}')"><i class="bi bi-router"></i> Port</button>
      </div>
    </div>`;
  }).join('');
}

async function startCodeIgniterInstall() {
  const siteName = document.getElementById('ci-site-name').value.trim();
  const installPath = document.getElementById('ci-install-path').value.trim();
  const port = document.getElementById('ci-port').value.trim();
  const dbName = document.getElementById('ci-db-name').value.trim();
  const dbUser = document.getElementById('ci-db-user').value.trim();
  const dbPass = document.getElementById('ci-db-pass').value.trim();
  const log = document.getElementById('ci-install-log');
  const btn = document.getElementById('ci-install-btn');
  if (!siteName || !installPath || !port || !dbName || !dbUser) { toast('Fill all required fields', 'error'); return; }
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-sm"></span> Creating...';
  log.textContent = 'Starting CodeIgniter installation…\n';
  document.getElementById('ci-install-result').style.display = 'none';
  const r = await api('/api/codeigniter/install', 'POST', { site_name: siteName, install_path: installPath, port, db_name: dbName, db_user: dbUser, db_pass: dbPass || undefined });
  if (!r.success) {
    toast(r.error || 'Failed to start install', 'error');
    btn.disabled = false;
    btn.innerHTML = '<i class="bi bi-download"></i> Create CodeIgniter App';
    return;
  }
  if (codeIgniterPollInterval) clearInterval(codeIgniterPollInterval);
  codeIgniterPollInterval = setInterval(async () => {
    const job = await api(`/api/codeigniter/install/${r.job_id}`);
    log.textContent = (job.logs || []).join('\n');
    log.scrollTop = log.scrollHeight;
    if (job.status === 'done') {
      clearInterval(codeIgniterPollInterval);
      btn.disabled = false;
      btn.innerHTML = '<i class="bi bi-download"></i> Create CodeIgniter App';
      if (job.result?.success) {
        toast('CodeIgniter app created!', 'success');
        document.getElementById('ci-result-url').href = job.result.url;
        document.getElementById('ci-install-result').style.display = 'block';
        loadCodeIgniterApps();
      }
    } else if (job.status === 'error') {
      clearInterval(codeIgniterPollInterval);
      btn.disabled = false;
      btn.innerHTML = '<i class="bi bi-download"></i> Create CodeIgniter App';
      toast('CodeIgniter install failed', 'error');
    }
  }, 1000);
}

async function changeCodeIgniterPort(name, nginxSite, currentPort) {
  const port = prompt(`New port for ${name}:`, currentPort || '8200');
  if (!port) return;
  const r = await api('/api/codeigniter/port', 'POST', { nginx_site: nginxSite, port });
  if (r.success) { toast(`${name} is now on port ${port}`, 'success'); loadCodeIgniterApps(); }
  else toast(r.stderr || r.error || 'Failed to change port', 'error');
}

async function deleteCodeIgniterApp(name, path, dbName, dbUser, nginxSite) {
  if (!confirm(`Delete CodeIgniter app ${name}? This removes files, database, user, and Nginx site.`)) return;
  const r = await apiDelete('/api/codeigniter/apps', { path, db_name: dbName, db_user: dbUser, nginx_site: nginxSite });
  if (!r.success) { toast(r.error || 'Failed to start delete', 'error'); return; }
  toast('Deleting CodeIgniter app…', 'info');
  if (codeIgniterDeletePollInterval) clearInterval(codeIgniterDeletePollInterval);
  codeIgniterDeletePollInterval = setInterval(async () => {
    const job = await api(`/api/codeigniter/delete/${r.job_id}`);
    if (job.status === 'done') {
      clearInterval(codeIgniterDeletePollInterval);
      toast('CodeIgniter app deleted', 'success');
      loadCodeIgniterApps();
    } else if (job.status === 'error') {
      clearInterval(codeIgniterDeletePollInterval);
      toast(job.result?.error || 'Delete failed', 'error');
    }
  }, 1200);
}
```

- [ ] **Step 4: Smoke-check frontend text references**

Run: `python3 -m py_compile panel.py`

Expected: exit code `0` with no output. Then load the panel manually and verify the CodeIgniter page opens.

---

### Task 4: Documentation, Verification, Commit, Push

**Files:**
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: completed CodeIgniter helper, backend, and UI.
- Produces: documented project state and pushed GitHub branch.

- [ ] **Step 1: Update docs**

Add `codeigniter-helper.sh` to the file list and document these routes:

```markdown
| GET | `/api/codeigniter/apps` | List CodeIgniter 4 apps |
| GET | `/api/codeigniter/next_port` | Find next available suggested CodeIgniter port |
| POST | `/api/codeigniter/install` | Start CodeIgniter 4 install job |
| GET | `/api/codeigniter/install/<job_id>` | Poll CodeIgniter install progress |
| POST | `/api/codeigniter/port` | Change a CodeIgniter Nginx site listen port |
| DELETE | `/api/codeigniter/apps` | Start CodeIgniter delete job |
| GET | `/api/codeigniter/delete/<job_id>` | Poll CodeIgniter delete progress |
```

- [ ] **Step 2: Run verification commands**

Run:

```bash
python3 -m py_compile panel.py
bash -n setup-sudo.sh wp-install-helper.sh wp-delete-helper.sh laravel-helper.sh codeigniter-helper.sh perf-helper.sh start-panel.sh
git status --short
```

Expected:

```text
python3 -m py_compile panel.py exits 0
bash -n ... exits 0
```

- [ ] **Step 3: Commit and push only intended files**

Run:

```bash
git status --short
git diff
git log --oneline -10
git add panel.py index.html setup-sudo.sh codeigniter-helper.sh CLAUDE.md docs/superpowers/plans/2026-07-25-codeigniter4-support.md
git commit -m "Add CodeIgniter 4 app management"
git push
```

Expected: push updates `origin/main`.

---

## Self-Review

- Spec coverage: the plan covers CI4-only creation, discovery, Nginx hosting, MySQL creation/deletion, UI, helper script, sudoers, rollback, and verification.
- Placeholder scan: no TBD/TODO/fill-in-later steps remain.
- Type consistency: backend functions and frontend function names are consistent across tasks and API routes.
