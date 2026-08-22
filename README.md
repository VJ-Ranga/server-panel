# Server Management Panel

A local web panel for managing a localhost LEMP development environment. It is built with pure Python and vanilla HTML/JavaScript, with no external Python dependencies.

The panel is designed to make local WordPress and PHP-based project management easier: create apps, manage ports, open folders, manage databases, edit Nginx configs, and control local services from one browser UI.

## What It Manages

- Local service status for Nginx, MySQL, and PHP-FPM.
- Nginx virtual hosts and logs.
- MySQL databases and SQL queries.
- WordPress sites.
- Laravel apps.
- CodeIgniter 4 apps.
- Plain PHP projects.
- phpMyAdmin installation and config.
- Basic Nginx/PHP-FPM/MySQL performance settings.

## Requirements

This project is intended for a local Linux/Ubuntu-style LEMP stack.

- Python 3.
- Nginx.
- MySQL or MariaDB.
- PHP-FPM.
- PHP 8.3 in the current default configuration.
- Composer for Laravel and CodeIgniter project creation.
- `sudo` access for first-time setup.

## Installation

Clone the repository or place it in your projects folder:

```bash
cd ~/Documents
git clone https://github.com/VJ-Ranga/server-panel.git
cd server-panel
```

If you already have the files locally, open the project folder:

```bash
cd ~/Documents/server-panel
```

## First-Time Sudo Setup

Run this once:

```bash
sudo bash ~/Documents/server-panel/setup-sudo.sh vjranga
```

This creates `/etc/sudoers.d/server-panel` with narrow passwordless sudo rules so the panel can safely perform required local server tasks without asking for your password every time.

The sudo helper scripts are specific to this panel. They handle privileged operations such as restarting services, writing Nginx configs, creating webroot files, setting permissions, and saving performance config backups.

## Start The Panel

```bash
cd ~/Documents/server-panel
python3 panel.py
```

Open:

```text
http://127.0.0.1:8765
```

Default login password:

```text
admin
```

Change the password from **Settings** after first login.

## Stop The Panel

```bash
kill $(lsof -ti:8765)
```

## Daily Usage

Use **App Launcher** as the main hub for application projects.

The sidebar stays short. App-specific pages are opened from App Launcher actions:

- **Create** opens the install form for that app type.
- **View All** opens the hidden management page for that app type.
- **Manage** from Recent Projects opens the matching app management page.
- **Open** opens the detected local project URL when a port is available.

App Launcher shows compact app cards with installed counts, then a grouped **Recent Projects** section below the cards.

## App Workflows

### WordPress

WordPress support can:

- Auto-detect installs in `/var/www` and `/opt`.
- Create a new WordPress site.
- Download WordPress.
- Create a database and database user.
- Generate `wp-config.php` with salts.
- Create and enable an Nginx site on a chosen port.
- Show a live install log.
- Roll back files, database, user, and Nginx site on failed install.
- Open frontend, WP Admin, phpMyAdmin, and the project folder.
- Change Nginx listen port.
- Change database user password and update `wp-config.php`.
- Change WordPress admin password for user ID 1.
- Delete a site with a live progress log.
- Update WordPress core for selected local sites without changing plugins, themes, `wp-content`, or `wp-config.php`.
- Reuse one cached official archive across updates, refreshing it only when WordPress releases a newer version.

### Laravel

Laravel support can:

- Create a Laravel app with Composer.
- Create database credentials.
- Write environment configuration.
- Configure Nginx with `public/` as the webroot.
- Open the app, folder, and phpMyAdmin.
- Change the Nginx listen port.
- Run common Artisan actions such as migrate, cache clear, and storage link.
- Delete the app files, database, database user, and Nginx site.

Composer must be installed before creating Laravel apps.

### CodeIgniter

CodeIgniter support can:

- Auto-detect CodeIgniter 4 apps by scanning for `spark`.
- Create a CodeIgniter 4 app with Composer.
- Create database credentials.
- Write `.env` settings.
- Configure Nginx with `public/` as the webroot.
- Open the app, folder, and phpMyAdmin.
- Change the Nginx listen port.
- Delete the app files, database, database user, and Nginx site.

Composer must be installed before creating CodeIgniter apps.

### PHP Projects

