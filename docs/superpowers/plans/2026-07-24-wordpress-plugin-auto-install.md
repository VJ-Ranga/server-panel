# WordPress Plugin Auto-Install Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local WordPress plugin zip library and allow selected plugins to be installed and activated during WordPress site creation.

**Architecture:** The backend scans `wp-plugin-library/` for zip files, extracts plugin metadata from PHP headers, and exposes it via an authenticated API. The WordPress install flow receives selected plugin IDs, validates them against the scanned library, extracts safe zip contents into the new site's `wp-content/plugins/`, and activates each plugin after WordPress install. The frontend shows plugin checkboxes in the existing WordPress install form.

**Tech Stack:** Python standard library (`zipfile`, `os`, `re`), existing `ThreadingHTTPServer`, Bash helper for permissions, vanilla JavaScript, Bootstrap UI.

## Global Constraints

- Plugin folder is `wp-plugin-library/` under `/home/vjranga/Documents/server-panel`.
- Only `.zip` files from that folder can be selected.
- Selected plugins are installed and activated automatically.
- Invalid zip files are skipped and surfaced in API results.
- Plugin activation failure logs an error but does not roll back the WordPress site.
- Extraction must prevent zip-slip paths outside `wp-content/plugins/`.

---

### Task 1: Plugin Library Folder And Scanner

**Files:**
- Create directory: `wp-plugin-library/`
- Modify: `panel.py`

**Interfaces:**
- Produces: `get_wp_plugin_library() -> dict` with `success`, `plugins`, and `invalid` keys.
- Produces: `GET /api/wordpress/plugins` returning plugin metadata.

- [ ] Create `wp-plugin-library/` in the project root.
- [ ] Add `WP_PLUGIN_LIBRARY_DIR = os.path.join(SCRIPT_DIR, "wp-plugin-library")` near other path constants.
- [ ] Implement zip scanning with `zipfile.ZipFile`.
- [ ] Detect plugin headers `Plugin Name:` and `Version:` from PHP files inside the zip.
- [ ] Return stable plugin IDs based on zip filename.
- [ ] Add authenticated `GET /api/wordpress/plugins` route.
- [ ] Verify with an empty folder: API returns `success: true`, empty `plugins`, empty `invalid`.

### Task 2: Plugin Selection UI

**Files:**
- Modify: `index.html`

**Interfaces:**
- Consumes: `GET /api/wordpress/plugins`.
- Produces: `selected_plugins` array in `/api/wordpress/install` payload.

- [ ] Add a **Plugins** section to the WordPress install form below admin email.
- [ ] Add `loadWpPluginLibrary()` to fetch plugin metadata.
- [ ] Render checkboxes with plugin name, version, and zip filename.
- [ ] Add a Refresh button for plugin rescanning.
- [ ] Call `loadWpPluginLibrary()` when the WordPress page/install tab loads.
- [ ] In `startWpInstall()`, collect checked plugin IDs into `selected_plugins`.
- [ ] Verify empty folder shows a useful “No plugin zips found” message.

### Task 3: Safe Plugin Extract And Activation

**Files:**
- Modify: `panel.py`
- Modify: `wp-install-helper.sh` only if permission fix is needed after extraction.

**Interfaces:**
- Consumes: `selected_plugins: list[str]` from `/api/wordpress/install`.
- Produces install logs for each selected plugin.

- [ ] Add validation that each requested plugin ID exists in `get_wp_plugin_library()`.
- [ ] Add safe extraction helper that rejects absolute paths and `..` path traversal.
- [ ] Extract selected plugin zips into `<install_path>/wp-content/plugins/` after WordPress is configured.
- [ ] Run existing permission helper path after plugin extraction so `vjranga` and `www-data` can edit files.
- [ ] Add PHP activation script using `activate_plugin()` for each plugin main file.
- [ ] Log `[plugin] Installed and activated: Name` on success.
- [ ] Log `[plugin] Activation failed: Name - reason` on activation failure without failing the site install.

### Task 4: Verification

**Files:**
- Modify: no files unless bugs are found.

- [ ] Run `python3 -m py_compile panel.py`.
- [ ] Run `bash -n wp-install-helper.sh`.
- [ ] Add one valid plugin zip to `wp-plugin-library/` and verify it appears in the install form.
- [ ] Install a WordPress site with no plugins selected; expected site install still succeeds.
- [ ] Install a WordPress site with one plugin selected; expected plugin appears under `wp-content/plugins/` and is active.
