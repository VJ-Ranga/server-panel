#!/usr/bin/env python3
"""
Local Server Management Panel
Manages Nginx, MySQL, and WordPress installations.
Run: python3 panel.py
Access: http://127.0.0.1:8765
Default password: admin
"""

import json
import subprocess
import os
import re
import hashlib
import secrets
import time
import glob
import threading
import string
import shlex
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

# ── background job registry ───────────────────────────────────────────────────
_jobs = {}   # job_id -> {"status": "running"|"done"|"error", "logs": [], "result": {}}

PORT = 8765
HOST = "127.0.0.1"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "panel_config.json")
WP_CACHE_DIR = os.path.join(SCRIPT_DIR, "cache", "wordpress")
WP_CACHE_TAR = os.path.join(WP_CACHE_DIR, "latest.tar.gz")
WP_CACHE_VERSION = os.path.join(WP_CACHE_DIR, "latest.version")
WP_PLUGIN_LIBRARY_DIR = os.path.join(SCRIPT_DIR, "wp-plugin-library")

DEFAULT_CONFIG = {
    "password_hash": hashlib.sha256("admin".encode()).hexdigest(),
    "session_tokens": {},
    "mysql_user": "root",
    "mysql_password": "",
    "wp_admin_credentials": {},
}

ALLOWED_SERVICES = {"nginx", "mysql", "mariadb",
                    "php8.3-fpm", "php8.2-fpm", "php8.1-fpm", "php8.0-fpm", "php7.4-fpm"}
ALLOWED_ACTIONS  = {"start", "stop", "restart", "reload"}

PMA_NGINX_TEMPLATE = """\
server {{
    listen {port};
    server_name localhost;

    root /usr/share/phpmyadmin;
    index index.php index.html;

    # Security: block direct access to sensitive dirs
    location ~ ^/phpmyadmin/(libraries|templates|setup/lib)/ {{
        deny all;
    }}

    location / {{
        try_files $uri $uri/ /index.php?$args;
    }}

    location ~ \\.php$ {{
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:/run/php/php{phpver}-fpm.sock;
        fastcgi_param HTTP_HOST localhost;
    }}

    location ~ /\\.ht {{
        deny all;
    }}
}}
"""


# ── helpers ──────────────────────────────────────────────────────────────────

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            cfg = json.load(f)
        merged = DEFAULT_CONFIG.copy()
        merged.update(cfg)
        merged.setdefault("wp_admin_credentials", {})
        return merged
    return DEFAULT_CONFIG.copy()


def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


def get_wp_admin_credential(install_path):
    cfg = load_config()
    return cfg.get("wp_admin_credentials", {}).get(install_path, {})


def save_wp_admin_credential(install_path, username, password):
    if not install_path or not username or not password:
        return
    cfg = load_config()
    cfg.setdefault("wp_admin_credentials", {})[install_path] = {
        "username": username,
        "password": password,
        "updated_at": int(time.time()),
    }
    save_config(cfg)


def remove_wp_admin_credential(install_path):
    cfg = load_config()
    creds = cfg.setdefault("wp_admin_credentials", {})
    if install_path in creds:
        del creds[install_path]
        save_config(cfg)


def random_wp_admin_username(site_name=""):
    base = re.sub(r"[^a-z0-9]", "", (site_name or "user").lower())[:10] or "user"
    return f"{base}_{secrets.token_hex(3)}"


def parse_plugin_header(text):
    name = version = ""
    for line in text.splitlines()[:120]:
        line = re.sub(r"^\s*/?\*+\s?", "", line).strip()
        if not name:
            m = re.match(r"\s*Plugin Name\s*:\s*(.+)", line, re.I)
            if m:
                name = m.group(1).strip()
        if not version:
            m = re.match(r"\s*Version\s*:\s*(.+)", line, re.I)
            if m:
                version = m.group(1).strip()
        if name and version:
            break
    return name, version


def get_wp_plugin_library():
    os.makedirs(WP_PLUGIN_LIBRARY_DIR, exist_ok=True)
    plugins = []
    invalid = []
    for filename in sorted(os.listdir(WP_PLUGIN_LIBRARY_DIR)):
        if not filename.lower().endswith(".zip"):
            continue
        zip_path = os.path.join(WP_PLUGIN_LIBRARY_DIR, filename)
        plugin_id = os.path.splitext(filename)[0]
        try:
            with zipfile.ZipFile(zip_path) as zf:
                php_files = [n for n in zf.namelist() if n.lower().endswith(".php") and not n.endswith("/")]
                detected = None
                for member in php_files:
                    try:
                        text = zf.read(member).decode("utf-8", "ignore")
                    except Exception:
                        continue
                    plugin_name, version = parse_plugin_header(text)
                    if plugin_name:
                        slug = member.split("/", 1)[0] if "/" in member else os.path.splitext(os.path.basename(member))[0]
                        detected = {
                            "id": plugin_id,
                            "zip": filename,
                            "name": plugin_name,
                            "version": version or "—",
                            "slug": slug,
                            "main_file": member,
                            "size": os.path.getsize(zip_path),
                        }
                        break
                if detected:
                    plugins.append(detected)
                else:
                    invalid.append({"zip": filename, "error": "No WordPress plugin header found"})
        except Exception as e:
            invalid.append({"zip": filename, "error": str(e)})
    return {"success": True, "plugins": plugins, "invalid": invalid}


def safe_extract_zip(zf, dest_dir):
    dest_real = os.path.realpath(dest_dir)
    os.makedirs(dest_real, exist_ok=True)
    for member in zf.infolist():
        name = member.filename
        if name.startswith("/") or "\x00" in name:
            raise ValueError(f"Unsafe zip path: {name}")
        target = os.path.realpath(os.path.join(dest_real, name))
        if target != dest_real and not target.startswith(dest_real + os.sep):
            raise ValueError(f"Unsafe zip path: {name}")
    zf.extractall(dest_real)


def install_selected_wp_plugins(install_path, selected_plugin_ids, log):
    if not selected_plugin_ids:
        return
    library = get_wp_plugin_library()
    plugins_by_id = {p["id"]: p for p in library.get("plugins", [])}
    selected = []
    for plugin_id in selected_plugin_ids:
        if plugin_id in plugins_by_id:
            selected.append(plugins_by_id[plugin_id])
        else:
            log(f"  [plugin] Skipped unknown plugin id: {plugin_id}")
    if not selected:
        return

    plugins_dir = os.path.join(install_path, "wp-content", "plugins")
    log("▶ [plugins] Installing selected plugins…")
    for plugin in selected:
        zip_path = os.path.join(WP_PLUGIN_LIBRARY_DIR, plugin["zip"])
        try:
            with zipfile.ZipFile(zip_path) as zf:
                safe_extract_zip(zf, plugins_dir)
            log(f"  [plugin] Installed: {plugin['name']}")
        except Exception as e:
            log(f"  [plugin] Install failed: {plugin['name']} - {e}")
            continue

        plugin_file = plugin["main_file"]
        php_script = f"""<?php
$install_path = {repr(install_path)};
$plugin_file = {repr(plugin_file)};
define('ABSPATH', $install_path . '/');
require_once ABSPATH . 'wp-load.php';
require_once ABSPATH . 'wp-admin/includes/plugin.php';
$result = activate_plugin($plugin_file);
if (is_wp_error($result)) {{ echo 'error:' . $result->get_error_message(); exit(1); }}
echo 'ok';
"""
        tmp_php = f"/tmp/_panel_wp_activate_plugin_{secrets.token_hex(6)}.php"
        try:
            with open(tmp_php, "w") as f:
                f.write(php_script)
            r = run_cmd(f"php {shell_quote(tmp_php)}", timeout=30)
            if r["success"] and "ok" in r["stdout"]:
                log(f"  [plugin] Installed and activated: {plugin['name']}")
            else:
                log(f"  [plugin] Activation failed: {plugin['name']} - {(r['stderr'] or r['stdout'] or r.get('error', 'Failed')).strip()}")
        finally:
            run_cmd(f"rm -f {shell_quote(tmp_php)}")

    helper = os.path.join(SCRIPT_DIR, "wp-install-helper.sh")
    r = run_cmd(f"sudo {shell_quote(helper)} --fix-site-perms {shell_quote(install_path)}", timeout=60)
    if not r["success"]:
        log(f"  [plugin] Permission refresh failed: {(r['stderr'] or r['stdout'] or r.get('error', 'Failed')).strip()}")


def detect_wp_admin_users_for_path(install_path):
    try:
        creds = read_wp_config(install_path)
        return detect_wp_admin_users(
            creds.get("db_name", ""),
            creds.get("db_user", ""),
            creds.get("db_pass", ""),
            creds.get("db_host", "localhost"),
            creds.get("table_prefix", "wp_"),
        )
    except Exception:
        return []


def detect_wp_admin_user_for_path(install_path):
    users = detect_wp_admin_users_for_path(install_path)
    return users[0] if users else ""


def run_cmd(cmd, timeout=15, input_data=None):
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=timeout, input=input_data
        )
        return {"success": r.returncode == 0, "stdout": r.stdout,
                "stderr": r.stderr, "returncode": r.returncode}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Timed out", "stdout": "", "stderr": ""}
    except Exception as e:
        return {"success": False, "error": str(e), "stdout": "", "stderr": ""}


def shell_quote(value):
    return shlex.quote(str(value))


def parse_port(value, default=None):
    try:
        port = int(value if value not in (None, "") else default)
    except (TypeError, ValueError):
        raise ValueError("Port must be a number")
    if not 1 <= port <= 65535:
        raise ValueError("Port must be between 1 and 65535")
    return port


def validate_install_path(path):
    if not path or not path.startswith("/"):
        raise ValueError("Install path must be absolute")
    if not re.fullmatch(r"/[A-Za-z0-9._/\-]+", path):
        raise ValueError("Install path contains unsupported characters")
    blocked = {"/", "/var", "/var/www", "/opt", "/usr", "/home"}
    if path.rstrip("/") in blocked:
        raise ValueError("Install path is too broad")
    return path.rstrip("/")


def path_modified_at(path):
    try:
        return int(os.path.getmtime(path))
    except OSError:
        return 0


def svc_status(service):
    r = run_cmd(f"systemctl is-active {service}")
    return r["stdout"].strip() or "inactive"


def get_system_info():
    info = {}
    r = run_cmd("grep 'cpu ' /proc/stat | awk '{usage=($2+$4)*100/($2+$3+$4+$5)} END {printf \"%.1f\", usage}'")
    info["cpu"] = r["stdout"].strip() + "%" if r["success"] else "N/A"
    r = run_cmd("free -h | awk '/^Mem/{print $2\"|\"$3\"|\"$6}'")
    if r["success"] and "|" in r["stdout"]:
        parts = r["stdout"].strip().split("|")
        info["mem_total"], info["mem_used"], info["mem_free"] = parts[0], parts[1], parts[2]
    r = run_cmd("df -h / | awk 'NR==2{print $2\"|\"$3\"|\"$5}'")
    if r["success"] and "|" in r["stdout"]:
        parts = r["stdout"].strip().split("|")
        info["disk_total"], info["disk_used"], info["disk_pct"] = parts[0], parts[1], parts[2]
    r = run_cmd("uptime -p")
    info["uptime"] = r["stdout"].strip() if r["success"] else "N/A"
    r = run_cmd("hostname")
    info["hostname"] = r["stdout"].strip() if r["success"] else "localhost"
    return info


