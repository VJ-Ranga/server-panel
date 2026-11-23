# CloudyCode Server Panel

A local LEMP development panel with a standard-library Python backend and a browser UI.

## Quick Start

From the repository directory, run:

```bash
python3 panel.py
```

Open **http://127.0.0.1:8765** and sign in with your configured panel credentials. The default username and password are both `admin`. Change both in Settings. Press Ctrl+C to stop a foreground panel.

Use `python3 scripts/demo_server.py` to preview the same UI on `127.0.0.1:8799` with fake data and disabled mutations. Use `./scripts/make_screenshots.sh` for documentation captures. Work against the demo when real services should remain untouched.

## First Time Setup (run once)

Run `./install.sh` as your regular user. It checks dependencies, configures the panel login and default project location, and offers sudo setup, MCP access, a desktop launcher and desktop autostart. Use `--yes` to accept the defaults.

The installer calls `python3 panel.py --set-login`, which reads the username and password from stdin on separate lines and exits. A blank line selects `admin`. A login change invalidates existing sessions. For manual sudo setup, run this command from the repository directory:

```bash
sudo bash setup-sudo.sh "$USER" "$PWD"
```

This writes `/etc/sudoers.d/server-panel` with rules for project helpers and specific service, Nginx, database and phpMyAdmin commands. Use the panel on loopback only.

## Files

| File | Purpose |
|---|---|
| `panel.py` | Python backend — HTTP server, all API routes |
| `index.html` | Frontend — Bootstrap 5 and vanilla JS with CloudyCode light and dark themes |
| `panel_config.json` | Git-ignored login, sessions and credentials (auto-created) |
| `projects.json` | Git-ignored project and links registry (auto-created) |
| `assets/` | Locally served CloudyCode brand artwork and Plus Jakarta Sans font |
| `install.sh` | Installer and desktop integration |
| `setup-sudo.sh` | Run once with sudo to grant passwordless sudo rules |
| `wp-install-helper.sh` | Sudo helper — copies WP files, sets permissions, creates nginx site |
| `wp-delete-helper.sh` | Sudo helper — removes WP files and nginx site |
| `laravel-helper.sh` | Sudo helper — copies Laravel files, sets permissions, creates nginx site |
| `codeigniter-helper.sh` | Sudo helper — copies CodeIgniter files, sets permissions, creates nginx site |
| `php-project-helper.sh` | Sudo helper — copies plain PHP files, sets permissions, creates nginx site |
| `perf-helper.sh` | Sudo helper — saves tuned Nginx/PHP-FPM/MySQL config files and restarts services |
| `start-panel.sh` | Desktop launcher helper — starts the panel and opens the browser |
| `panel-icon.svg` | Desktop launcher icon |
| `wp-auto-login-plugin.php` | Source for the optional per-site WordPress auto-login plugin |
| `wp-plugin-library/` | Local plugin ZIP library for the WordPress install wizard |
| `scripts/mcp-setup.sh` | Enable or revoke an MCP key and manage AI client registrations |
| `mcp/server_panel_mcp.py` | Standard-library MCP bridge. See [client setup](mcp/README.md) |
| `scripts/demo_server.py` | Standalone read-only demo using fixed fake data |
| `scripts/make_screenshots.sh` | Generates demo screenshots with headless Chrome |
| `tests/` | Regression tests. Run `python3 -m pytest -q` |

## Features

### Dashboard
- Live CPU, RAM, disk, uptime stats (polls every 7 seconds)
- Nginx, MySQL, PHP-FPM service cards with Start / Stop / Restart buttons

### App Launcher
- Single app hub for WordPress, Laravel, CodeIgniter, and PHP Projects
- Keeps app-specific pages out of the sidebar so future app types do not make navigation longer
- Shows compact app cards with requirements, default port range, and installed counts
- Shows up to three recent projects per app type in a grouped Recent Projects section below the cards
- Create opens existing install forms; View All/Manage opens existing hidden app-specific management pages
- Full app lists, deletes, port changes, and advanced controls stay on the app-specific pages

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
- Discovers WordPress installs in supported paths under `/var/www`, `/opt` and `~/local`
- **Install New Site** wizard:
  - Downloads latest WordPress
  - Creates database + user with mysql_native_password
  - Generates wp-config.php with unique salts
  - Creates and enables nginx site on chosen port
  - Live progress log in browser
  - Attempts rollback of newly created resources on failure (removes files, DB, user, nginx site)
