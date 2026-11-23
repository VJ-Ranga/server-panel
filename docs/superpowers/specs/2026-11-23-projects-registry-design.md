# Projects registry design

## Intent

Keep every project's links in one place inside the panel: the local site, the git repository, the live and staging sites, and the hosting dashboard. A project can have several parts, such as a WordPress backend and an Astro frontend on different hosts. The owner manages the list in the UI. AI tools read it through MCP to answer "which repo or host is this?" without asking.

## Goals

- Store projects and their parts with names, URLs, folders and short notes.
- Open any stored link from the panel.
- Show whether each part's local URL is running.
- Link an already-detected local WordPress, Laravel, CodeIgniter or PHP project to a part without typing.
- Expose the list read-only through MCP.

## Non-goals

- No live-site health checks, git API calls or other outgoing network requests.
- No deployment, git push, SSH or hosting actions.

## Anti-goals

- The registry must never hold passwords, tokens, keys or credentials, including in URLs such as `https://token@github.com/...`.
- Client names must never reach the public repository.

## Approaches considered

1. **Separate git-ignored `projects.json` with a small CRUD API (chosen).** Keeps client data out of git and out of `panel_config.json`, which holds the login.
2. Store projects inside `panel_config.json`. Rejected: mixes credentials and client data, and every login change rewrites it.
3. Keep using the Obsidian projects index. Rejected: the panel and AI tools cannot read or validate it reliably. Each project stores a link to its vault instead.

## Data

The file is `projects.json` in the repository directory. It is git-ignored, written atomically with mode `0600`, and its path can be overridden with the `SERVER_PANEL_PROJECTS` environment variable.

```json
{"version": 1, "projects": [Project, ...]}
```

### Project

| Field | Rule |
|---|---|
| `id` | Server-generated, 8 lowercase hex characters, immutable |
| `name` | Required, 1–80 characters after trimming |
| `client` | Optional, at most 80 characters |
| `status` | One of `planning`, `building`, `review`, `live`, `maintenance` or `archived`. The default is `building` |
| `vault_path` | Optional absolute path, at most 300 characters |
| `notes` | Optional, at most 2000 characters |
| `parts` | A list of at most 12 parts |
| `created`, `updated` | ISO-8601 UTC timestamps set by the server |

### Part

| Field | Rule |
|---|---|
| `id` | Server-generated, 8 lowercase hex characters, kept when an update sends the same id |
| `role` | One of `wordpress`, `astro`, `laravel`, `codeigniter`, `php`, `api`, `frontend`, `backend` or `other` |
| `label` | Optional, at most 80 characters |
| `local_url` | Optional `http` or `https` URL whose host is `localhost`, `127.0.0.1` or `[::1]` |
| `local_path` | Optional absolute path, at most 300 characters |
| `live_url`, `staging_url`, `hosting_url` | Optional `http` or `https` URLs |
| `git_url` | Optional `https://` URL or SSH form `git@host:owner/repo(.git)` |
| `hosting_name` | Optional, at most 80 characters |
| `notes` | Optional, at most 1000 characters |

Every URL has a 500-character limit. URLs must not contain user information (`user@` or `user:pass@`), so a request with a token in a URL is rejected with HTTP 400. Unknown fields are dropped. Strings are trimmed.

## API

All routes need a session token or an MCP key.

| Method | Path | Behavior |
|---|---|---|
| GET | `/api/projects` | Returns `{"projects": [...]}`. Each part gets `local_running`: `true` or `false` from a TCP connect to the local URL's port on loopback with a 0.3-second timeout, or `null` without a local URL. Checks run in parallel with a total limit of about 1 second |
| POST | `/api/projects` | Create. Returns `{"success": true, "project": {...}}`, or 400 with `error` |
| POST | `/api/projects/<id>` | Replace the editable fields of a project. Returns 404 for an unknown id |
| DELETE | `/api/projects/<id>` | Delete. Returns 404 for an unknown id |

## MCP

- `list_projects` is a read-only tool that calls `GET /api/projects`.
- `get_project` is a read-only tool that takes an `id` or a case-insensitive `name` and returns a single project.

## UI

- A **Projects** sidebar item opens `page-projects`, after the App Launcher.
- Each project has a card with its name, client, status badge and vault link. Each part is a row with a role badge, label and a local running dot (green running, grey stopped). The row has open buttons for Local, Live, Staging, Repo and Hosting. Links open with `target="_blank" rel="noopener noreferrer"`.
- The page has a search box that filters by project, client, part label or URL.
- **Add project** and **Edit** open one modal with project fields and a dynamic part list. Each part has a **Link local site** select filled from the existing app list endpoints, which fills the local URL with `http://localhost:<port>/` and the local folder.
- Delete uses the existing custom confirmation modal.
- The UI escapes all stored text with the existing `esc()` helper. It reuses the existing classes, buttons and theme tokens in light and dark modes.
- An empty state invites the user to add the first project.

## Left to the builder

The builder chooses the exact markup, icons and the split into helper functions within the existing code style. The builder also adds fake sample data to the demo server and documentation for README, CLAUDE.md and the MCP README.