def get_nginx_sites():
    sites = []
    avail = "/etc/nginx/sites-available"
    enabl = "/etc/nginx/sites-enabled"
    if not os.path.isdir(avail):
        return sites
    for name in sorted(os.listdir(avail)):
        path = os.path.join(avail, name)
        enabled = os.path.exists(os.path.join(enabl, name))
        server_name = "—"
        try:
            content = open(path).read()
            m = re.search(r"server_name\s+([^;]+);", content)
            if m:
                server_name = m.group(1).strip()
        except Exception:
            pass
        sites.append({"name": name, "enabled": enabled, "server_name": server_name})
    return sites


def find_nginx_site_for_path(install_path):
    """Scan nginx sites-available to find which config file serves install_path."""
    avail = "/etc/nginx/sites-available"
    if not os.path.isdir(avail):
        return None
    install_path = install_path.rstrip("/")
    best_match = None
    best_len = -1
    for name in os.listdir(avail):
        if name.endswith(".bak") or ".bak." in name:
            continue
        try:
            content = open(os.path.join(avail, name)).read()
            # Match root directives that equal or are a parent of install_path
            for m in re.finditer(r"root\s+([^;]+);", content):
                root = m.group(1).strip().rstrip("/")
                if install_path == root or install_path.startswith(root + "/"):
                    if len(root) > best_len:
                        best_match = name
                        best_len = len(root)
        except Exception:
            pass
    return best_match


def get_nginx_site_port(site_name):
    if not site_name or not re.fullmatch(r"[\w\-\.]+", site_name):
        return None
    path = f"/etc/nginx/sites-available/{site_name}"
    try:
        content = open(path).read()
    except Exception:
        return None
    m = re.search(r"(?m)^\s*listen\s+(?:\[::\]:)?(\d+)(?:\s+[^;]*)?;", content)
    return int(m.group(1)) if m else None


def set_nginx_site_port(site_name, port):
    if not site_name or not re.fullmatch(r"[\w\-\.]+", site_name):
        return {"success": False, "error": "Bad Nginx site name"}
    avail = f"/etc/nginx/sites-available/{site_name}"
    try:
        content = open(avail).read()
    except Exception as e:
        return {"success": False, "error": str(e)}

    new_content, changed = re.subn(
        r"(?m)^(\s*listen\s+)(?:\[::\]:)?\d+((?:\s+[^;]*)?;)",
        rf"\g<1>{port}\2",
        content,
        count=1,
    )
    if not changed:
        return {"success": False, "error": "No listen directive found"}

    helper = os.path.join(SCRIPT_DIR, "wp-install-helper.sh")
    r = run_cmd(
        f"sudo {shell_quote(helper)} --set-port {shell_quote(site_name)} {shell_quote(port)}",
        timeout=30,
    )
    return {**r, "port": port}


def detect_wp_admin_users(db_name, db_user, db_pass, db_host, table_prefix):
    if not db_name or not db_user or db_name == "—" or db_user == "—":
        return []
    safe_prefix = re.sub(r"[^A-Za-z0-9_]", "", table_prefix or "wp_")
    if not safe_prefix:
        safe_prefix = "wp_"
    tables = {
        "users": f"`{safe_prefix}users`",
        "usermeta": f"`{safe_prefix}usermeta`",
    }
    meta_key = (safe_prefix + "capabilities").replace("'", "''")
    sql = (
        f"SELECT u.user_login FROM {tables['users']} u "
        f"JOIN {tables['usermeta']} m ON m.user_id = u.ID "
        f"WHERE m.meta_key = '{meta_key}' AND m.meta_value LIKE '%administrator%' "
        f"ORDER BY u.ID;"
    )
    auth = f"-h {shell_quote(db_host or 'localhost')} -u {shell_quote(db_user)}"
    env = ""
    if db_pass:
        env = f"MYSQL_PWD={shell_quote(db_pass)} "
    r = run_cmd(f"{env}mysql {auth} {shell_quote(db_name)} -N -B -e {shell_quote(sql)}", timeout=10)
    if not r["success"] or not r["stdout"].strip():
        return []
    return [line.strip() for line in r["stdout"].splitlines() if line.strip()]


def detect_wp_admin_user(db_name, db_user, db_pass, db_host, table_prefix):
    users = detect_wp_admin_users(db_name, db_user, db_pass, db_host, table_prefix)
    return users[0] if users else ""


def get_wp_sites():
    sites = []
    patterns = ["/var/www/*/wp-config.php", "/var/www/html/*/wp-config.php",
                "/var/www/*/*/wp-config.php", "/opt/*/wp-config.php",
                "/opt/*/*/wp-config.php", "/opt/wp-config.php",
                os.path.expanduser("~/local/*/wp-config.php")]
    found = []
    for p in patterns:
        found.extend(glob.glob(p))
    for wp_cfg in found:
        site_path = os.path.dirname(wp_cfg)
        site_name = os.path.basename(site_path)
        entry = {"name": site_name, "path": site_path, "db_name": "—", "modified_at": path_modified_at(site_path)}
        try:
            with open(wp_cfg) as f:
                content = f.read()
            m = re.search(r"define\(\s*['\"]DB_NAME['\"]\s*,\s*['\"]([^'\"]+)['\"]", content)
            if m:
                entry["db_name"] = m.group(1)
            m2 = re.search(r"define\(\s*['\"]DB_USER['\"]\s*,\s*['\"]([^'\"]+)['\"]", content)
            entry["db_user"] = m2.group(1) if m2 else "—"
            m3 = re.search(r"\$table_prefix\s*=\s*['\"]([^'\"]+)['\"]", content)
            entry["table_prefix"] = m3.group(1) if m3 else "wp_"
            m4 = re.search(r"define\(\s*['\"]DB_PASSWORD['\"]\s*,\s*['\"]([^'\"]*)['\"]", content)
            m5 = re.search(r"define\(\s*['\"]DB_HOST['\"]\s*,\s*['\"]([^'\"]+)['\"]", content)
            admin_users = detect_wp_admin_users(
                entry["db_name"],
                entry["db_user"],
                m4.group(1) if m4 else "",
                m5.group(1) if m5 else "localhost",
                entry["table_prefix"],
            )
            entry["wp_admin_users"] = admin_users
            entry["wp_admin_user"] = admin_users[0] if admin_users else ""
        except Exception as e:
            entry["error"] = str(e)
        entry["has_wpcli"]   = os.path.exists("/usr/local/bin/wp")
        entry["nginx_site"]  = find_nginx_site_for_path(site_path) or site_name
        entry["port"]        = get_nginx_site_port(entry["nginx_site"])
        admin_creds = get_wp_admin_credential(site_path)
        if admin_creds:
            saved_user = admin_creds.get("username") or ""
            entry["wp_saved_admin_user"] = saved_user
            if saved_user and not entry.get("wp_admin_users"):
                entry["wp_admin_users"] = [saved_user]
            entry["wp_admin_user"] = saved_user if saved_user in entry.get("wp_admin_users", []) else entry.get("wp_admin_user", "")
            entry["wp_admin_pass"] = admin_creds.get("password", "")
        sites.append(entry)
    return sites


