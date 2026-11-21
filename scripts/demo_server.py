#!/usr/bin/env python3
"""Serve the panel UI against fixed, read-only demo data on loopback."""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
ASSETS = (ROOT / "assets").resolve()
ASSET_TYPES = {
    ".woff2": "font/woff2",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}

BOOTSTRAP = """<script>
localStorage.setItem('panel_token', 'demo');
const demoTheme = new URLSearchParams(location.search).get('theme');
if (demoTheme === 'dark' || demoTheme === 'light') {
  localStorage.setItem('panel_theme', demoTheme);
}
if (location.hash === '#apps') {
  history.replaceState(null, '', '#app-launcher');
}
</script>
"""

SYSTEM = {
    "cpu": "8.4%",
    "mem_total": "16 GiB",
    "mem_used": "4.2 GiB",
    "mem_free": "11.8 GiB",
    "disk_total": "240 GiB",
    "disk_used": "62 GiB",
    "disk_pct": "26%",
    "uptime": "up 2 days, 4 hours",
    "hostname": "dev-laptop",
}

PHPMYADMIN = {
    "installed": True,
    "config_path": "/etc/phpmyadmin/config.inc.php",
    "config_exists": True,
    "nginx_site_exists": True,
    "nginx_site_enabled": True,
    "php_version": "8.3",
    "php_fpm_service": "php8.3-fpm",
    "php_fpm_status": "active",
    "pma_port": 8081,
    "url": "http://phpmyadmin.example.test:8081",
}


def demo_app(name, port, modified_at):
    slug = name.replace("-", "_")
    return {
        "name": name,
        "path": f"/var/www/{name}",
        "db_name": f"{slug}_db",
        "db_user": f"{slug}_user",
        "nginx_site": name,
        "port": port,
        "modified_at": modified_at,
    }


WORDPRESS = [
    {
        **demo_app(name, port, modified_at),
        "wp_version": version,
        "table_prefix": "wp_",
        "wp_admin_users": ["admin"],
        "wp_admin_user": "admin",
        "has_wpcli": True,
        "auto_login": {"installed": enabled, "active": enabled},
    }
    for name, port, modified_at, version, enabled in (
        ("acme-shop", 8082, 1782302400, "6.9.1", True),
        ("demo-blog", 8083, 1782216000, "6.9.2", False),
        ("example-journal", 8084, 1782129600, "6.8.3", False),
    )
]

LARAVEL = {
    **demo_app("demo-inventory", 8100, 1782043200),
    "app_name": "Demo Inventory",
    "app_url": "http://demo-inventory.example.test:8100",
    "version": "Laravel Framework 12.10.0",
    "db_pass": "admin",
}

CODEIGNITER = {
    **demo_app("sample-directory", 8200, 1781956800),
    "app_url": "http://sample-directory.example.test:8200",
    "version": "CodeIgniter v4.6.1",
    "db_pass": "admin",
}

PHP_PROJECT = {
    **demo_app("portfolio-site", 8300, 1781870400),
    "install_path": "/var/www/portfolio-site",
    "template": "php",
    "db_name": "",
    "db_user": "",
    "db_created": False,
    "created_at": 1781784000,
}

NGINX_SITES = [
    {"name": "default", "server_name": "_", "enabled": False},
    {"name": "phpmyadmin", "server_name": "phpmyadmin.example.test", "enabled": True},
    *[
        {"name": app["name"], "server_name": f"{app['name']}.example.test", "enabled": True}
        for app in [*WORDPRESS, LARAVEL, CODEIGNITER, PHP_PROJECT]
    ],
]

PERFORMANCE = {
    "nginx": {
        "worker_processes": "auto", "worker_connections": "1024",
        "keepalive_timeout": "65", "client_max_body_size": "32m",
        "gzip": "on", "gzip_comp_level": "6", "server_tokens": "off",
    },
    "php": {
        "path": "/etc/php/8.3/fpm/php.ini", "memory_limit": "256M",
        "max_execution_time": "30", "max_input_time": "60",
        "upload_max_filesize": "32M", "post_max_size": "40M", "max_file_uploads": "20",
    },
    "fpm": {
        "path": "/etc/php/8.3/fpm/pool.d/www.conf", "pm": "dynamic",
        "pm.max_children": "12", "pm.start_servers": "3", "pm.min_spare_servers": "2",
        "pm.max_spare_servers": "5", "pm.max_requests": "500",
        "request_terminate_timeout": "0",
    },
    "mysql": {
        "path": "/etc/mysql/mysql.conf.d/mysqld.cnf", "max_connections": "151",
        "innodb_buffer_pool_size": "256M", "slow_query_log": "0",
        "long_query_time": "2", "max_allowed_packet": "64M",
    },
}


def site_config(name, port, root):
    return {
        "success": True,
        "content": (
            f"server {{\n    listen {port};\n    server_name {name}.example.test;\n"
            f"    root {root};\n    index index.php index.html;\n}}\n"
        ),
    }


SITE_CONFIGS = {
    app["nginx_site"]: site_config(
        app["name"], app["port"], app["path"] + ("/public" if app in (LARAVEL, CODEIGNITER) else "")
    )
    for app in [*WORDPRESS, LARAVEL, CODEIGNITER, PHP_PROJECT]
}
SITE_CONFIGS["default"] = site_config("default", 80, "/var/www/html")
SITE_CONFIGS["phpmyadmin"] = site_config("phpmyadmin", PHPMYADMIN["pma_port"], "/usr/share/phpmyadmin")