- **Delete Site** with live progress log:
  - Drops the database and removes non-root MySQL users
  - Removes nginx site config
  - Deletes install directory
- Installed Sites dashboard:
  - Shows detected Nginx site and port for each WordPress install
  - Opens frontend, WP Admin, and phpMyAdmin for the selected site
  - Optional normal-plugin auto-login uses one-use native WordPress auth tokens
  - Auto-login plugin can be enabled, disabled, or removed per site; remove it before backups
  - Changes the Nginx listen port safely via helper script + `nginx -t`
  - Reads DB credentials from `wp-config.php` for phpMyAdmin quick access
  - Changes DB user password and updates `wp-config.php`
  - Changes the selected WordPress admin password via WP-CLI or PHP fallback
- **Core Update** with shared cache:
  - Checks the installed core version of each local site against the latest version in a shared cached official archive
  - Reuses one cached archive across sites, refreshing it only when WordPress releases a newer version
  - Updates only core files, leaving plugins, themes, `wp-content`, and `wp-config.php` untouched
  - Uses maintenance mode per site during the update and always removes it
  - Skips already-current sites and continues after per-site errors

### Laravel
- Discovers apps by their `artisan` file in supported web roots
- The install wizard uses Composer, provisions MySQL and Nginx, and attempts rollback on failure
- Installed apps support port changes, deletion and a fixed set of Artisan and Composer actions

### CodeIgniter
- Auto-discovers CodeIgniter 4 apps by scanning for `spark` in `/var/www`, `/opt`, and `/opt/*/*`
- **Create New App** wizard:
  - Creates a CodeIgniter 4 app with Composer (`codeigniter4/appstarter`)
  - Creates database + user with mysql_native_password
  - Writes `.env` with app URL and database settings
  - Creates and enables nginx site on chosen port with `public/` as webroot
  - Live progress log in browser
  - Attempts rollback of newly created resources on failure (removes files, DB, user, nginx site)
- Installed Apps dashboard:
  - Opens frontend, app folder, and phpMyAdmin for the selected app
  - Shows detected Nginx site and port
  - Changes the Nginx listen port safely via helper script + `nginx -t`
  - Deletes app files, database, database user, and Nginx site

### PHP Projects
- Creates and manages panel-created plain PHP projects
- **Create New Project** wizard:
  - Template choices: Blank Folder, PHP Only, PHP + DB
  - Creates optional MySQL database + user only for PHP + DB projects
  - Generates starter `index.php` and `config.php` when selected
  - Creates `.server-panel-project.json` metadata for safe discovery/deletion
  - Creates and enables nginx site on chosen port
  - Live progress log in browser
  - Attempts rollback of newly created resources on failure
- Installed Projects dashboard:
  - Lists only panel-created PHP projects with metadata
  - Opens frontend, app folder, and phpMyAdmin when a DB exists
  - Changes the Nginx listen port safely via helper script + `nginx -t`
  - Deletes files, Nginx site, and DB resources only when metadata confirms panel ownership

### phpMyAdmin
- Install via apt with one click (live log)
- Auto-generates nginx site config (default port 8081)
- Edit config.inc.php in browser
- Generate secure blowfish secret
- PHP-FPM start / stop / restart

### Settings
- Change the panel username or password. Username changes require the current password
- Set MySQL credentials (saved to panel_config.json)
- Choose the default for the WordPress install form from `~/local`, `/var/www` and `/opt`. The install form can select a different location.

### Performance
- Read/tune selected Nginx, PHP, PHP-FPM, and MySQL settings
- Save through `perf-helper.sh` with backups and service reload/restart

### Projects
- Stores projects and their parts (local site, Git repository, live/staging sites, hosting dashboard, vault path, notes)
- Supports multi-part projects (e.g. WordPress backend and Astro frontend)
- Real-time `local_running` status check via concurrent loopback TCP connect with 0.3-second timeout
- Read-only tools exposed via MCP (`list_projects`, `get_project`)
- Stored in Git-ignored `projects.json` with mode `0600` under atomic replacement and file locking

### MCP
- The stdio bridge connects Claude Code, Codex and OpenCode to the localhost API
- Run `scripts/mcp-setup.sh on`, `scripts/mcp-setup.sh off` or `scripts/mcp-setup.sh status` to manage key-based access. `panel_config.json` stores the key privately with mode `0600`, and revocation takes effect on the next request.
- Existing clients can continue using `SERVER_PANEL_PASSWORD`. MCP keys cannot update settings or call the panel open and close endpoints.
- See [MCP setup and tool documentation](mcp/README.md)

