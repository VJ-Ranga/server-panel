# Server Panel Project Log

This file is the durable project memory for future work. Read it first when returning to this project after some time or when starting a new AI/chat session.

## Project Purpose

Server Management Panel is a local web control panel for managing a localhost LEMP development stack. It is built to make local WordPress and PHP-based project work easier by reducing manual Nginx, MySQL, PHP-FPM, phpMyAdmin, and project setup steps.

The panel is intended for local development, not public hosting.

Default local URL:

```text
http://127.0.0.1:8765
```

Default password:

```text
admin
```

Change the password in **Settings** after first login.

## Current Status

- Repository: `https://github.com/VJ-Ranga/server-panel.git`
- Branch: `main`
- Latest pushed commit at time of this log update: `fb1565f Add project README`
- Current app hub: **App Launcher**
- Sidebar app-specific links are intentionally hidden to keep navigation short as more app types are added.
- App-specific pages still exist in `index.html`, but are opened through App Launcher actions.
- `README.md` now exists and is the main GitHub/user guide.

## Current Feature Set

### Dashboard

- Shows CPU, memory, disk, uptime, host information, and service controls.
- Service cards control Nginx, MySQL, and PHP-FPM.

### App Launcher

- Main hub for app creation and app management entry.
- Shows compact cards for:
  - WordPress
  - Laravel
  - CodeIgniter
  - PHP Projects
- Each card shows requirements/default port range and installed count.
- App cards have `Create` and `View All` actions.
- Recent projects are shown below cards in a grouped **Recent Projects** section.
- Recent project rows show project name, port/path summary, `Open`, and `Manage`.
- App-specific management pages are hidden from the sidebar but still exist and load through App Launcher.

### WordPress

- Discovers WordPress installs in `/var/www` and `/opt`.
- Creates WordPress sites with database, user, `wp-config.php`, salts, and Nginx site.
- Supports live install/delete progress logs.
- Supports rollback on failed install.
- Supports opening frontend, WP Admin, phpMyAdmin, and project folder.
- Supports port change, DB password change, and WP admin password change.

### Laravel

- Creates Laravel apps with Composer.
- Creates database credentials.
- Configures `.env` and Nginx public webroot.
- Supports app listing, open, folder, phpMyAdmin, port change, Artisan actions, and delete.

### CodeIgniter

- Creates CodeIgniter 4 apps with Composer.
- Creates database credentials and `.env`.
- Configures Nginx public webroot.
- Supports app listing, open, folder, phpMyAdmin, port change, and delete.

### PHP Projects

- Creates panel-managed plain PHP projects.
- Templates: Blank Folder, PHP Only, PHP + DB.
- Uses `.server-panel-project.json` metadata for safer discovery/deletion.
- Supports project listing, open, folder, phpMyAdmin when DB exists, port change, and delete.

### Server Tools

- Nginx site list, enable/disable, config editor, validation, and logs.
- MySQL database list/create/drop and SQL query runner.
- phpMyAdmin install/config/Nginx helper.
- Performance tuning for selected Nginx, PHP, PHP-FPM, and MySQL settings.
- Settings page for password and MySQL credentials.

## Major Timeline

### Initial Project

- Created a pure Python local server panel with `panel.py` backend and `index.html` frontend.
- Added helper scripts for privileged operations.
- Added service controls, Nginx management, MySQL management, WordPress management, phpMyAdmin, Settings, and Performance pages.

### CodeIgniter Support

- Added CodeIgniter 4 discovery and create/delete/port management.
- Added `codeigniter-helper.sh`.
- Added backend routes and frontend tests.
- Key commit: `01fb965 Add CodeIgniter 4 app management`

### Plain PHP Projects

- Added panel-created PHP project support.
- Added templates: Blank Folder, PHP Only, PHP + DB.
- Added metadata-based discovery/deletion with `.server-panel-project.json`.
- Added `php-project-helper.sh`.
- Key commits:
  - `68f0cb4 Add plain PHP projects design`
  - `7a98def Add plain PHP project management`

### App Launcher First Version

- Added App Launcher design/spec.
- Added frontend tests.
- Added sidebar App Launcher item and cards for WordPress, Laravel, CodeIgniter, PHP Projects.
- Added `Create` and `Manage` navigation helpers that reuse existing app pages/tabs.
- Pushed to GitHub.
- Key commits:
  - `acc9662 Add app launcher design`
  - `c1a6a49 Add app launcher frontend tests`
  - `2c0fd1e Strengthen app launcher frontend tests`
  - `c7966d9 Add app launcher page`
  - `b65f692 Add app launcher page`

### App Launcher Navigation Dashboard