GET_RESPONSES = {
    "/api/status": {"nginx": "active", "mysql": "active", "system": SYSTEM},
    "/api/system/info": SYSTEM,
    "/api/settings": {"username": "admin", "home_dir": "/home/demo", "default_install_location": "home-local"},
    "/api/wordpress/sites": {"success": True, "sites": WORDPRESS},
    "/api/wordpress/plugins": {"success": True, "plugins": [], "invalid": []},
    "/api/wordpress/core-update-status": {
        "success": True,
        "cached_version": "6.9.2",
        "target_version": "6.9.2",
        "cache_state": "current",
        "sites": [
            {
                "path": site["path"], "name": site["name"],
                "installed_version": site["wp_version"],
                "needs_update": site["wp_version"] != "6.9.2",
            }
            for site in WORDPRESS
        ],
    },
    "/api/laravel/apps": {"success": True, "apps": [LARAVEL]},
    "/api/codeigniter/apps": {"success": True, "apps": [CODEIGNITER]},
    "/api/php-projects/apps": {"success": True, "apps": [PHP_PROJECT]},
    "/api/wordpress/next_port": {"success": True, "port": 8085},
    "/api/laravel/next_port": {"success": True, "port": 8101},
    "/api/codeigniter/next_port": {"success": True, "port": 8201},
    "/api/php-projects/next_port": {"success": True, "port": 8301},
    "/api/nginx/sites": {"success": True, "sites": sorted(NGINX_SITES, key=lambda site: site["name"])},
    "/api/nginx/config": {
        "success": True,
        "content": (
            "worker_processes auto;\nevents { worker_connections 1024; }\n"
            "http {\n    include /etc/nginx/mime.types;\n"
            "    include /etc/nginx/sites-enabled/*;\n}\n"
        ),
    },
    "/api/nginx/logs/error": {
        "success": True,
        "logs": '2026/06/24 09:30:00 [notice] 1000#1000: signal process started\n',
    },
    "/api/nginx/logs/access": {
        "success": True,
        "logs": '192.0.2.10 - - [24/Jun/2026:09:30:01 +0000] "GET / HTTP/1.1" 200 1842 "-" "Demo browser"\n',
    },
    "/api/mysql/databases": {
        "success": True,
        "databases": [
            "information_schema", "performance_schema", "mysql", "sys",
            *[app["db_name"] for app in [*WORDPRESS, LARAVEL, CODEIGNITER]],
        ],
    },
    "/api/performance": PERFORMANCE,
    "/api/phpmyadmin/status": PHPMYADMIN,
    "/api/phpmyadmin/config": {
        "success": True,
        "content": "<?php\n$cfg['Servers'][1]['auth_type'] = 'cookie';\n",
    },
    "/api/phpmyadmin/nginx": SITE_CONFIGS["phpmyadmin"],
}
JOB_ROUTE = re.compile(
    r"/api/(?:(?:wordpress|laravel|codeigniter|php-projects)/(?:install|delete)"
    r"|wordpress/core-update)/[^/]+"
)
REFUSED = {"success": False, "error": "Demo mode: changes are disabled."}


class DemoHandler(BaseHTTPRequestHandler):
    def send_bytes(self, body, mime, status=200):
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, value, status=200):
        self.send_bytes(json.dumps(value).encode("utf-8"), "application/json", status)

    def serve_asset(self, path):
        try:
            relative = Path(unquote(path))
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("Invalid asset path")
            asset = (ASSETS / relative).resolve()
            asset.relative_to(ASSETS)
            mime = ASSET_TYPES.get(asset.suffix.lower())
            if not mime or not asset.is_file():
                raise ValueError("Unsupported asset")
            body = asset.read_bytes()
        except (OSError, ValueError, RuntimeError):
            self.send_json({"error": "Not found"}, 404)
            return
        self.send_bytes(body, mime)

    def do_GET(self):
        url = urlsplit(self.path)
        path = url.path
        if path in ("/", "/index.html"):
            html = (ROOT / "index.html").read_text(encoding="utf-8")
            html = html.replace("<head>", "<head>\n" + BOOTSTRAP, 1)
            self.send_bytes(html.encode("utf-8"), "text/html; charset=utf-8")
        elif path.startswith("/assets/"):
            self.serve_asset(path[len("/assets/"):])
        elif path.startswith("/api/nginx/site/"):
            name = path[len("/api/nginx/site/"):]
            self.send_json(SITE_CONFIGS.get(name, {"success": False, "error": "Site not found"}))
        elif path == "/api/wordpress/credentials":
            site_path = parse_qs(url.query).get("path", [""])[0]
            for site in WORDPRESS:
                if site_path == site["path"]:
                    self.send_json({
                        "success": True, "db_name": site["db_name"], "db_user": site["db_user"],
                        "db_pass": "admin", "db_host": "localhost", "table_prefix": site["table_prefix"],
                    })
                    return
            error = "Site not found" if site_path else "Missing path"
            self.send_json({"success": False, "error": error})
        elif JOB_ROUTE.fullmatch(path):
            self.send_json({"error": "Job not found"}, 404)
        else:
            self.send_json(GET_RESPONSES.get(path, {}))

    def do_POST(self):
        path = urlsplit(self.path).path
        if path == "/api/login":
            self.send_json({"success": True, "token": "demo"})
        elif path in ("/api/panel/open", "/api/panel/close"):
            self.send_json({"success": True, "results": {}})
        else:
            self.send_json(REFUSED)

    def do_DELETE(self):
        self.send_json(REFUSED)


def create_server(port=8799):
    return ThreadingHTTPServer(("127.0.0.1", port), DemoHandler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8799, help="loopback port (default: 8799)")
    args = parser.parse_args()
    if not 0 <= args.port <= 65535 or args.port == 8765:
        parser.error("--port must be between 0 and 65535, excluding the live panel port 8765")
    with create_server(args.port) as server:
        print(f"http://127.0.0.1:{server.server_port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
