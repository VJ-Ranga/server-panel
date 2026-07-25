# Server Management Panel

A web-based local server management panel built with pure Python (no external dependencies).
Manages Nginx, MySQL, WordPress, and phpMyAdmin on a local LEMP stack.

## Quick Start

```bash
cd ~/Documents/server-panel
python3 panel.py
```

Open: **http://127.0.0.1:8765**
Password: **admin** (change in Settings page)

To stop:
```bash
kill $(lsof -ti:8765)
```

## First Time Setup (run once)

```bash
sudo bash ~/Documents/server-panel/setup-sudo.sh vjranga
```

This creates `/etc/sudoers.d/server-panel` so the panel can control services, edit nginx configs, and manage WordPress files without a password prompt every time.

## Files

| File | Purpose |
|---|---|
| `panel.py` | Python backend — HTTP server, all API routes |
| `index.html` | Frontend — Bootstrap 5 dark theme, vanilla JS |
| `panel_config.json` | Panel password hash + MySQL credentials (auto-created) |
| `setup-sudo.sh` | Run once with sudo to grant passwordless sudo rules |
| `wp-install-helper.sh` | Sudo helper — copies WP files, sets permissions, creates nginx site |
| `wp-delete-helper.sh` | Sudo helper — removes WP files and nginx site |
| `perf-helper.sh` | Sudo helper — saves tuned Nginx/PHP-FPM/MySQL config files and restarts services |
| `start-panel.sh` | Desktop launcher helper — starts the panel and opens the browser |
| `panel-icon.svg` | Desktop launcher icon |

## Features

### Dashboard
- Live CPU, RAM, disk, uptime stats (polls every 7 seconds)
- Nginx, MySQL, PHP-FPM service cards with Start / Stop / Restart buttons

### Nginx
- List all virtual hosts with enabled/disabled status
- Enable / disable sites with one click
- Edit individual site configs and nginx.conf in browser
- Test config before saving (auto-backup to .bak)
- View error log and access log (last 200 lines)

### MySQL
- List all databases
- Create / drop databases
- SQL query runner with database selector
- Connects via `sudo mysql` fallback for auth_socket root

### WordPress
- Auto-discovers all WP installs in `/var/www` and `/opt`
- **Install New Site** wizard:
  - Downloads latest WordPress
  - Creates database + user with mysql_native_password
  - Generates wp-config.php with unique salts
  - Creates and enables nginx site on chosen port
  - Live progress log in browser
  - Full rollback on failure (removes files, DB, user, nginx site)
- **Delete Site** with live progress log:
  - Drops database (skips if db_user is `root`)
  - Drops MySQL user
  - Removes nginx site config
  - Deletes install directory
- Installed Sites dashboard:
  - Shows detected Nginx site and port for each WordPress install
  - Opens frontend, WP Admin, and phpMyAdmin for the selected site
  - Changes the Nginx listen port safely via helper script + `nginx -t`
  - Reads DB credentials from `wp-config.php` for phpMyAdmin quick access
  - Changes DB user password and updates `wp-config.php`
  - Changes WP admin password for user ID 1 via WP-CLI or PHP fallback

### phpMyAdmin
- Install via apt with one click (live log)
- Auto-generates nginx site config (default port 8081)
- Edit config.inc.php in browser
- Generate secure blowfish secret
- PHP-FPM start / stop / restart

### Settings
- Change panel password
- Set MySQL credentials (saved to panel_config.json)

### Performance
- Read/tune selected Nginx, PHP, PHP-FPM, and MySQL settings
- Save through `perf-helper.sh` with backups and service reload/restart

## System Info

| Item | Value |
|---|---|
| PHP version | 8.3 |
| PHP-FPM socket | `/run/php/php8.3-fpm.sock` |
| MySQL auth | root uses `auth_socket` (no password) |
| phpMyAdmin login | user `admin` with mysql_native_password |
| phpMyAdmin URL | http://localhost:8081 |
| WordPress sites | `/opt/wp` (nginx site: `wordpress`), `/opt/leopardtrails_wp_build/leopard-trails` |
| Nginx WP config | root `/opt`, serves `/wp` as subpath on port 80 |

## Architecture