- Decided the sidebar should not grow as more app types are added.
- Removed WordPress/Laravel/CodeIgniter/PHP Projects from the sidebar.
- Kept hidden app-specific pages available through App Launcher.
- Added app counts and recent project summaries.
- Fixed hidden app page direct hash/saved-page behavior so App Launcher stays active.
- Added `rel="noopener noreferrer"` to new launcher open links.
- Key commits:
  - `698757d Add app launcher navigation design`
  - `b1570cf Expand app launcher dashboard design`
  - `a77780e Update app launcher navigation tests`
  - `a72fbb1 Make app launcher the app dashboard`
  - `64ce501 Document app launcher dashboard navigation`
  - `d5d848e Update hidden app frontend tests`
  - `cee7b55 Fix hidden app launcher navigation state`

### Recent Projects Layout Redesign

- User noticed recent project rows inside cards made some cards too tall and messy.
- Redesign approved: keep app cards compact and move project rows below cards.
- Added grouped **Recent Projects** section below card grid.
- Moved `launcher-*-recent` containers out of app cards.
- Updated tests and documentation.
- Key commits:
  - `87e2085 Add app launcher recent projects layout design`
  - `491d5da Update app launcher recent layout tests`
  - `06f58a7 Refine app launcher recent layout tests`
  - `3252f90 Strengthen app launcher recent group tests`
  - `7922f1e Move app launcher recent projects below cards`
  - `2f561c3 Document app launcher recent projects layout`

### README Documentation

- Added a GitHub-friendly `README.md`.
- README explains install, first-time sudo setup, start/stop, daily use, app workflows, server tools, security notes, troubleshooting, and development verification.
- Key commits:
  - `d37006e Add README documentation design`
  - `fb1565f Add project README`

## Important Files

| File | Purpose |
|---|---|
| `README.md` | Main GitHub/user guide |
| `PROJECT_LOG.md` | Durable project memory and update history |
| `CLAUDE.md` | Detailed internal project documentation and API route reference |
| `panel.py` | Python backend, HTTP server, API routes, app discovery/install/delete logic |
| `index.html` | Frontend UI, navigation, App Launcher, management pages |
| `setup-sudo.sh` | First-time sudoers setup |
| `wp-install-helper.sh` | WordPress install helper |
| `wp-delete-helper.sh` | WordPress delete helper |
| `laravel-helper.sh` | Laravel helper |
| `codeigniter-helper.sh` | CodeIgniter helper |
| `php-project-helper.sh` | PHP Projects helper |
| `perf-helper.sh` | Performance config helper |
| `tests/` | Python unittest coverage for backend/frontend structure |
| `docs/superpowers/specs/` | Approved design specs |
| `docs/superpowers/plans/` | Implementation plans used for major changes |

## How The Panel Works

- `panel.py` starts a local Python HTTP server on port `8765`.
- `index.html` is served as the frontend.
- Frontend JavaScript calls `/api/...` routes in `panel.py`.
- Long-running installs/deletes run in background jobs and are polled by the frontend.
- Privileged operations are delegated to specific helper scripts.
- `setup-sudo.sh` creates narrow sudoers rules for those helpers.
- App Launcher uses existing app list APIs to show counts and recent projects.
- App Launcher actions open hidden app-specific pages/tabs rather than duplicating full management tables.

## Current Verification Commands

Run these before claiming the project is clean:

```bash
python3 -m py_compile panel.py
python3 -m unittest discover -s tests -v
bash -n setup-sudo.sh wp-install-helper.sh wp-delete-helper.sh laravel-helper.sh codeigniter-helper.sh php-project-helper.sh perf-helper.sh start-panel.sh
python3 - <<'PY'
from pathlib import Path
html = Path('index.html').read_text()
start = html.index('<script>') + len('<script>')
end = html.rindex('</script>')
Path('/tmp/opencode/server-panel-inline.js').write_text(html[start:end])
PY
node --check "/tmp/opencode/server-panel-inline.js"
git diff --check
```

Latest full verification before README push passed:

- `python3 -m py_compile panel.py`
- `python3 -m unittest discover -s tests -v` -> 23 tests OK
- shell helper syntax check
- `git diff --check`

## Known Design Decisions

- App-specific pages are hidden from the sidebar intentionally.
- App Launcher is the single app hub.
- Future app types should be added as App Launcher cards/groups, not as sidebar links.
- Recent project rows should stay outside the top app cards.
- App Launcher should not include destructive actions such as delete.
- Full management tables and destructive controls stay on app-specific management pages.
- Backend routes should not be duplicated for App Launcher if existing app APIs already provide the needed data.

## Useful Next Steps

- Add screenshots to `README.md` after the UI feels stable.
- Add SSL certificate management.
- Add file manager for webroot.
- Add cron job manager.
- Add PHP version switcher.
- Add Nginx live log tail.
- Add browser/DOM-level tests if the frontend grows more interactive.

## Notes For Future Sessions

- Start by reading `PROJECT_LOG.md`, then `README.md`, then `CLAUDE.md` for deep details.
- Before changing App Launcher behavior, check tests in `tests/test_app_launcher_frontend.py`.
- Before changing app creation/deletion behavior, check the related helper script and sudoers expectations.
- Do not expose this panel publicly without adding stronger security controls.
- Keep documentation updated when major workflow or UI behavior changes.
