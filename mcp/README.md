# Server Panel MCP

A Python 3.8+ standard-library MCP server for Claude Code, Codex, and OpenCode.
It sends authenticated requests to the existing panel over localhost HTTP, using
newline-delimited JSON-RPC over stdio. It does not start the panel.

Destructive tools act on real sites and databases. Configure your MCP client to
ask you before calling tools that change the server. Tool descriptions and
annotations request confirmation; this bridge does not enforce a confirmation
prompt. Results are automatically redacted to protect plaintext credentials,
but share SQL output and server data carefully.

## Quick setup

From the repository directory, run these commands as your normal user.

```bash
scripts/mcp-setup.sh on
scripts/mcp-setup.sh status
scripts/mcp-setup.sh off
```

`on` enables the key and registers `server-panel` in Claude Code and Codex when their CLIs are available. Existing entries are kept by default. Use `on --force` to replace an existing entry. If OpenCode is detected, the script prints a JSON snippet for you to merge into its configuration. Restart the AI tool after setup.

The key is stored in the repository's Git-ignored `panel_config.json` with mode `0600`. The AI tool registration needs only the bridge command. `off` revokes key-based access immediately on a running panel and offers to remove Claude Code and Codex registrations. Use `off --yes` to keep them without prompting or `off --remove-clients` to remove them without prompting. Existing password-based registrations still authenticate after the key is turned off. Manage the OpenCode entry in its configuration.

To replace an active key, run `python3 panel.py --mcp-key rotate` and restart the AI tool.

## Configuration

| Environment variable | Default | Purpose |
| --- | --- | --- |
| `SERVER_PANEL_URL` | `http://127.0.0.1:8765` | Panel origin. Hosts allowed are `127.0.0.1`, `localhost` and `::1` |
| `SERVER_PANEL_TOKEN` | unset | Use an explicit bearer token first |
| `SERVER_PANEL_PASSWORD` | unset | Use the existing password-based login flow when supplied |
| `SERVER_PANEL_USER` | `admin` | Username for password-based login |
| `SERVER_PANEL_CONFIG` | Repository-root `panel_config.json` | Config path used to read the MCP key when neither token nor password is supplied |

Login is lazy and credentials are held in memory. When a password is configured, a 401 triggers one login and retry. Normal requests use a 30-second timeout. Job requests, job initiation and generic API requests use 120 seconds. Logs go to stderr only. Redirects and environment HTTP proxies are disabled.

If you override `SERVER_PANEL_CONFIG`, provide the same absolute path to the panel, setup script and MCP bridge. Automatic registration uses the repository default unless the AI client passes the override to the bridge process.

MCP keys can read settings. Updating settings, revealing credentials, reading WordPress credentials, or opening and closing the panel requires a browser or API session token.

## Manual client setup

Enable the key first with `python3 panel.py --mcp-key on`. Use the absolute path to the bridge in your checkout.

### Claude Code

```sh
claude mcp add server-panel -s user -- python3 /ABSOLUTE/PATH/server-panel/mcp/server_panel_mcp.py
```

### Codex

```sh
codex mcp add server-panel -- python3 /ABSOLUTE/PATH/server-panel/mcp/server_panel_mcp.py
```

You can also add the following to `~/.codex/config.toml`.

```toml
[mcp_servers.server-panel]
command = "python3"
args = ["/ABSOLUTE/PATH/server-panel/mcp/server_panel_mcp.py"]
```

### OpenCode

Merge this entry into `opencode.json`.

```json
{
  "mcp": {
    "server-panel": {
      "type": "local",
      "command": ["python3", "/ABSOLUTE/PATH/server-panel/mcp/server_panel_mcp.py"],
      "enabled": true
    }
  }
}
```

Restart your AI tool after saving the registration.

## Read-only tools

| Tool | HTTP route |
| --- | --- |
| `panel_status` | GET `/api/status` |
| `list_wordpress_sites` | GET `/api/wordpress/sites` |
| `list_laravel_apps` | GET `/api/laravel/apps` |
| `list_codeigniter_apps` | GET `/api/codeigniter/apps` |
| `list_php_projects` | GET `/api/php-projects/apps` |
| `list_projects` | GET `/api/projects` |
| `get_project(id?, name?)` | GET `/api/projects` (filtered by ID or case-insensitive name) |
| `wordpress_core_update_status` | GET `/api/wordpress/core-update-status` |
| `nginx_list_sites` | GET `/api/nginx/sites` |
| `nginx_get_site_config(name)` | GET `/api/nginx/site/{name}` |
| `nginx_get_main_config` | GET `/api/nginx/config` |
| `nginx_logs(kind)` | GET `/api/nginx/logs/{error\|access}` |
| `mysql_list_databases` | GET `/api/mysql/databases` |
| `performance_get_settings` | GET `/api/performance` |
| `phpmyadmin_status` | GET `/api/phpmyadmin/status` |
| `get_job(kind, job_id)` | GET job route from the table below |