## Architecture

- **Backend** uses Python `ThreadingHTTPServer` bound to `127.0.0.1:8765`. The UI is served at `/` and `/index.html`. The `/assets/<path>` route restricts reads to supported files inside the assets directory.
- **Authentication** checks the username and SHA-256 password hash. The browser stores the bearer token in localStorage. Tokens expire after 24 hours.
- **Background jobs** handle installs, deletions and WordPress core updates. The frontend polls the associated job route for progress.
- **Service lifecycle** uses the panel open and close endpoints to start and stop stack services.
- **Sudo** uses the rules in `/etc/sudoers.d/server-panel` for helper scripts and direct commands.
- **Frontend** uses CloudyCode paper and graphite surfaces, pen-blue accents, and a local Plus Jakarta Sans font. The theme preference is stored as `panel_theme` in localStorage.
- **Demo** serves the UI with a fixed demo token and fake API payloads. It runs independently of the real panel and does not run system commands.

## API Routes

API requests use a bearer token except login and panel close. Login issues the token, and panel close validates the token supplied in its JSON body. The handler also responds to OPTIONS.

| Method | Path | Description |
| --- | --- | --- |
| GET | `/api/codeigniter/apps` | List CodeIgniter 4 apps |
| DELETE | `/api/codeigniter/apps` | Start CodeIgniter delete job |
| GET | `/api/codeigniter/delete/<job_id>` | Poll CodeIgniter delete progress |
| POST | `/api/codeigniter/install` | Start CodeIgniter 4 install job |
| GET | `/api/codeigniter/install/<job_id>` | Poll CodeIgniter install progress |
| GET | `/api/codeigniter/next_port` | Find next available suggested CodeIgniter port |
| POST | `/api/codeigniter/port` | Change a CodeIgniter Nginx site listen port |
| GET | `/api/laravel/apps` | List Laravel apps |
| DELETE | `/api/laravel/apps` | Start a Laravel delete job |
| POST | `/api/laravel/artisan` | Run a supported Artisan or Composer action |
| GET | `/api/laravel/delete/<job_id>` | Poll Laravel delete progress |
| POST | `/api/laravel/install` | Start a Laravel install job |
| GET | `/api/laravel/install/<job_id>` | Poll Laravel install progress |
| GET | `/api/laravel/next_port` | Suggest a Laravel port |
| POST | `/api/laravel/port` | Change a Laravel site's Nginx listen port |
| POST | `/api/login` | Authenticate with username and password and return a bearer token |
| GET | `/api/mysql/databases` | List databases |
| POST | `/api/mysql/databases` | Create database |
| DELETE | `/api/mysql/databases/<name>` | Drop database |
| POST | `/api/mysql/query` | Run SQL query |
| GET | `/api/nginx/config` | Read nginx.conf |
| POST | `/api/nginx/config` | Validate and save nginx.conf |
| GET | `/api/nginx/logs/access` | Last 200 lines of access log |
| GET | `/api/nginx/logs/error` | Last 200 lines of error log |
| GET | `/api/nginx/site/<name>` | Read a site config |
| POST | `/api/nginx/site/<name>` | Save, enable or disable a site |
| GET | `/api/nginx/sites` | List virtual hosts |
| POST | `/api/nginx/validate` | Test nginx config |
| POST | `/api/open_folder` | Open a directory in the desktop file manager |
| POST | `/api/panel/close` | Stop stack services using the token in the request body |
| POST | `/api/panel/open` | Start stack services |
| GET | `/api/performance` | Read Nginx/PHP/FPM/MySQL performance settings |
| POST | `/api/performance/fpm` | Save selected PHP-FPM pool settings |
| POST | `/api/performance/mysql` | Save selected MySQL settings |
| POST | `/api/performance/nginx` | Save selected Nginx performance settings |
| POST | `/api/performance/php` | Save selected PHP settings |
| GET | `/api/php-projects/apps` | List panel-created PHP projects |
| DELETE | `/api/php-projects/apps` | Start PHP project delete job |
| GET | `/api/php-projects/delete/<job_id>` | Poll PHP project delete progress |
| POST | `/api/php-projects/install` | Start plain PHP project install job |
| GET | `/api/php-projects/install/<job_id>` | Poll PHP project install progress |
| GET | `/api/php-projects/next_port` | Find next available suggested PHP project port |
| POST | `/api/php-projects/port` | Change a PHP project Nginx site listen port |
| POST | `/api/phpmyadmin/blowfish` | Generate random blowfish secret |
| GET | `/api/phpmyadmin/config` | Read config.inc.php |
| POST | `/api/phpmyadmin/config` | Save config.inc.php |
| POST | `/api/phpmyadmin/install` | apt install phpMyAdmin |
| GET | `/api/phpmyadmin/nginx` | Read the saved configuration or a generated template |
| POST | `/api/phpmyadmin/nginx` | Generate, save, enable or disable the site configuration |
| GET | `/api/phpmyadmin/status` | phpMyAdmin install/nginx/fpm status |
| GET | `/api/projects` | List registered projects with computed local running status |
| POST | `/api/projects` | Create a project |
| POST | `/api/projects/<id>` | Replace editable fields of an existing project |
| DELETE | `/api/projects/<id>` | Delete a project |
| POST | `/api/services/<svc>/<action>` | Control service (start/stop/restart/reload) |
| GET | `/api/settings` | Return `username`, `home_dir` and `default_install_location` |
| POST | `/api/settings` | Update username with `new_username` and `current_password`, update password with `new_password`, update MySQL credentials, or save `default_install_location`. Requires a session token |
| GET | `/api/status` | Nginx/MySQL status + system info |
| GET | `/api/system/info` | Return system metrics and hostname |
| POST | `/api/wordpress/auto-login` | Install, enable, disable, or remove per-site auto-login plugin |
| POST | `/api/wordpress/auto-login/token` | Create one-use native WordPress admin login URL |
| POST | `/api/wordpress/change_db_password` | Change site DB user password and update wp-config.php |
| POST | `/api/wordpress/change_wp_admin` | Change the selected WordPress admin password |
| POST | `/api/wordpress/core-update` | Start bulk core update job → returns job_id |
| GET | `/api/wordpress/core-update-status` | Latest known WP version + shared cache state |
| GET | `/api/wordpress/core-update/<job_id>` | Poll a core update or cache refresh job |
| POST | `/api/wordpress/core-update/refresh` | Start a shared core archive refresh job |
| GET | `/api/wordpress/credentials?path=<path>` | Read DB credentials from a site's wp-config.php |
| GET | `/api/wordpress/delete/<job_id>` | Poll delete progress |
| POST | `/api/wordpress/install` | Start install job → returns job_id |
| GET | `/api/wordpress/install/<job_id>` | Poll install progress |
| GET | `/api/wordpress/next_port` | Find next available suggested WP port |
| GET | `/api/wordpress/plugins` | List plugin ZIPs and validation errors |
| POST | `/api/wordpress/port` | Change a WP Nginx site listen port |
| GET | `/api/wordpress/sites` | List WP installations |
| DELETE | `/api/wordpress/sites` | Start delete job → returns job_id |