- **Backend**: Python `ThreadingHTTPServer` — handles GET, POST, DELETE
- **Auth**: SHA-256 hashed password, bearer token stored in localStorage (24hr expiry)
- **Long-running tasks**: WordPress install and delete run in background threads, frontend polls every 0.8–1.5s for live progress
- **Sudo**: All privileged operations go through helper shell scripts with specific sudoers rules — no broad `ALL` access

## API Routes

| Method | Path | Description |
|---|---|---|
| POST | `/api/login` | Authenticate, get token |
| GET | `/api/status` | Nginx/MySQL status + system info |
| POST | `/api/services/<svc>/<action>` | Control service (start/stop/restart/reload) |
| GET | `/api/nginx/sites` | List virtual hosts |
| GET/POST | `/api/nginx/site/<name>` | Read or save a site config |
| GET/POST | `/api/nginx/config` | Read or save nginx.conf |
| GET | `/api/nginx/logs/error` | Last 200 lines of error log |
| GET | `/api/nginx/logs/access` | Last 200 lines of access log |
| POST | `/api/nginx/validate` | Test nginx config |
| GET | `/api/mysql/databases` | List databases |
| POST | `/api/mysql/databases` | Create database |
| DELETE | `/api/mysql/databases/<name>` | Drop database |
| POST | `/api/mysql/query` | Run SQL query |
| GET | `/api/wordpress/sites` | List WP installations |
| GET | `/api/wordpress/next_port` | Find next available suggested WP port |
| GET | `/api/wordpress/credentials?path=<path>` | Read DB credentials from a site's wp-config.php |
| POST | `/api/wordpress/install` | Start install job → returns job_id |
| GET | `/api/wordpress/install/<job_id>` | Poll install progress |
| POST | `/api/wordpress/port` | Change a WP Nginx site listen port |
| POST | `/api/wordpress/change_db_password` | Change site DB user password and update wp-config.php |
| POST | `/api/wordpress/change_wp_admin` | Change WP admin password for user ID 1 |
| DELETE | `/api/wordpress/sites` | Start delete job → returns job_id |
| GET | `/api/wordpress/delete/<job_id>` | Poll delete progress |
| GET | `/api/performance` | Read Nginx/PHP/FPM/MySQL performance settings |
| POST | `/api/performance/nginx` | Save selected Nginx performance settings |
| POST | `/api/performance/php` | Save selected PHP settings |
| POST | `/api/performance/fpm` | Save selected PHP-FPM pool settings |
| POST | `/api/performance/mysql` | Save selected MySQL settings |
| GET | `/api/phpmyadmin/status` | phpMyAdmin install/nginx/fpm status |
| GET/POST | `/api/phpmyadmin/config` | Read or save config.inc.php |
| GET/POST | `/api/phpmyadmin/nginx` | Read, generate, save, enable/disable nginx site |
| POST | `/api/phpmyadmin/install` | apt install phpMyAdmin |
| POST | `/api/phpmyadmin/blowfish` | Generate random blowfish secret |
| POST | `/api/settings` | Update password or MySQL credentials |

## Known Bugs Fixed

- **MySQL auth_socket**: `mysql_cmd` tries 3 fallbacks — `mysql -uroot`, `sudo mysql -uroot`, `sudo mysql` (socket auth). The last one works because sudo runs as root.
- **WP delete was silent**: `do_DELETE` called `read_body()` twice — second call got empty body so all params were empty strings. Fixed by removing the duplicate call.
- **Nginx site name mismatch on delete**: WP at `/opt/wp` has nginx site named `wordpress` not `wp`. Fixed with `find_nginx_site_for_path()` that scans nginx root directives to find the correct config file.
- **sudo password prompts**: `setup-sudo.sh` was not run + mysql rule was missing `*` for arguments. Fixed both.
- **Browser blocking confirm/prompt dialogs**: Replaced native `confirm()`/`prompt()` with custom Bootstrap modal for delete confirmation.
- **WP config permission denied**: New installs set `wp-config.php` to `www-data:<panel-user>` with `640`, so PHP and the panel can read it while keeping it private.
- **WP port mismatch**: WordPress site discovery now matches the longest valid Nginx `root` path and ignores backup site files, avoiding `/var/www/test2` matching `/var/www/test`.

## Possible Future Features

- SSL certificate management (Let's Encrypt / self-signed)
- File manager for webroot
- Cron job manager
- PHP version switcher
- Nginx log live tail (WebSocket)
- Multiple server support