## Tools requiring confirmation

| Tool | HTTP route / body notes |
| --- | --- |
| `service_control(service, action)` | POST `/api/services/{service}/{action}` |
| `nginx_save_site_config` | POST `/api/nginx/site/{name}`; `action: save`, `content` |
| `nginx_save_main_config` | POST `/api/nginx/config`; `content` |
| `nginx_toggle_site` | POST `/api/nginx/site/{name}`; `action: enable` or `disable` |
| `nginx_validate` | POST `/api/nginx/validate` |
| `mysql_create_database` | POST `/api/mysql/databases`; `name` |
| `mysql_drop_database` | DELETE `/api/mysql/databases/{name}` |
| `mysql_query(sql, database?)` | POST `/api/mysql/query`; `sql` maps to `query` |
| `wordpress_install` | POST `/api/wordpress/install` |
| `wordpress_delete` | DELETE `/api/wordpress/sites` |
| `wordpress_change_port` | POST `/api/wordpress/port` |
| `wordpress_core_update` | POST `/api/wordpress/core-update`; `paths` |
| `laravel_install` | POST `/api/laravel/install` |
| `laravel_delete` | DELETE `/api/laravel/apps` |
| `laravel_change_port` | POST `/api/laravel/port` |
| `codeigniter_install` | POST `/api/codeigniter/install` |
| `codeigniter_delete` | DELETE `/api/codeigniter/apps` |
| `codeigniter_change_port` | POST `/api/codeigniter/port` |
| `php_project_install` | POST `/api/php-projects/install` |
| `php_project_delete` | DELETE `/api/php-projects/apps` |
| `php_project_change_port` | POST `/api/php-projects/port` |
| `wait_for_job(kind, job_id, timeout_seconds?)` | Repeated GETs of an existing job; does not initiate changes |
| `panel_api(method, path, body?)` | GET, POST, or DELETE any other `/api/` route |

Install schemas use the panel's exact field names: `site_name`, `install_path`,
`db_name`, `db_user`, `db_pass`, `port`. WordPress additionally accepts `wp_title`,
`wp_admin`, `wp_admin_pass`, `wp_email`, `selected_plugins`; its required fields
are `site_name`, `db_name`, `db_user`, `db_pass`, `port`. Laravel additionally
accepts `app_name`, `laravel_version` (`latest` or `12`). PHP projects accept
`template` (`blank`, `php`, `php_db`). Other installers allow the panel's defaults.

Deletes accept `install_path` for WordPress or `path` for other apps, plus
optional `db_name`, `db_user`, `nginx_site`. Port changes use `nginx_site`, `port`.
`tools/list` supplies full schemas, defaults, and service/action enums.

`panel_api` refuses `/api/login`, `/api/panel/open`, `/api/panel/close`,
`/api/secrets/reveal`, `/api/wordpress/credentials`,
`/api/wordpress/change_db_password`, and `/api/wordpress/change_wp_admin`,
including case, slash, encoding, and query variants.
Paths must be direct `/api/` paths without traversal or encoded path segments;
encoded query parameters are supported. Tool results undergo recursive redaction
of sensitive credential keys and line patterns before returning to AI clients.
Settings and WordPress auto-login are not dedicated tools. Generic API calls can
reach WordPress auto-login and read settings. Settings updates, credential changes,
and credential reveals require a session token.

## Job kinds

| Kind | GET route |
| --- | --- |
| `wordpress_install` | `/api/wordpress/install/{job_id}` |
| `wordpress_delete` | `/api/wordpress/delete/{job_id}` |
| `wordpress_core_update` | `/api/wordpress/core-update/{job_id}` |
| `laravel_install` | `/api/laravel/install/{job_id}` |
| `laravel_delete` | `/api/laravel/delete/{job_id}` |
| `codeigniter_install` | `/api/codeigniter/install/{job_id}` |
| `codeigniter_delete` | `/api/codeigniter/delete/{job_id}` |
| `php_project_install` | `/api/php-projects/install/{job_id}` |
| `php_project_delete` | `/api/php-projects/delete/{job_id}` |

`wait_for_job` polls every 2 seconds while `status` is `running`, stopping on
`done` or `error`. It returns the final job JSON with the last 200 log lines. A `done` job can contain `result.success: false`,
for example a partial WordPress core update failure; that also sets `isError`.
The wait defaults to 600 seconds and accepts 1–1800 seconds. A timeout does not
cancel the panel job; use `get_job` afterward. phpMyAdmin installation is
synchronous and has no job route in this panel.

API JSON is pretty-printed as MCP text; responses over 60,000 characters are
truncated with a note. Tool failures use `isError: true`.

## Tests

```sh
python3 -m pytest -q
```

MCP integration tests use a fake HTTP server on `127.0.0.1:0`, never the real panel.