PHP Projects support can create and manage panel-created plain PHP projects.

Templates:

- Blank Folder.
- PHP Only.
- PHP + DB.

PHP + DB projects create a MySQL database and database user. Panel-created PHP projects include `.server-panel-project.json` metadata so discovery and deletion stay safer.

## Server Tools

### Dashboard

The dashboard shows CPU, memory, disk, uptime, and service cards for Nginx, MySQL, and PHP-FPM.

### Nginx

The Nginx page can list virtual hosts, enable or disable sites, edit site configs, edit `nginx.conf`, validate config, and view access/error logs.

### MySQL

The MySQL page can list databases, create/drop databases, and run SQL queries. It supports local root socket auth by falling back to `sudo mysql` when needed.

### phpMyAdmin

The phpMyAdmin page can install phpMyAdmin through apt, generate an Nginx config, edit `config.inc.php`, generate a blowfish secret, and manage PHP-FPM.

Default phpMyAdmin URL:

```text
http://localhost:8081
```

### Performance

The Performance page can read and save selected Nginx, PHP, PHP-FPM, and MySQL tuning settings through `perf-helper.sh`. Backups are created before config changes.

## Important Files

| File | Purpose |
|---|---|
| `panel.py` | Python backend, HTTP server, and API routes |
| `index.html` | Frontend UI built with Bootstrap 5 and vanilla JavaScript |
| `panel_config.json` | Auto-created config for password hash and MySQL credentials |
| `setup-sudo.sh` | First-time sudoers setup |
| `wp-install-helper.sh` | WordPress install helper |
| `wp-delete-helper.sh` | WordPress delete helper |
| `laravel-helper.sh` | Laravel create/delete/port helper |
| `codeigniter-helper.sh` | CodeIgniter create/delete/port helper |
| `php-project-helper.sh` | Plain PHP project create/delete/port helper |
| `perf-helper.sh` | Performance config helper |
| `start-panel.sh` | Desktop launcher helper |
| `panel-icon.svg` | Desktop launcher icon |

## Security Notes

- This is a local development tool.
- Do not expose it to the public internet.
- Keep it bound to localhost unless you know exactly what you are doing.
- Change the default `admin` password in Settings.
- `panel_config.json` can contain sensitive local credentials. Do not commit it.
- The helper scripts are designed to avoid broad sudo access. Review `setup-sudo.sh` before running it on a new machine.

## Troubleshooting

### Panel Port Already In Use

If port `8765` is already used, stop the old panel process:

```bash
kill $(lsof -ti:8765)
```

Then start again:

```bash
python3 panel.py
```

### Nginx Config Save Fails

Use the Nginx validation action before saving. If `nginx -t` fails, fix the config error shown in the panel before reloading Nginx.

### MySQL Root Login Fails

Many local MySQL installs use `auth_socket` for root. The panel tries normal root login first, then falls back to `sudo mysql` for socket auth.

Make sure the first-time sudo setup has been run.

### Laravel Or CodeIgniter Creation Fails

Install Composer first:

```bash
composer --version
```

If Composer is missing, install it and retry the app creation.

### phpMyAdmin Does Not Open

Check the phpMyAdmin page in the panel:

- Confirm phpMyAdmin is installed.
- Confirm the Nginx site is generated and enabled.
- Confirm PHP-FPM is running.
- Open `http://localhost:8081`.

### Project URL Does Not Open

Check that Nginx is running and that the project port is not already used by another service. Use the app management page to change the port if needed.

## Development And Verification

Run backend syntax check:

```bash
python3 -m py_compile panel.py
```

Run tests:

```bash
python3 -m unittest discover -s tests -v
```

Check helper shell syntax:

```bash
bash -n setup-sudo.sh wp-install-helper.sh wp-delete-helper.sh laravel-helper.sh codeigniter-helper.sh php-project-helper.sh perf-helper.sh start-panel.sh
```

Check inline frontend JavaScript syntax:

```bash
python3 - <<'PY'
from pathlib import Path
html = Path('index.html').read_text()
start = html.index('<script>') + len('<script>')
end = html.rindex('</script>')
Path('/tmp/opencode/server-panel-inline.js').write_text(html[start:end])
PY
node --check "/tmp/opencode/server-panel-inline.js"
```
