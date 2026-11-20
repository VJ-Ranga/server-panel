# Server Panel — Productize Plan (2026-11-20)

Goal: polish the working panel into a proper, publishable CloudyCode localhost tool. Polish, not rewrite.

## Hard rule

Do not touch the running WordPress / PHP projects (site files, their Nginx site configs, their databases).
WordPress / Laravel / CodeIgniter / PHP project features in the panel must keep working exactly as today.
Anything that could affect a running site waits for the end and needs VJ's OK first.

## Who does what

- Reading / mapping: Claude Haiku subagents.
- Fixes: Codex and Command Code (cheapest tier first). Claude reviews every diff and runs the tests.
- Test baseline (2026-11-20): `python3 -m pytest -q` → 96 passed.

## Phase 0 — Small safe fixes (done, commit f184d75)

- [x] `.gitignore`: `.playwright-mcp/`, `.pytest_cache/`, `.remember/`, `.superpowers/`
- [x] Remove unneeded CORS `*` header from `do_OPTIONS` (frontend is same-origin)
- [x] `read_body()`: bad JSON returns `{}` instead of crashing the request thread
- [x] Delete leftover `/tmp/_panel_*` files that hold passwords after use (change DB password, change WP admin, install password)
- [x] Remove hardcoded username from UI help text (sudo command shows `$USER`)

## Phase 1 — Cleanup (needs one decision)

One-click WordPress login exists twice:
- A (older): panel stores WP admin password in `panel_config.json`, opens a popup and auto-submits the WP login form (`submitWpLogin`, index.html ~2145).
- B (newer): `wp-auto-login-plugin.php` + one-use 60s token (`/api/wordpress/auto-login/token`).

Decided (2026-11-20): keep B, remove A's popup form submit. Keep the saved-credentials store only if the "change WP admin password" screen still needs it.

Also: remove dead code found while doing this; keep console job logs.

Done (2026-11-20): A was already unwired — the "WP Admin Auto Login" button already used B. Removed the dead `wordpressLoginUrl()` / `submitWpLogin()` and the unused `password` field in `wpLoginCreds`. The "Saved WP Admin Login" box (shows saved password + Copy) is a separate feature and stays.

## Phase 2 — CloudyCode design system + redesign

Source: `~/Documents/cc/cloudycode-redesign/brand/brand-guide.md` + `public/assets/css/site.css`.

- Colour: paper `#F4F1EA`, sheet `#FAF8F3`, field `#FFFEFB`, graphite `#23252B` / `#50525A` / `#5F6068`, rules `rgba(35,37,43,.16/.42)`, one accent pen-blue `#2A4FD0` (hover `#1E3BA6`, focus wash `rgba(42,79,208,.16)`), error `#B3261E`.
- Brand does not define success / warning or dark mode — a dashboard needs them. Muted green + amber status colours.
- Decided (2026-11-20): paper light theme by default + graphite dark theme via toggle, following the system setting.
- Type: Plus Jakarta Sans (self-hosted woff2, 400/700/800), mono for logs. No handwriting font in the UI except maybe the empty states.
- Buttons: one system — primary (blue fill), secondary (blue outline 1.5px), ghost, danger. Pill radius for buttons, 6px inputs, 3px cards, hard "paper-cut" shadows, no gradients, no emoji.
- Spacing: 8px base.
- Logo: CloudyCode mark in the sidebar (graphite on light, white on dark).
- Keep Bootstrap 5 grid/JS (modals, collapse) but restyle; swap Bootstrap Icons only if needed.
- Needs a small backend route to serve `/assets/*` (fonts, logo) — panel only.
- Same page ids and JS function names so all features keep working; frontend tests updated only where they check old colours/markup.

Done (2026-11-20, not yet committed): new token-based style block, 224 inline colours mapped to tokens, `/assets/` route (`resolve_asset`, traversal-safe, tested), logo + self-hosted font, light/dark toggle (follows system until chosen), mobile slide-out sidebar, tables scroll on small screens. Checked all 11 pages in light, dark and 375px on a read-only preview copy. Running panel needs a restart to serve `/assets/`.

## Phase 3 — Installer

`install.sh` for other laptops:
- Checks python3 (required) and reports nginx / mysql / php-fpm / phpMyAdmin status.
- Asks admin username (Enter = `admin`) and password (Enter = `admin`), writes `panel_config.json` (mode 600).
- Runs `setup-sudo.sh` with the real install path (today it hardcodes `/home/$USER/Documents/server-panel`).
- Adds desktop launcher; optional autostart.
- Login gets a username field; old configs without a username default to `admin`, so nobody gets locked out.
- Settings page can change username + password.

Done (2026-11-20): `install.sh` (python check, tool report, login prompt via `panel.py --set-login` over stdin, optional sudo setup, launcher, opt-in autostart, `--yes`). Login takes username; legacy configs and requests without a username act as `admin`. Settings can change username (needs current password). `setup-sudo.sh` takes an optional install dir as 2nd arg; output for the old call is byte-identical (checked). Dry-run of the installer in a temp copy with a fake HOME passed.

## Phase 4 — MCP server

`mcp/server_panel_mcp.py`, pure Python stdio (no dependencies), talks to the panel API on 127.0.0.1 with a token.
- Read tools: status, services, sites/apps list, nginx sites + logs, databases, performance settings.
- Decided (2026-11-20): full control — every panel action incl. service control, any SQL, create/delete sites. Destructive tools still clearly named and described so the calling LLM asks its user first.
- Setup snippets for Claude Code, Codex and OpenCode in the README.

Done (2026-11-20): `mcp/server_panel_mcp.py` (stdlib, stdio JSON-RPC, 37 tools, localhost-only, lazy login + re-login on 401, `wait_for_job`), `mcp/README.md` with Claude Code / Codex / OpenCode snippets. `/api/login`, `/api/panel/open`, `/api/panel/close` refused. Smoke-tested over stdio against a read-only preview.

## Phase 5 — Docs + publish

README (install, MCP setup, screenshots), CLAUDE.md refresh, push to `github.com/VJ-Ranga/server-panel` after VJ's OK.

## Phase 6 — Talk first (could affect sites)

- `setup-sudo.sh` rule changes (path fix) — rewrites `/etc/sudoers.d/server-panel`.
- `wp-install-helper.sh` `/home/$PANEL_USER/local` handling and `index.html` `home-local` path.
- Salted password hashing upgrade (needs config migration).
- Any helper-script behaviour change.