def read_env_file(path):
    data = {}
    if not os.path.exists(path):
        return data
    with open(path, errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            data[key] = val.strip().strip('"').strip("'")
    return data


def set_env_value(content, key, value):
    safe = str(value).replace('"', '\\"')
    line = f'{key}="{safe}"'
    new, n = re.subn(rf"(?m)^{re.escape(key)}=.*$", line, content)
    if n:
        return new
    return content.rstrip() + "\n" + line + "\n"


def get_laravel_apps():
    apps = []
    patterns = ["/var/www/*/artisan", "/opt/*/artisan", "/opt/*/*/artisan"]
    found = []
    for p in patterns:
        found.extend(glob.glob(p))
    for artisan in sorted(set(found)):
        app_path = os.path.dirname(artisan)
        name = os.path.basename(app_path)
        env = read_env_file(os.path.join(app_path, ".env"))
        nginx_site = find_nginx_site_for_path(os.path.join(app_path, "public")) or find_nginx_site_for_path(app_path) or name
        version = ""
        r = run_cmd(f"php {shell_quote(artisan)} --version", timeout=10)
        if r["success"]:
            version = r["stdout"].strip()
        apps.append({
            "name": name,
            "path": app_path,
            "app_name": env.get("APP_NAME", name),
            "app_url": env.get("APP_URL", ""),
            "db_name": env.get("DB_DATABASE", ""),
            "db_user": env.get("DB_USERNAME", ""),
            "db_pass": env.get("DB_PASSWORD", ""),
            "nginx_site": nginx_site,
            "port": get_nginx_site_port(nginx_site),
            "version": version,
            "modified_at": path_modified_at(app_path),
        })
    return apps


def install_laravel_job(job_id, params, cfg):
    job = _jobs[job_id]

    def log(msg):
        job["logs"].append(msg)
        print(msg)

    created = {"src": "", "dir": False, "db": False, "db_user": False, "nginx": False}
    site_name = install_path = db_name = db_user = None
    try:
        site_name = re.sub(r"[^\w\-]", "", params.get("site_name", "laravel"))
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
        port = parse_port(params.get("port", 8100), 8100)
        app_name = params.get("app_name", site_name).strip() or site_name
        laravel_version = str(params.get("laravel_version", "latest")).strip().lower()
        if laravel_version not in ("latest", "12"):
            raise ValueError("Unsupported Laravel version")
        php_ver, _ = detect_php_fpm()

        r = run_cmd("command -v composer")
        if not r["success"]:
            raise Exception("Composer is not installed. Install Composer first to create Laravel apps.")

        tmp_src = f"/tmp/_panel_laravel_{site_name}_{secrets.token_hex(4)}"
        created["src"] = tmp_src

        log("▶ [1/6] Creating Laravel project with Composer…")
        package = "laravel/laravel" if laravel_version == "latest" else "laravel/laravel:^12.0"
        r = run_cmd(f"composer create-project {shell_quote(package)} {shell_quote(tmp_src)} --no-interaction", timeout=1800)
        if not r["success"]:
            raise Exception("Composer create-project failed:\n" + (r["stderr"] or r["stdout"]))
        log("  Laravel project created")

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

        log("▶ [3/6] Writing Laravel .env…")
        env_path = os.path.join(tmp_src, ".env")
        env_content = open(env_path).read() if os.path.exists(env_path) else ""
        for key, value in {
            "APP_NAME": app_name,
            "APP_ENV": "local",
            "APP_DEBUG": "true",
            "APP_URL": f"http://localhost:{port}",
            "DB_CONNECTION": "mysql",
            "DB_HOST": "127.0.0.1",
            "DB_PORT": "3306",
            "DB_DATABASE": db_name,
            "DB_USERNAME": db_user,
            "DB_PASSWORD": db_pass,
            "SESSION_DRIVER": "file",
            "CACHE_STORE": "file",
            "QUEUE_CONNECTION": "sync",
        }.items():
            env_content = set_env_value(env_content, key, value)
        open(env_path, "w").write(env_content)

        log("▶ [4/6] Preparing Laravel app…")
        r = run_cmd(f"cd {shell_quote(tmp_src)} && php artisan key:generate --force && php artisan storage:link || true", timeout=120)
        if not r["success"]:
            raise Exception("Laravel artisan setup failed:\n" + (r["stderr"] or r["stdout"]))

        log("▶ [5/6] Installing files and Nginx site…")
        helper = os.path.join(SCRIPT_DIR, "laravel-helper.sh")
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
            helper = os.path.join(SCRIPT_DIR, "laravel-helper.sh")
            run_cmd(f"sudo {shell_quote(helper)} delete {shell_quote(install_path or '')} {shell_quote(site_name or '')}", timeout=60)
        job["status"] = "error"
        job["result"] = {"success": False, "error": str(e)}
    finally:
        if created.get("src"):
            run_cmd(f"rm -rf {shell_quote(created['src'])}")


def delete_laravel_job(job_id, app_path, db_name, db_user, nginx_site, cfg):
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
        helper = os.path.join(SCRIPT_DIR, "laravel-helper.sh")
        r = run_cmd(f"sudo {shell_quote(helper)} delete {shell_quote(app_path)} {shell_quote(nginx_site)}", timeout=60)
        log((r["stdout"] + r["stderr"]).strip())
        job["status"] = "done"
        job["result"] = {"success": True}
    except Exception as e:
        log(f"✖ Error: {e}")
        job["status"] = "error"
        job["result"] = {"success": False, "error": str(e)}

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
            "modified_at": path_modified_at(app_path),
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
        os.makedirs(os.path.join(tmp_src, "writable"), exist_ok=True)

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


PHP_PROJECT_META = ".server-panel-project.json"
PHP_PROJECT_TEMPLATES = {"blank", "php", "php_db"}


def read_php_project_metadata(project_path):
    meta_path = os.path.join(project_path, PHP_PROJECT_META)
    with open(meta_path, errors="ignore") as f:
        data = json.load(f)
    if data.get("type") != "php":
        raise ValueError("Not a panel PHP project")
    return data


def get_php_projects():
    projects = []
    patterns = [f"/var/www/*/{PHP_PROJECT_META}", f"/opt/*/{PHP_PROJECT_META}", f"/opt/*/*/{PHP_PROJECT_META}"]
    found = []
    for p in patterns:
        found.extend(glob.glob(p))
    for meta_path in sorted(set(found)):
        app_path = os.path.dirname(meta_path)
        try:
            meta = read_php_project_metadata(app_path)
        except Exception:
            continue
        name = meta.get("name") or os.path.basename(app_path)
        nginx_site = find_nginx_site_for_path(app_path) or meta.get("nginx_site") or name
        port = get_nginx_site_port(nginx_site) or meta.get("port") or ""
        projects.append({
            "name": name,
            "template": meta.get("template", "blank"),
            "path": app_path,
            "install_path": app_path,
            "nginx_site": nginx_site,
            "port": port,
            "db_name": meta.get("db_name", ""),
            "db_user": meta.get("db_user", ""),
            "db_created": bool(meta.get("db_created")),
            "created_at": meta.get("created_at", 0),
            "modified_at": path_modified_at(app_path),
        })
    return projects


def php_export(value):
    return json.dumps(str(value))


def write_php_project_files(src_dir, metadata, db_pass=""):
    os.makedirs(src_dir, exist_ok=True)
    template = metadata.get("template", "blank")
    meta_path = os.path.join(src_dir, PHP_PROJECT_META)
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    if template == "blank":
        return

    project_name = metadata.get("name", "PHP Project")
    if template == "php_db":
        config = """<?php
return [
    'host' => '127.0.0.1',
    'database' => %s,
    'username' => %s,
    'password' => %s,
    'charset' => 'utf8mb4',
];
""" % (php_export(metadata.get("db_name", "")), php_export(metadata.get("db_user", "")), php_export(db_pass))
        with open(os.path.join(src_dir, "config.php"), "w") as f:
            f.write(config)
        index = """<?php
$projectName = %s;
$config = require __DIR__ . '/config.php';
$status = 'Not checked';
$details = '';
try {
    $dsn = "mysql:host={$config['host']};dbname={$config['database']};charset={$config['charset']}";
    $pdo = new PDO($dsn, $config['username'], $config['password'], [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);
    $status = 'Connected';
    $details = 'Database connection successful.';
} catch (Throwable $e) {
    $status = 'Failed';
    $details = $e->getMessage();
}
?>
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title><?= htmlspecialchars($projectName) ?></title>
  <style>body{font-family:system-ui,sans-serif;max-width:760px;margin:48px auto;padding:0 20px;line-height:1.5}code{background:#f3f4f6;padding:2px 6px;border-radius:4px}.ok{color:#047857}.bad{color:#b91c1c}</style>
</head>
<body>
  <h1><?= htmlspecialchars($projectName) ?></h1>
  <p>Plain PHP project with MySQL connection test.</p>
  <p><strong>PHP:</strong> <?= htmlspecialchars(PHP_VERSION) ?></p>
  <p><strong>Database:</strong> <code><?= htmlspecialchars($config['database']) ?></code></p>
  <p><strong>Status:</strong> <span class="<?= $status === 'Connected' ? 'ok' : 'bad' ?>"><?= htmlspecialchars($status) ?></span></p>
  <p><?= htmlspecialchars($details) ?></p>
</body>
</html>
""" % php_export(project_name)
    else:
        index = """<?php
$projectName = %s;
?>
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title><?= htmlspecialchars($projectName) ?></title>
  <style>body{font-family:system-ui,sans-serif;max-width:760px;margin:48px auto;padding:0 20px;line-height:1.5}code{background:#f3f4f6;padding:2px 6px;border-radius:4px}</style>
</head>
<body>
  <h1><?= htmlspecialchars($projectName) ?></h1>
  <p>Plain PHP project is running.</p>
  <p><strong>PHP:</strong> <?= htmlspecialchars(PHP_VERSION) ?></p>
  <p><strong>Server time:</strong> <?= htmlspecialchars(date('Y-m-d H:i:s')) ?></p>
  <p><strong>Document root:</strong> <code><?= htmlspecialchars($_SERVER['DOCUMENT_ROOT'] ?? __DIR__) ?></code></p>
</body>
</html>
""" % php_export(project_name)

    with open(os.path.join(src_dir, "index.php"), "w") as f:
        f.write(index)


def install_php_project_job(job_id, params, cfg):
    job = _jobs[job_id]

    def log(msg):
        job["logs"].append(msg)
        print(msg)

    created = {"src": "", "dir": False, "db": False, "db_user": False, "nginx": False}
    site_name = install_path = db_name = db_user = None
    try:
        site_name = re.sub(r"[^\w\-]", "", params.get("site_name", "php-project"))
        if not site_name:
            raise ValueError("Project name is invalid")
        install_path = validate_install_path(params.get("install_path", f"/var/www/{site_name}"))
        template = str(params.get("template", "php")).strip().lower()
        if template not in PHP_PROJECT_TEMPLATES:
            raise ValueError("Unsupported PHP project template")
        port = parse_port(params.get("port", 8300), 8300)
        db_pass = ""
        if template == "php_db":
            db_name = re.sub(r"[^\w\-]", "", params.get("db_name", f"{site_name}_db"))
            db_user = re.sub(r"[^\w\-]", "", params.get("db_user", f"{site_name[:16]}_user"))
            db_pass = params.get("db_pass") or secrets.token_urlsafe(14)
            if not db_name or not db_user:
                raise ValueError("Database name or user is invalid")
            if "'" in db_pass or "\\" in db_pass:
                raise ValueError("Database password cannot contain single quotes or backslashes")
        php_ver, _ = detect_php_fpm()
        tmp_src = f"/tmp/_panel_php_project_{site_name}_{secrets.token_hex(4)}"
        created["src"] = tmp_src

        if template == "php_db":
            log(f"▶ [1/4] Creating database '{db_name}' and user '{db_user}'...")
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
        else:
            log("▶ [1/4] Database skipped for this template")

        log("▶ [2/4] Generating project files...")
        metadata = {
            "type": "php",
            "name": site_name,
            "template": template,
            "install_path": install_path,
            "nginx_site": site_name,
            "port": port,
            "db_name": db_name or "",
            "db_user": db_user or "",
            "db_created": template == "php_db",
            "created_at": int(time.time()),
        }
        write_php_project_files(tmp_src, metadata, db_pass)

        log("▶ [3/4] Installing files and Nginx site...")
        helper = os.path.join(SCRIPT_DIR, "php-project-helper.sh")
        r = run_cmd(
            f"sudo {shell_quote(helper)} install {shell_quote(tmp_src)} {shell_quote(install_path)} {shell_quote(site_name)} {shell_quote(php_ver)} {shell_quote(port)}",
            timeout=120,
        )
        if not r["success"]:
            raise Exception("System setup failed:\n" + r["stdout"] + r["stderr"])
        created["dir"] = True
        created["nginx"] = True
        log(r["stdout"].strip())

        log("▶ [4/4] Done!")
        log(f"  URL: http://localhost:{port}")
        job["status"] = "done"
        job["result"] = {"success": True, "url": f"http://localhost:{port}", "install_path": install_path, "template": template, "db_name": db_name or "", "db_user": db_user or "", "db_pass": db_pass, "nginx_site": site_name}
    except Exception as e:
        log(f"\n✖ Error: {e}")
        log("↩ Rolling back what was created...")
        if created.get("db_user") and db_user:
            mysql_cmd(cfg, f"DROP USER IF EXISTS '{db_user}'@'localhost'; FLUSH PRIVILEGES;")
        if created.get("db") and db_name:
            mysql_cmd(cfg, f"DROP DATABASE IF EXISTS `{db_name}`;")
        if created.get("dir") or created.get("nginx"):
            helper = os.path.join(SCRIPT_DIR, "php-project-helper.sh")
            run_cmd(f"sudo {shell_quote(helper)} delete {shell_quote(install_path or '')} {shell_quote(site_name or '')}", timeout=60)
        job["status"] = "error"
        job["result"] = {"success": False, "error": str(e)}
    finally:
        if created.get("src"):
            run_cmd(f"rm -rf {shell_quote(created['src'])}")


def delete_php_project_job(job_id, app_path, db_name, db_user, nginx_site, cfg):
    job = _jobs[job_id]
    def log(msg):
        job["logs"].append(msg); print(msg)
    try:
        meta = read_php_project_metadata(app_path)
        db_created = bool(meta.get("db_created"))
        safe_db_name = meta.get("db_name") or db_name
        safe_db_user = meta.get("db_user") or db_user
        safe_nginx_site = meta.get("nginx_site") or nginx_site
        if db_created and safe_db_name and re.fullmatch(r"[\w\-]+", safe_db_name):
            log(f"▶ Dropping database '{safe_db_name}'...")
            mysql_cmd(cfg, f"DROP DATABASE IF EXISTS `{safe_db_name}`;")
        if db_created and safe_db_user and safe_db_user not in ("root", "—") and re.fullmatch(r"[\w\-]+", safe_db_user):
            log(f"▶ Dropping user '{safe_db_user}'...")
            mysql_cmd(cfg, f"DROP USER IF EXISTS '{safe_db_user}'@'localhost'; FLUSH PRIVILEGES;")
        log("▶ Removing files and Nginx site...")
        helper = os.path.join(SCRIPT_DIR, "php-project-helper.sh")
        r = run_cmd(f"sudo {shell_quote(helper)} delete {shell_quote(app_path)} {shell_quote(safe_nginx_site)}", timeout=60)
        log((r["stdout"] + r["stderr"]).strip())
        job["status"] = "done" if r["success"] else "error"
        job["result"] = {"success": bool(r["success"]), "error": "" if r["success"] else (r["stderr"] or r["stdout"])}
    except Exception as e:
        log(f"✖ Error: {e}")
        job["status"] = "error"
        job["result"] = {"success": False, "error": str(e)}


def mysql_cmd(cfg, query, database=None):
    user = cfg.get("mysql_user", "root")
    pwd  = cfg.get("mysql_password", "")
    auth = f"-u{user}" + (f" -p{pwd}" if pwd else "")
    db   = database if database and database != "_none_" else ""
    # Try progressively: normal → sudo with auth → sudo socket-only (for auth_socket root)
    attempts = [
        f"mysql {auth} {db} --batch",
        f"sudo mysql {auth} {db} --batch",
        f"sudo mysql {db} --batch",
    ]
    for cmd in attempts:
        r = run_cmd(cmd, input_data=query)
        if r["success"]:
            return r
    return r


def detect_php_fpm():
    """Return (version_string, service_name) for the active/installed PHP-FPM."""
    for v in ["8.3", "8.2", "8.1", "8.0", "7.4"]:
        svc = f"php{v}-fpm"
        st  = svc_status(svc)
        if st in ("active", "inactive"):   # service exists even if stopped
            return v, svc
    # Fall back to PHP CLI version
    r = run_cmd("php --version 2>/dev/null | head -1")
    if r["success"]:
        m = re.search(r"PHP (\d+\.\d+)", r["stdout"])
        if m:
            v = m.group(1)
            return v, f"php{v}-fpm"
    return "8.3", "php8.3-fpm"


def get_phpmyadmin_info():
    php_ver, php_svc = detect_php_fpm()
    installed        = os.path.isdir("/usr/share/phpmyadmin")
    cfg_path         = "/etc/phpmyadmin/config.inc.php"
    nginx_avail      = "/etc/nginx/sites-available/phpmyadmin"
    nginx_enabled    = "/etc/nginx/sites-enabled/phpmyadmin"

    info = {
        "installed":          installed,
        "config_path":        cfg_path,
        "config_exists":      os.path.exists(cfg_path),
        "nginx_site_exists":  os.path.exists(nginx_avail),
        "nginx_site_enabled": os.path.exists(nginx_enabled),
        "php_version":        php_ver,
        "php_fpm_service":    php_svc,
        "php_fpm_status":     svc_status(php_svc),
        "pma_port":           8081,
    }

    # Try to read the port we configured last time from the nginx site
    if info["nginx_site_exists"]:
        try:
            txt = open(nginx_avail).read()
            m   = re.search(r"listen\s+(\d+)", txt)
            if m:
                info["pma_port"] = int(m.group(1))
        except Exception:
            pass

    info["url"] = f"http://localhost:{info['pma_port']}"
    return info


# ── performance helpers ───────────────────────────────────────────────────────

def get_php_ini_path():
    php_ver, _ = detect_php_fpm()
    for p in [f"/etc/php/{php_ver}/fpm/php.ini", f"/etc/php/{php_ver}/apache2/php.ini"]:
        if os.path.exists(p):
            return p
    return f"/etc/php/{php_ver}/fpm/php.ini"

def get_fpm_pool_path():
    php_ver, _ = detect_php_fpm()
    return f"/etc/php/{php_ver}/fpm/pool.d/www.conf"

def get_mysql_conf_path():
    for p in ["/etc/mysql/mysql.conf.d/mysqld.cnf", "/etc/mysql/conf.d/mysql.cnf", "/etc/mysql/my.cnf"]:
        if os.path.exists(p):
            return p
    return "/etc/mysql/mysql.conf.d/mysqld.cnf"

def read_ini_value(filepath, key, default=""):
    try:
        for line in open(filepath):
            line = line.strip()
            if line.startswith(";"):
                continue
            m = re.match(rf"^{re.escape(key)}\s*=\s*(.+)", line)
            if m:
                return m.group(1).strip()
    except Exception:
        pass
    return default

def set_ini_value(content, key, value):
    # Replace uncommented setting
    new, n = re.subn(rf"^({re.escape(key)}\s*=).*$", rf"\g<1> {value}", content, flags=re.MULTILINE)
    if n:
        return new
    # Uncomment and replace commented setting
    new, n = re.subn(rf"^;\s*({re.escape(key)}\s*=).*$", rf"\1 {value}", content, flags=re.MULTILINE)
    if n:
        return new
    # Append
    return content.rstrip() + f"\n{key} = {value}\n"

def read_nginx_value(content, key, default=""):
    m = re.search(rf"(?m)^\s*{re.escape(key)}\s+([^;]+);", content)
    return m.group(1).strip() if m else default

def set_nginx_value(content, key, value):
    new, n = re.subn(rf"(?m)^(\s*){re.escape(key)}\s+[^;]+;", rf"\g<1>{key} {value};", content)
    if n:
        return new, True
    # Not found — add to http block before first include
    new, n = re.subn(r"(http\s*\{[^}]*?)([ \t]*include\s)", rf"\1    {key} {value};\n\2", content, flags=re.DOTALL)
    return new, n > 0

def get_perf_nginx():
    try:
        c = open("/etc/nginx/nginx.conf").read()
    except Exception:
        return {"error": "Cannot read nginx.conf"}
    return {
        "worker_processes":     read_nginx_value(c, "worker_processes",    "auto"),
        "worker_connections":   read_nginx_value(c, "worker_connections",  "768"),
        "keepalive_timeout":    read_nginx_value(c, "keepalive_timeout",   "65"),
        "client_max_body_size": read_nginx_value(c, "client_max_body_size","1m"),
        "gzip":                 read_nginx_value(c, "gzip",                "off"),
        "gzip_comp_level":      read_nginx_value(c, "gzip_comp_level",     "6"),
        "server_tokens":        read_nginx_value(c, "server_tokens",       "on"),
    }

def get_perf_php():
    path = get_php_ini_path()
    if not os.path.exists(path):
        return {"error": f"Not found: {path}"}
    return {
        "path":               path,
        "memory_limit":       read_ini_value(path, "memory_limit",       "128M"),
        "max_execution_time": read_ini_value(path, "max_execution_time", "30"),
        "max_input_time":     read_ini_value(path, "max_input_time",     "60"),
        "upload_max_filesize":read_ini_value(path, "upload_max_filesize","2M"),
        "post_max_size":      read_ini_value(path, "post_max_size",      "8M"),
        "max_file_uploads":   read_ini_value(path, "max_file_uploads",   "20"),
    }

def get_perf_fpm():
    path = get_fpm_pool_path()
    if not os.path.exists(path):
        return {"error": f"Not found: {path}"}
    return {
        "path":                      path,
        "pm":                        read_ini_value(path, "pm",                       "dynamic"),
        "pm.max_children":           read_ini_value(path, "pm.max_children",          "5"),
        "pm.start_servers":          read_ini_value(path, "pm.start_servers",         "2"),
        "pm.min_spare_servers":      read_ini_value(path, "pm.min_spare_servers",     "1"),
        "pm.max_spare_servers":      read_ini_value(path, "pm.max_spare_servers",     "3"),
        "pm.max_requests":           read_ini_value(path, "pm.max_requests",          "500"),
        "request_terminate_timeout": read_ini_value(path, "request_terminate_timeout","0"),
    }

def get_perf_mysql():
    path = get_mysql_conf_path()
    if not os.path.exists(path):
        return {"error": f"Not found: {path}"}
    return {
        "path":                   path,
        "max_connections":        read_ini_value(path, "max_connections",         "151"),
        "innodb_buffer_pool_size":read_ini_value(path, "innodb_buffer_pool_size", "128M"),
        "slow_query_log":         read_ini_value(path, "slow_query_log",          "0"),
        "long_query_time":        read_ini_value(path, "long_query_time",         "2"),
        "max_allowed_packet":     read_ini_value(path, "max_allowed_packet",      "64M"),
    }


def gen_wp_salt():
    chars = string.ascii_letters + string.digits + "!@#$%^&*()-_[]{}<>~`+=,.;:/?|"
    return "".join(secrets.choice(chars) for _ in range(64))


def get_used_ports():
    """Return set of ports in use — nginx configs + actually listening ports."""
    used = {PORT, 80, 443}
    # Scan nginx configs (includes .bak files etc.)
    avail = "/etc/nginx/sites-available"
    if os.path.isdir(avail):
        for name in os.listdir(avail):
            try:
                content = open(os.path.join(avail, name)).read()
                for m in re.finditer(r"(?m)^\s*listen\s+(?:\[::\]:)?(\d+)", content):
                    used.add(int(m.group(1)))
            except Exception:
                pass
    # Also check actually-listening TCP ports via ss
    r = run_cmd("ss -tlnp 2>/dev/null | awk 'NR>1{print $4}' | grep -oE '[0-9]+$'")
    if r["success"]:
        for line in r["stdout"].splitlines():
            try:
                used.add(int(line.strip()))
            except ValueError:
                pass
    return used


def find_next_port(start=8090):
    used = get_used_ports()
    port = start
    while port in used and port <= 65535:
        port += 1
    return port


def read_wp_config(install_path):
    wp_cfg = os.path.join(install_path, "wp-config.php")
    content = open(wp_cfg).read()
    def extract(key):
        m = re.search(rf"define\(\s*'(?:DB_{key}|{key})',\s*'([^']*)'\s*\)", content)
        return m.group(1) if m else ""
    m_pfx = re.search(r"""\$table_prefix\s*=\s*'([^']+)'""", content)
    return {
        "db_name": extract("NAME"),
        "db_user": extract("USER"),
        "db_pass": extract("PASSWORD"),
        "db_host": extract("HOST") or "localhost",
        "table_prefix": m_pfx.group(1) if m_pfx else "wp_",
    }


def delete_wordpress_job(job_id, install_path, db_name, db_user, nginx_site, cfg):
    job = _jobs[job_id]

    def log(msg):
        job["logs"].append(msg)
        print(msg)

    try:
        # MySQL: drop database
        if db_name and db_name != "—" and re.fullmatch(r"[\w\-]+", db_name):
            log(f"▶ Dropping database '{db_name}'…")
            r = mysql_cmd(cfg, f"DROP DATABASE IF EXISTS `{db_name}`;")
            log(f"  {'OK' if r['success'] else r['stderr']}")
        else:
            log("  Skipping DB drop (no valid db name)")

        # MySQL: drop user (never drop root)
        if db_user and db_user not in ("—", "root") and re.fullmatch(r"[\w\-]+", db_user):
            log(f"▶ Dropping user '{db_user}'…")
            r = mysql_cmd(cfg, f"DROP USER IF EXISTS '{db_user}'@'localhost'; FLUSH PRIVILEGES;")
            log(f"  {'OK' if r['success'] else r['stderr']}")
        else:
            log(f"  Skipping user drop ('{db_user}' is protected or invalid)")

        # Files + nginx via sudo helper
        log("▶ Removing files and Nginx site…")
        helper     = os.path.join(SCRIPT_DIR, "wp-delete-helper.sh")
        safe_nginx = nginx_site if (nginx_site and re.fullmatch(r"[\w\-\.]+", nginx_site)) else ""
        safe_path  = install_path if install_path else ""
        r = run_cmd(f"sudo {shell_quote(helper)} {shell_quote(safe_path)} {shell_quote(safe_nginx)}", timeout=30)
        for line in (r["stdout"] + r["stderr"]).splitlines():
            if line.strip():
                log(f"  {line.strip()}")

        log("\n✔ Delete complete.")
        remove_wp_admin_credential(install_path)
        job["status"] = "done"
        job["result"] = {"success": True}

    except Exception as e:
        log(f"\n✖ Error: {e}")
        job["status"] = "error"
        job["result"] = {"success": False, "error": str(e)}


def delete_wordpress(install_path, db_name, db_user, nginx_site, cfg):
    msgs = []
    if db_name and db_name != "—" and re.fullmatch(r"[\w\-]+", db_name):
        r = mysql_cmd(cfg, f"DROP DATABASE IF EXISTS `{db_name}`;")
        msgs.append(f"  Drop database {db_name}: {'OK' if r['success'] else r['stderr']}")
    if db_user and db_user not in ("—", "root") and re.fullmatch(r"[\w\-]+", db_user):
        r = mysql_cmd(cfg, f"DROP USER IF EXISTS '{db_user}'@'localhost'; FLUSH PRIVILEGES;")
        msgs.append(f"  Drop user {db_user}: {'OK' if r['success'] else r['stderr']}")
    helper = os.path.join(SCRIPT_DIR, "wp-delete-helper.sh")
    safe_path = install_path or ""
    safe_nginx = nginx_site if (nginx_site and re.fullmatch(r"[\w\-\.]+", nginx_site)) else ""
    r = run_cmd(f"sudo {shell_quote(helper)} {shell_quote(safe_path)} {shell_quote(safe_nginx)}", timeout=30)
    for line in (r["stdout"] + r["stderr"]).splitlines():
        if line.strip():
            msgs.append(f"  {line.strip()}")
    return msgs


def install_wordpress_job(job_id, params, cfg):
    job = _jobs[job_id]

    def log(msg):
        job["logs"].append(msg)
        print(msg)

    # Track what was created so we can roll back on failure
    created = {"dir": False, "db": False, "db_user": False, "nginx": False}
    site_name = install_path = db_name = db_user = None

    try:
        site_name    = re.sub(r"[^\w\-]", "", params.get("site_name", "wordpress"))
        if not site_name:
            raise ValueError("Site name is invalid")
        install_path = validate_install_path(params.get("install_path", f"/var/www/{site_name}"))
        db_name      = re.sub(r"[^\w\-]", "", params.get("db_name", site_name))
        db_user      = re.sub(r"[^\w\-]", "", params.get("db_user", site_name[:16]))
        if not db_name or not db_user:
            raise ValueError("Database name or user is invalid")
        db_pass      = params.get("db_pass") or secrets.token_urlsafe(14)
        if "'" in db_pass or "\\" in db_pass:
            raise ValueError("Database password cannot contain single quotes or backslashes")
        port         = parse_port(params.get("port", 8090), 8090)
        php_ver, _   = detect_php_fpm()
        wp_title     = params.get("wp_title", site_name.replace("-","_").title()) or site_name
        wp_admin     = re.sub(r"[^\w\-]", "", params.get("wp_admin", "")) or random_wp_admin_username(site_name)
        wp_admin_pass = params.get("wp_admin_pass") or secrets.token_urlsafe(12)
        wp_email     = params.get("wp_email", "admin@localhost.local")
        selected_plugins = params.get("selected_plugins") or []
        if not isinstance(selected_plugins, list):
            selected_plugins = []

        # ── 1. Check WordPress version, download only if newer ───────────────
        os.makedirs(WP_CACHE_DIR, exist_ok=True)
        wp_tar     = WP_CACHE_TAR
        wp_ver_file= WP_CACHE_VERSION
        wp_src     = "/tmp/_panel_wp_src"

        log("▶ [1/6] Checking latest WordPress version…")
        r_ver = run_cmd("curl -sf https://api.wordpress.org/core/version-check/1.7/", timeout=15)
        latest_ver = None
        if r_ver["success"]:
            try:
                latest_ver = json.loads(r_ver["stdout"])["offers"][0]["version"]
            except Exception:
                pass

        cached_ver = open(wp_ver_file).read().strip() if os.path.exists(wp_ver_file) else None
        has_tar    = os.path.exists(wp_tar) and os.path.getsize(wp_tar) > 0

        if latest_ver:
            log(f"  Latest: {latest_ver}  |  Cached: {cached_ver or 'none'}")
        elif has_tar:
            log(f"  Could not check latest version — using cached WordPress {cached_ver or 'unknown version'}.")

        should_download = not has_tar or (latest_ver and latest_ver != cached_ver)
        if should_download:
            reason = "no cache" if not has_tar else f"new version {latest_ver}"
            log(f"  Downloading WordPress ({reason})…")
            tmp_tar = wp_tar + ".part"
            if os.path.exists(tmp_tar):
                os.remove(tmp_tar)
            proc = subprocess.Popen(
                ["curl", "-L", "--retry", "3", "--retry-delay", "3",
                 "-o", tmp_tar, "https://wordpress.org/latest.tar.gz"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            deadline = time.time() + 3600  # 1 hour hard limit
            last_size = 0
            while proc.poll() is None:
                time.sleep(5)
                size = os.path.getsize(tmp_tar) if os.path.exists(tmp_tar) else 0
                if size != last_size:
                    log(f"  {size/1048576:.1f} MB downloaded…")
                    last_size = size
                if time.time() > deadline:
                    proc.kill()
                    raise Exception("Download timed out after 60 minutes")
            if proc.returncode != 0:
                raise Exception(f"curl exited with code {proc.returncode}")
            os.replace(tmp_tar, wp_tar)
            final_size = os.path.getsize(wp_tar) if os.path.exists(wp_tar) else 0
            log(f"  Download complete ({final_size/1048576:.1f} MB)")
            if latest_ver:
                with open(wp_ver_file, "w") as f:
                    f.write(latest_ver)
        else:
            log(f"  Already up to date ({cached_ver or 'cached'}) — using cached copy from {wp_tar}.")

        log("▶ [2/6] Extracting files…")
        run_cmd(f"rm -rf {wp_src}")
        r = run_cmd(f"tar -xzf {shell_quote(wp_tar)} -C /tmp/ --overwrite && mv /tmp/wordpress {shell_quote(wp_src)}")
        if not r["success"]:
            raise Exception(f"Extract failed: {r['stderr']}")

        # ── 2. Build wp-config.php ───────────────────────────────────────────
        log("▶ [3/6] Building wp-config.php…")
        cfg_src = open("/tmp/_panel_wp_src/wp-config-sample.php").read()
        cfg_src = re.sub(r"define\(\s*'DB_NAME',\s*'[^']*'\s*\)",
                         f"define( 'DB_NAME', '{db_name}' )", cfg_src)
        cfg_src = re.sub(r"define\(\s*'DB_USER',\s*'[^']*'\s*\)",
                         f"define( 'DB_USER', '{db_user}' )", cfg_src)
        cfg_src = re.sub(r"define\(\s*'DB_PASSWORD',\s*'[^']*'\s*\)",
                         f"define( 'DB_PASSWORD', '{db_pass}' )", cfg_src)
        for key in ["AUTH_KEY","SECURE_AUTH_KEY","LOGGED_IN_KEY","NONCE_KEY",
                    "AUTH_SALT","SECURE_AUTH_SALT","LOGGED_IN_SALT","NONCE_SALT"]:
            cfg_src = re.sub(
                rf"define\(\s*'{key}',\s*'put your unique phrase here'\s*\);",
                f"define( '{key}', '{gen_wp_salt()}' );", cfg_src)
        tmp_cfg = f"/tmp/_panel_wp_config_{site_name}.php"
        with open(tmp_cfg, "w") as f:
            f.write(cfg_src)

        # ── 3. Create nginx config ───────────────────────────────────────────
        nginx_conf = (
            f"server {{\n"
            f"    listen {port};\n"
            f"    server_name localhost;\n"
            f"    root {install_path};\n"
            f"    index index.php index.html;\n\n"
            f"    location / {{\n"
            f"        try_files $uri $uri/ /index.php?$args;\n"
            f"    }}\n\n"
            f"    location ~ \\.php$ {{\n"
            f"        include snippets/fastcgi-php.conf;\n"
            f"        fastcgi_pass unix:/run/php/php{php_ver}-fpm.sock;\n"
            f"    }}\n\n"
            f"    location ~ /\\.ht {{ deny all; }}\n"
            f"}}\n"
        )
        with open(f"/tmp/_panel_wp_nginx_{site_name}", "w") as f:
            f.write(nginx_conf)

        # ── 4. Run privileged helper (files + nginx) ─────────────────────────
        log("▶ [4/6] Installing files & configuring Nginx…")
        helper = os.path.join(SCRIPT_DIR, "wp-install-helper.sh")
        r = run_cmd(
            f"sudo {shell_quote(helper)} {shell_quote(install_path)} {shell_quote(site_name)} {shell_quote(php_ver)}",
            timeout=60,
        )
        if not r["success"]:
            raise Exception(f"System setup failed:\n{r['stdout']}\n{r['stderr']}")
        log(r["stdout"].strip())
        created["dir"]   = True
        created["nginx"] = True

        # ── 5. Set up MySQL ──────────────────────────────────────────────────
        log(f"▶ [5/6] Creating database '{db_name}' and user '{db_user}'…")
        sql = (
            f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
            f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;\n"
        )
        r = mysql_cmd(cfg, sql)
        if r.get("stderr") and "ERROR" in r["stderr"]:
            raise Exception(f"MySQL error (create db): {r['stderr']}")
        created["db"] = True

        sql = (
            f"CREATE USER IF NOT EXISTS '{db_user}'@'localhost' "
            f"IDENTIFIED WITH mysql_native_password BY '{db_pass}';\n"
            f"GRANT ALL PRIVILEGES ON `{db_name}`.* TO '{db_user}'@'localhost';\n"
            f"FLUSH PRIVILEGES;\n"
        )
        r = mysql_cmd(cfg, sql)
        if r.get("stderr") and "ERROR" in r["stderr"]:
            raise Exception(f"MySQL error (create user): {r['stderr']}")
        created["db_user"] = True

        # ── 6. Configure WordPress ───────────────────────────────────────────
        log(f"▶ [6/7] Configuring WordPress (admin user, title)…")
        tmp_wp_pass = "/tmp/_panel_wp_install_pass"
        with open(tmp_wp_pass, "w") as f:
            f.write(wp_admin_pass)
        php_install = f"""<?php
$install_path = {repr(install_path)};
$site_url     = 'http://localhost:{port}';
$site_title   = {repr(wp_title)};
$admin_user   = {repr(wp_admin)};
$admin_email  = {repr(wp_email)};
$admin_pass   = trim(file_get_contents('/tmp/_panel_wp_install_pass'));

$_SERVER['HTTP_HOST']   = 'localhost:{port}';
$_SERVER['REQUEST_URI'] = '/';
$_SERVER['HTTPS']       = '';
$_SERVER['SERVER_PORT'] = {port};

define('ABSPATH',       $install_path . '/');
define('WP_INSTALLING', true);

require_once(ABSPATH . 'wp-load.php');
require_once(ABSPATH . 'wp-admin/includes/upgrade.php');

$result = wp_install($site_title, $admin_user, $admin_email, true, '', $admin_pass);
if (is_wp_error($result)) {{
    echo 'error:' . $result->get_error_message();
    exit(1);
}}
echo 'ok';
"""
        tmp_php = f"/tmp/_panel_wp_install_{site_name}.php"
        with open(tmp_php, "w") as f:
            f.write(php_install)
        r = run_cmd(f"php {tmp_php}", timeout=30)
        run_cmd(f"rm -f {tmp_php} {tmp_wp_pass}")
        if r["success"] and "ok" in r["stdout"]:
            log(f"  WP configured — admin: {wp_admin}")
        else:
            log(f"  WP auto-configure skipped/partial: {(r['stderr'] or r['stdout'] or '')[:200]}")
            log(f"  Visit http://localhost:{port}/wp-admin/install.php to finish setup manually.")

        install_selected_wp_plugins(install_path, selected_plugins, log)

        # ── 7. Done ──────────────────────────────────────────────────────────
        log("▶ [7/7] All done!")
        log(f"\n✔ WordPress installed at: http://localhost:{port}")
        log(f"\n  ── WordPress Admin ──")
        log(f"  URL      : http://localhost:{port}/wp-admin/")
        log(f"  Username : {wp_admin}")
        log(f"  Password : {wp_admin_pass}")
        log(f"\n  ── Database ──")
        log(f"  DB Name  : {db_name}")
        log(f"  DB User  : {db_user}")
        log(f"  DB Pass  : {db_pass}")
        log("\n  Save these credentials!")
        save_wp_admin_credential(install_path, wp_admin, wp_admin_pass)

        job["status"] = "done"
        job["result"] = {
            "success":        True,
            "url":            f"http://localhost:{port}",
            "admin_url":      f"http://localhost:{port}/wp-admin/",
            "setup_url":      f"http://localhost:{port}/wp-admin/install.php",
            "wp_admin":       wp_admin,
            "wp_admin_pass":  wp_admin_pass,
            "db_name":        db_name,
            "db_user":        db_user,
            "db_pass":        db_pass,
            "install_path":   install_path,
            "nginx_site":     site_name,
        }

    except Exception as e:
        log(f"\n✖ Error: {e}")
        log("↩ Rolling back what was created…")

        rb_nginx = site_name   if created["nginx"]   else None
        rb_db    = db_name     if created["db"]       else None
        rb_user  = db_user     if created["db_user"]  else None
        rb_path  = install_path if created["dir"]     else None

        msgs = delete_wordpress(rb_path, rb_db, rb_user, rb_nginx, cfg)
        for m in msgs:
            log(m)
        log("↩ Rollback complete.")

        job["status"] = "error"
        job["result"] = {"success": False, "error": str(e)}


# ── HTTP handler ──────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):

    def log_message(self, *_):
        pass  # silence access log

    def send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path, mime="text/html; charset=utf-8"):
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def read_body(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n)) if n else {}

    def authed(self):
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return False
        return self.valid_token(auth[7:])

    def valid_token(self, token):
        cfg = load_config()
        tokens = cfg.get("session_tokens", {})
        if token in tokens and time.time() - tokens[token] < 86400:
            return True
        return False

    def start_panel_services(self):
        php_ver, php_svc = detect_php_fpm()
        services = ["nginx", "mysql", php_svc]
        results = {}
        for svc in services:
            if svc in ALLOWED_SERVICES:
                results[svc] = run_cmd(f"sudo systemctl start {svc}", timeout=20)
        return results

    def stop_panel_services(self):
        php_ver, php_svc = detect_php_fpm()
        services = [php_svc, "mysql", "nginx"]
        results = {}
        for svc in services:
            if svc in ALLOWED_SERVICES:
                results[svc] = run_cmd(f"sudo systemctl stop {svc}", timeout=20)
        return results

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type,Authorization")
        self.end_headers()

    # ── GET ──────────────────────────────────────────────────────────────────

    def do_GET(self):
        path = urlparse(self.path).path

        if path in ("/", "/index.html"):
            self.send_file(os.path.join(SCRIPT_DIR, "index.html"))
            return

        if not self.authed():
            self.send_json({"error": "Unauthorized"}, 401)
            return

        cfg = load_config()

        if path == "/api/status":
            nginx = svc_status("nginx")
            mysql = svc_status("mysql") if svc_status("mysql") == "active" else svc_status("mariadb")
            self.send_json({
                "nginx": nginx,
                "mysql": mysql,
                "system": get_system_info(),
            })

        elif path == "/api/nginx/sites":
            self.send_json({"success": True, "sites": get_nginx_sites()})

        elif path == "/api/nginx/config":
            try:
                content = open("/etc/nginx/nginx.conf").read()
                self.send_json({"success": True, "content": content})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)})

        elif path.startswith("/api/nginx/site/"):
            name = path.split("/")[-1]
            if not re.fullmatch(r'[\w\-\.]+', name):
                self.send_json({"success": False, "error": "Bad name"}); return
            try:
                content = open(f"/etc/nginx/sites-available/{name}").read()
                self.send_json({"success": True, "content": content})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)})

        elif path == "/api/nginx/logs/error":
            r = run_cmd("sudo tail -200 /var/log/nginx/error.log 2>/dev/null")
            self.send_json({"success": True, "logs": r["stdout"] or r["stderr"]})

        elif path == "/api/nginx/logs/access":
            r = run_cmd("sudo tail -200 /var/log/nginx/access.log 2>/dev/null")
            self.send_json({"success": True, "logs": r["stdout"] or r["stderr"]})

        elif path == "/api/mysql/databases":
            r = mysql_cmd(cfg, "SHOW DATABASES;")
            if r["success"]:
                dbs = [l.strip() for l in r["stdout"].splitlines() if l.strip() and l.strip() != "Database"]
                self.send_json({"success": True, "databases": dbs})
            else:
                self.send_json({"success": False, "error": r["stderr"] or r.get("error","Failed")})

        elif path == "/api/wordpress/sites":
            self.send_json({"success": True, "sites": get_wp_sites()})

        elif path == "/api/wordpress/plugins":
            self.send_json(get_wp_plugin_library())

        elif path == "/api/laravel/apps":
            self.send_json({"success": True, "apps": get_laravel_apps()})

        elif path == "/api/codeigniter/apps":
            self.send_json({"success": True, "apps": get_codeigniter_apps()})

        elif path == "/api/php-projects/apps":
            self.send_json({"success": True, "apps": get_php_projects()})

        elif path == "/api/wordpress/next_port":
            self.send_json({"success": True, "port": find_next_port()})

        elif path == "/api/laravel/next_port":
            self.send_json({"success": True, "port": find_next_port(8100)})

        elif path == "/api/codeigniter/next_port":
            self.send_json({"success": True, "port": find_next_port(8200)})

        elif path == "/api/php-projects/next_port":
            self.send_json({"success": True, "port": find_next_port(8300)})

        elif path == "/api/wordpress/credentials":
            qs = parse_qs(urlparse(self.path).query)
            wp_path = qs.get("path", [None])[0]
            if not wp_path:
                self.send_json({"success": False, "error": "Missing path"}); return
            try:
                creds = read_wp_config(wp_path)
                self.send_json({"success": True, **creds})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)})

        elif path == "/api/system/info":
            self.send_json(get_system_info())

        elif path.startswith("/api/wordpress/install/") or path.startswith("/api/wordpress/delete/"):
            job_id = path.split("/")[-1]
            if job_id in _jobs:
                self.send_json(_jobs[job_id])
            else:
                self.send_json({"error": "Job not found"}, 404)

        elif path.startswith("/api/laravel/install/") or path.startswith("/api/laravel/delete/"):
            job_id = path.split("/")[-1]
            if job_id in _jobs:
                self.send_json(_jobs[job_id])
            else:
                self.send_json({"error": "Job not found"}, 404)

        elif path.startswith("/api/codeigniter/install/") or path.startswith("/api/codeigniter/delete/"):
            job_id = path.split("/")[-1]
            if job_id in _jobs:
                self.send_json(_jobs[job_id])
            else:
                self.send_json({"error": "Job not found"}, 404)

        elif path.startswith("/api/php-projects/install/") or path.startswith("/api/php-projects/delete/"):
            job_id = path.split("/")[-1]
            if job_id in _jobs:
                self.send_json(_jobs[job_id])
            else:
                self.send_json({"error": "Job not found"}, 404)

        elif path == "/api/performance":
            self.send_json({
                "nginx": get_perf_nginx(),
                "php":   get_perf_php(),
                "fpm":   get_perf_fpm(),
                "mysql": get_perf_mysql(),
            })

        elif path == "/api/phpmyadmin/status":
            self.send_json(get_phpmyadmin_info())

        elif path == "/api/phpmyadmin/config":
            info = get_phpmyadmin_info()
            if not info["config_exists"]:
                self.send_json({"success": False, "error": "config.inc.php not found – install phpMyAdmin first"})
                return
            try:
                content = open(info["config_path"]).read()
                self.send_json({"success": True, "content": content})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)})

        elif path == "/api/phpmyadmin/nginx":
            avail = "/etc/nginx/sites-available/phpmyadmin"
            if os.path.exists(avail):
                try:
                    self.send_json({"success": True, "content": open(avail).read()})
                except Exception as e:
                    self.send_json({"success": False, "error": str(e)})
            else:
                # Return a generated template
                php_ver, _ = detect_php_fpm()
                content     = PMA_NGINX_TEMPLATE.format(port=8081, phpver=php_ver)
                self.send_json({"success": True, "content": content, "generated": True})

        else:
            self.send_json({"error": "Not found"}, 404)

    # ── POST ─────────────────────────────────────────────────────────────────

    def do_POST(self):
        path = urlparse(self.path).path

        # Login is unauthenticated
        if path == "/api/login":
            data = self.read_body()
            pw = data.get("password", "")
            cfg = load_config()
            if hashlib.sha256(pw.encode()).hexdigest() == cfg["password_hash"]:
                token = secrets.token_hex(32)
                cfg.setdefault("session_tokens", {})[token] = time.time()
                save_config(cfg)
                self.send_json({"success": True, "token": token})
            else:
                self.send_json({"success": False, "error": "Wrong password"}, 401)
            return

        if path == "/api/panel/close":
            data = self.read_body()
            if not self.valid_token(data.get("token", "")):
                self.send_json({"error": "Unauthorized"}, 401)
                return
            results = self.stop_panel_services()
            self.send_json({"success": True, "results": results})
            return

        if not self.authed():
            self.send_json({"error": "Unauthorized"}, 401)
            return

        cfg  = load_config()
        data = self.read_body()

        # Service control  /api/services/<service>/<action>
        if path.startswith("/api/services/"):
            parts = path.strip("/").split("/")
            if len(parts) == 4:
                _, _, svc, action = parts
                if svc in ALLOWED_SERVICES and action in ALLOWED_ACTIONS:
                    r = run_cmd(f"sudo systemctl {action} {svc}")
                    time.sleep(1)
                    self.send_json({**r, "status": svc_status(svc)})
                else:
                    self.send_json({"success": False, "error": "Not allowed"})
            else:
                self.send_json({"success": False, "error": "Bad path"})

        elif path == "/api/panel/open":
            results = self.start_panel_services()
            time.sleep(1)
            self.send_json({"success": True, "results": results})

        elif path == "/api/nginx/validate":
            r = run_cmd("sudo nginx -t")
            self.send_json({"success": r["returncode"] == 0,
                            "output": r["stdout"] + r["stderr"]})

        elif path == "/api/open_folder":
            folder = os.path.realpath(data.get("path", ""))
            allowed_roots = ["/var/www", "/opt"]
            if not folder or not os.path.isdir(folder):
                self.send_json({"success": False, "error": "Folder not found"}); return
            if not any(folder == root or folder.startswith(root + os.sep) for root in allowed_roots):
                self.send_json({"success": False, "error": "Folder is outside allowed web roots"}); return
            try:
                subprocess.Popen(["xdg-open", folder], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.send_json({"success": True})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)})

        elif path == "/api/nginx/config":
            content = data.get("content", "")
            tmp = "/tmp/_panel_nginx_main.conf"
            with open(tmp, "w") as f:
                f.write(content)
            test = run_cmd(f"sudo nginx -t -c {tmp}")
            if not test["success"]:
                self.send_json({"success": False, "error": "Config test failed",
                                "details": test["stderr"]}); return
            r = run_cmd(f"sudo cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.bak && sudo cp {tmp} /etc/nginx/nginx.conf")
            self.send_json(r)

        elif path.startswith("/api/nginx/site/"):
            name = path.split("/")[-1]
            if not re.fullmatch(r'[\w\-\.]+', name):
                self.send_json({"success": False, "error": "Bad name"}); return
            action = data.get("action", "save")
            if action == "enable":
                r = run_cmd(f"sudo ln -sf /etc/nginx/sites-available/{name} /etc/nginx/sites-enabled/{name}")
                self.send_json(r)
            elif action == "disable":
                r = run_cmd(f"sudo rm -f /etc/nginx/sites-enabled/{name}")
                self.send_json(r)
            elif action == "save":
                content = data.get("content", "")
                tmp = f"/tmp/_panel_site_{name}"
                with open(tmp, "w") as f:
                    f.write(content)
                r = run_cmd(f"sudo cp {tmp} /etc/nginx/sites-available/{name}")
                self.send_json(r)
            else:
                self.send_json({"success": False, "error": "Unknown action"})

        elif path == "/api/mysql/databases":
            name = data.get("name", "")
            if not re.fullmatch(r'[\w\-]+', name):
                self.send_json({"success": False, "error": "Invalid DB name"}); return
            r = mysql_cmd(cfg, f"CREATE DATABASE `{name}`;")
            self.send_json(r)

        elif path == "/api/mysql/query":
            query = data.get("query", "").strip()
            database = data.get("database", "_none_")
            if not query:
                self.send_json({"success": False, "error": "Empty query"}); return
            r = mysql_cmd(cfg, query, database)
            self.send_json(r)

        elif path == "/api/settings":
            if data.get("new_password"):
                cfg["password_hash"] = hashlib.sha256(data["new_password"].encode()).hexdigest()
                cfg["session_tokens"] = {}  # invalidate sessions
            if "mysql_user" in data:
                cfg["mysql_user"] = data["mysql_user"]
            if "mysql_password" in data:
                cfg["mysql_password"] = data["mysql_password"]
            save_config(cfg)
            self.send_json({"success": True})

        elif path == "/api/wordpress/install":
            required = ["site_name", "db_name", "db_user", "db_pass", "port"]
            missing  = [k for k in required if not data.get(k)]
            if missing:
                self.send_json({"success": False, "error": f"Missing: {', '.join(missing)}"}); return
            try:
                site_name = re.sub(r"[^\w\-]", "", data.get("site_name", ""))
                if not site_name:
                    raise ValueError("Site name is invalid")
                validate_install_path(data.get("install_path", f"/var/www/{site_name}"))
                parse_port(data.get("port"), None)
                if "'" in data.get("db_pass", "") or "\\" in data.get("db_pass", ""):
                    raise ValueError("Database password cannot contain single quotes or backslashes")
            except ValueError as e:
                self.send_json({"success": False, "error": str(e)}); return
            job_id = secrets.token_hex(8)
            _jobs[job_id] = {"status": "running", "logs": [], "result": {}}
            t = threading.Thread(target=install_wordpress_job, args=(job_id, data, cfg), daemon=True)
            t.start()
            self.send_json({"success": True, "job_id": job_id})

        elif path == "/api/wordpress/port":
            nginx_site = data.get("nginx_site", "")
            try:
                port = parse_port(data.get("port"), None)
            except ValueError as e:
                self.send_json({"success": False, "error": str(e)}); return
            r = set_nginx_site_port(nginx_site, port)
            self.send_json(r)

        elif path == "/api/laravel/install":
            job_id = secrets.token_hex(8)
            _jobs[job_id] = {"status": "running", "logs": [], "result": {}}
            t = threading.Thread(target=install_laravel_job, args=(job_id, data, cfg), daemon=True)
            t.start()
            self.send_json({"success": True, "job_id": job_id})

        elif path == "/api/laravel/port":
            nginx_site = data.get("nginx_site", "")
            try:
                port = parse_port(data.get("port"), None)
            except ValueError as e:
                self.send_json({"success": False, "error": str(e)}); return
            helper = os.path.join(SCRIPT_DIR, "laravel-helper.sh")
            r = run_cmd(f"sudo {shell_quote(helper)} set-port {shell_quote(nginx_site)} {shell_quote(port)}", timeout=30)
            self.send_json({**r, "port": port})

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

        elif path == "/api/php-projects/install":
            job_id = secrets.token_hex(8)
            _jobs[job_id] = {"status": "running", "logs": [], "result": {}}
            t = threading.Thread(target=install_php_project_job, args=(job_id, data, cfg), daemon=True)
            t.start()
            self.send_json({"success": True, "job_id": job_id})

        elif path == "/api/php-projects/port":
            nginx_site = data.get("nginx_site", "")
            try:
                port = parse_port(data.get("port"), None)
            except ValueError as e:
                self.send_json({"success": False, "error": str(e)}); return
            helper = os.path.join(SCRIPT_DIR, "php-project-helper.sh")
            r = run_cmd(f"sudo {shell_quote(helper)} set-port {shell_quote(nginx_site)} {shell_quote(port)}", timeout=30)
            self.send_json({**r, "port": port})

        elif path == "/api/laravel/artisan":
            app_path = data.get("path", "").strip()
            action = data.get("action", "").strip()
            commands = {
                "migrate": "php artisan migrate --force",
                "cache_clear": "php artisan cache:clear && php artisan config:clear && php artisan route:clear && php artisan view:clear",
                "storage_link": "php artisan storage:link",
                "composer_install": "composer install --no-interaction",
            }
            real = os.path.realpath(app_path)
            if action not in commands:
                self.send_json({"success": False, "error": "Unknown Laravel action"}); return
            if not (os.path.isfile(os.path.join(real, "artisan")) and (real.startswith("/var/www/") or real.startswith("/opt/"))):
                self.send_json({"success": False, "error": "Invalid Laravel app path"}); return
            r = run_cmd(f"cd {shell_quote(real)} && {commands[action]}", timeout=600)
            self.send_json(r)

        elif path == "/api/performance/nginx":
            try:
                content = open("/etc/nginx/nginx.conf").read()
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}); return
            for key, value in data.items():
                content, _ = set_nginx_value(content, key, str(value))
            tmp = "/tmp/_panel_perf_nginx.conf"
            with open(tmp, "w") as f:
                f.write(content)
            helper = os.path.join(SCRIPT_DIR, "perf-helper.sh")
            r = run_cmd(f"sudo {helper} nginx {tmp} /etc/nginx/nginx.conf", timeout=30)
            self.send_json({"success": r["success"], "error": "Config test failed" if not r["success"] else "", "output": r["stdout"] + r["stderr"]})

        elif path == "/api/performance/php":
            path_ = get_php_ini_path()
            try:
                content = open(path_).read()
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}); return
            for key, value in data.items():
                if key != "path":
                    content = set_ini_value(content, key, str(value))
            tmp = "/tmp/_panel_perf_php.ini"
            with open(tmp, "w") as f:
                f.write(content)
            helper = os.path.join(SCRIPT_DIR, "perf-helper.sh")
            r = run_cmd(f"sudo {helper} php {tmp} {path_}", timeout=30)
            self.send_json({"success": r["success"], "output": r["stdout"] + r["stderr"]})

        elif path == "/api/performance/fpm":
            path_ = get_fpm_pool_path()
            try:
                content = open(path_).read()
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}); return
            for key, value in data.items():
                if key != "path":
                    content = set_ini_value(content, key, str(value))
            tmp = "/tmp/_panel_perf_fpm.conf"
            with open(tmp, "w") as f:
                f.write(content)
            helper = os.path.join(SCRIPT_DIR, "perf-helper.sh")
            r = run_cmd(f"sudo {helper} fpm {tmp} {path_}", timeout=30)
            self.send_json({"success": r["success"], "output": r["stdout"] + r["stderr"]})

        elif path == "/api/performance/mysql":
            path_ = get_mysql_conf_path()
            try:
                content = open(path_).read()
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}); return
            for key, value in data.items():
                if key != "path":
                    content = set_ini_value(content, key, str(value))
            tmp = "/tmp/_panel_perf_mysql.cnf"
            with open(tmp, "w") as f:
                f.write(content)
            helper = os.path.join(SCRIPT_DIR, "perf-helper.sh")
            r = run_cmd(f"sudo {helper} mysql {tmp} {path_}", timeout=60)
            self.send_json({"success": r["success"], "output": r["stdout"] + r["stderr"]})

        elif path == "/api/phpmyadmin/install":
            # Non-interactive apt install; DEBIAN_FRONTEND avoids debconf prompts
            r = run_cmd(
                "sudo DEBIAN_FRONTEND=noninteractive apt-get install -y phpmyadmin php-mbstring php-zip php-gd php-json php-curl 2>&1",
                timeout=300
            )
            self.send_json({**r, "installed": os.path.isdir("/usr/share/phpmyadmin")})

        elif path == "/api/phpmyadmin/config":
            info = get_phpmyadmin_info()
            if not info["config_exists"]:
                self.send_json({"success": False, "error": "Install phpMyAdmin first"}); return
            content = data.get("content", "")
            tmp = "/tmp/_panel_pma_config.php"
            with open(tmp, "w") as f:
                f.write(content)
            r = run_cmd(f"sudo cp {tmp} {info['config_path']}")
            self.send_json(r)

        elif path == "/api/phpmyadmin/nginx":
            action  = data.get("action", "save")
            avail   = "/etc/nginx/sites-available/phpmyadmin"
            enabled = "/etc/nginx/sites-enabled/phpmyadmin"

            if action == "generate":
                php_ver, _ = detect_php_fpm()
                try:
                    port = parse_port(data.get("port", 8081), 8081)
                except ValueError as e:
                    self.send_json({"success": False, "error": str(e)}); return
                content    = PMA_NGINX_TEMPLATE.format(port=port, phpver=php_ver)
                self.send_json({"success": True, "content": content})

            elif action == "save":
                content = data.get("content", "")
                tmp     = "/tmp/_panel_pma_nginx"
                with open(tmp, "w") as f:
                    f.write(content)
                r = run_cmd(f"sudo cp {tmp} {avail}")
                self.send_json(r)

            elif action == "enable":
                r = run_cmd(f"sudo ln -sf {avail} {enabled} && sudo nginx -t && sudo systemctl reload nginx")
                self.send_json(r)

            elif action == "disable":
                r = run_cmd(f"sudo rm -f {enabled} && sudo systemctl reload nginx")
                self.send_json(r)

            else:
                self.send_json({"success": False, "error": "Unknown action"})

        elif path == "/api/wordpress/change_db_password":
            install_path = data.get("install_path", "").strip()
            db_user      = data.get("db_user", "").strip()
            new_pass     = data.get("new_pass", "").strip()
            if not all([install_path, db_user, new_pass]):
                self.send_json({"success": False, "error": "Missing required fields"}); return
            if not re.fullmatch(r"[\w\-]+", db_user):
                self.send_json({"success": False, "error": "Invalid DB user"}); return
            if "'" in new_pass or "\\" in new_pass:
                self.send_json({"success": False, "error": "Password cannot contain quotes or backslashes"}); return
            # 1. Update MySQL password
            sql = f"ALTER USER '{db_user}'@'localhost' IDENTIFIED BY '{new_pass}'; FLUSH PRIVILEGES;"
            r = mysql_cmd(cfg, sql)
            if r.get("stderr") and "ERROR" in r["stderr"]:
                self.send_json({"success": False, "error": r["stderr"]}); return
            # 2. Update wp-config.php
            try:
                wp_cfg_path = os.path.join(install_path, "wp-config.php")
                content = open(wp_cfg_path).read()
                content = re.sub(
                    r"define\(\s*'DB_PASSWORD',\s*'[^']*'\s*\)",
                    f"define( 'DB_PASSWORD', '{new_pass}' )",
                    content
                )
                tmp = "/tmp/_panel_wpconfig_dbpass.php"
                with open(tmp, "w") as f:
                    f.write(content)
                r2 = run_cmd(f"sudo cp {tmp} {shell_quote(wp_cfg_path)}")
                self.send_json({"success": True, "config_updated": r2["success"]})
            except Exception as e:
                self.send_json({"success": True, "config_updated": False, "config_error": str(e)})

        elif path == "/api/wordpress/change_wp_admin":
            install_path  = data.get("install_path", "").strip()
            wp_admin_user = data.get("wp_admin_user", "").strip()
            new_pass      = data.get("new_pass", "").strip()
            if not all([install_path, new_pass]):
                self.send_json({"success": False, "error": "Missing required fields"}); return
            if wp_admin_user and not re.fullmatch(r"[\w\-.@]+", wp_admin_user):
                self.send_json({"success": False, "error": "Invalid WP admin username"}); return
            if not wp_admin_user:
                old_creds = get_wp_admin_credential(install_path)
                wp_admin_user = old_creds.get("username") or detect_wp_admin_user_for_path(install_path)
            if not wp_admin_user:
                self.send_json({"success": False, "error": "No WP admin user selected or detected"}); return
            # Write password to temp file to avoid shell injection
            tmp_pass = "/tmp/_panel_wp_adminpass"
            with open(tmp_pass, "w") as f:
                f.write(new_pass)
            # Try wp-cli first
            if os.path.exists("/usr/local/bin/wp"):
                r = run_cmd(
                    f"wp user update {shell_quote(wp_admin_user)} --user_pass={shell_quote(new_pass)} --path={shell_quote(install_path)} --allow-root",
                    timeout=30
                )
                if r["success"]:
                    save_wp_admin_credential(install_path, wp_admin_user, new_pass)
                    self.send_json({"success": True, "method": "wp-cli"}); return
            # Fallback: PHP script using WP's phpass library
            php_script = f"""<?php
$install_path = {repr(install_path)};
$admin_user = {repr(wp_admin_user)};
$new_pass = trim(file_get_contents('/tmp/_panel_wp_adminpass'));
if (!$new_pass) {{ echo 'error:empty'; exit(1); }}
require_once($install_path . '/wp-includes/class-phpass.php');
$cfg = file_get_contents($install_path . '/wp-config.php');
preg_match("/define\\(\\s*'DB_NAME',\\s*'([^']+)'\\s*\\)/", $cfg, $m); $db_name = $m[1];
preg_match("/define\\(\\s*'DB_USER',\\s*'([^']+)'\\s*\\)/", $cfg, $m); $db_user = $m[1];
preg_match("/define\\(\\s*'DB_PASSWORD',\\s*'([^']*)'\\s*\\)/", $cfg, $m); $db_pass = isset($m[1]) ? $m[1] : '';
preg_match("/define\\(\\s*'DB_HOST',\\s*'([^']+)'\\s*\\)/", $cfg, $m); $db_host = isset($m[1]) ? $m[1] : 'localhost';
preg_match("/\\\\\\$table_prefix\\s*=\\s*'([^']+)'/", $cfg, $m); $pfx = isset($m[1]) ? $m[1] : 'wp_';
$hasher = new PasswordHash(8, true);
$hash = $hasher->HashPassword($new_pass);
$pdo = new PDO("mysql:host=$db_host;dbname=$db_name;charset=utf8", $db_user, $db_pass);
$stmt = $pdo->prepare("UPDATE {{$pfx}}users SET user_pass = ?, user_activation_key = '' WHERE user_login = ?");
$stmt->execute([$hash, $admin_user]);
if ($stmt->rowCount() < 1) {{ echo 'error:user not found'; exit(1); }}
echo 'ok';
"""
            tmp_php = "/tmp/_panel_wp_setpass.php"
            with open(tmp_php, "w") as f:
                f.write(php_script)
            r = run_cmd(f"php {tmp_php}", timeout=15)
            run_cmd(f"rm -f {tmp_pass} {tmp_php}")
            if r["success"] and "ok" in r["stdout"]:
                save_wp_admin_credential(install_path, wp_admin_user, new_pass)
                self.send_json({"success": True, "method": "php"})
            else:
                self.send_json({"success": False, "error": r["stderr"] or r["stdout"] or r.get("error", "Failed")})

        elif path == "/api/phpmyadmin/blowfish":
            import string, random
            chars = string.ascii_letters + string.digits + "!@#$%^&*()-_=+[]{}|;:,.<>?"
            secret = "".join(random.SystemRandom().choice(chars) for _ in range(32))
            self.send_json({"success": True, "secret": secret})

        else:
            self.send_json({"error": "Not found"}, 404)

    # ── DELETE ────────────────────────────────────────────────────────────────

    def do_DELETE(self):
        path = urlparse(self.path).path
        if not self.authed():
            self.send_json({"error": "Unauthorized"}, 401)
            return
        cfg  = load_config()
        data = self.read_body()

        if path.startswith("/api/mysql/databases/"):
            name = path.split("/")[-1]
            if not re.fullmatch(r'[\w\-]+', name):
                self.send_json({"success": False, "error": "Invalid name"}); return
            r = mysql_cmd(cfg, f"DROP DATABASE `{name}`;")
            self.send_json(r)

        elif path == "/api/wordpress/sites":
            install_path = data.get("install_path", "")
            db_name      = data.get("db_name", "")
            db_user      = data.get("db_user", "")
            nginx_site   = data.get("nginx_site", "")
            job_id       = secrets.token_hex(8)
            _jobs[job_id] = {"status": "running", "logs": [], "result": {}}
            t = threading.Thread(
                target=delete_wordpress_job,
                args=(job_id, install_path, db_name, db_user, nginx_site, cfg),
                daemon=True
            )
            t.start()
            self.send_json({"success": True, "job_id": job_id})

        elif path == "/api/laravel/apps":
            app_path   = data.get("path", "")
            db_name    = data.get("db_name", "")
            db_user    = data.get("db_user", "")
            nginx_site = data.get("nginx_site", "")
            job_id     = secrets.token_hex(8)
            _jobs[job_id] = {"status": "running", "logs": [], "result": {}}
            t = threading.Thread(
                target=delete_laravel_job,
                args=(job_id, app_path, db_name, db_user, nginx_site, cfg),
                daemon=True,
            )
            t.start()
            self.send_json({"success": True, "job_id": job_id})

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

        elif path == "/api/php-projects/apps":
            app_path   = data.get("path", "")
            db_name    = data.get("db_name", "")
            db_user    = data.get("db_user", "")
            nginx_site = data.get("nginx_site", "")
            job_id     = secrets.token_hex(8)
            _jobs[job_id] = {"status": "running", "logs": [], "result": {}}
            t = threading.Thread(
                target=delete_php_project_job,
                args=(job_id, app_path, db_name, db_user, nginx_site, cfg),
                daemon=True,
            )
            t.start()
            self.send_json({"success": True, "job_id": job_id})

        else:
            self.send_json({"error": "Not found"}, 404)


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)

    html = os.path.join(SCRIPT_DIR, "index.html")
    if not os.path.exists(html):
        print(f"ERROR: index.html not found in {SCRIPT_DIR}")
        raise SystemExit(1)

    print(f"╔══════════════════════════════════════╗")
    print(f"║   Server Management Panel  v1.1      ║")
    print(f"╚══════════════════════════════════════╝")
    print(f"  URL      : http://{HOST}:{PORT}")
    print(f"  Password : admin  (change in Settings)")
    print(f"  Stop     : Ctrl+C")
    print()

    server = ThreadingHTTPServer((HOST, PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