## Known Bugs Fixed

- **MySQL auth_socket**: `mysql_cmd` tries 3 fallbacks — `mysql -uroot`, `sudo mysql -uroot`, `sudo mysql` (socket auth). The last one works because sudo runs as root.
- **WP delete was silent**: `do_DELETE` called `read_body()` twice — second call got empty body so all params were empty strings. Fixed by removing the duplicate call.
- **Nginx site name mismatch on delete**: A site's Nginx config name can differ from its directory name. `find_nginx_site_for_path()` scans Nginx root directives to find the matching config.
- **sudo password prompts**: `setup-sudo.sh` was not run + mysql rule was missing `*` for arguments. Fixed both.
- **Browser blocking confirm/prompt dialogs**: Replaced native `confirm()`/`prompt()` with custom Bootstrap modal for delete confirmation.
- **WP config permission denied**: New installs set `wp-config.php` to `www-data:<panel-user>` with `640`, so PHP and the panel can read it while keeping it private.
- **WP port mismatch**: WordPress site discovery now matches the longest valid Nginx `root` path and ignores backup site files, so sibling directories with a shared name prefix are matched correctly.

## Possible Future Features

- SSL certificate management (Let's Encrypt / self-signed)
- File manager for webroot
- Cron job manager
- PHP version switcher
- Nginx log live tail (WebSocket)
- Multiple server support
