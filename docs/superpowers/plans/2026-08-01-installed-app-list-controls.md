# Installed App List Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add search, sort, clear, and count controls to every installed website/app list.

**Architecture:** Keep the controls frontend-side using shared vanilla JavaScript helpers in `index.html`. Add lightweight backend timestamp fields so newest/oldest sorting works consistently across WordPress, Laravel, CodeIgniter, and PHP Projects.

**Tech Stack:** Python `unittest`, vanilla JavaScript, Bootstrap-themed static HTML.

## Global Constraints

- No new external dependencies.
- Preserve the existing dark Bootstrap panel style.
- Controls must cover WordPress Sites, Laravel Apps, CodeIgniter Apps, and PHP Projects.
- Search must filter by name, path, database, database user, port, nginx site, and app-specific labels.
- Sort choices must include Newest first, Oldest first, Name A-Z, Name Z-A, Port low-high, and Port high-low.

---

### Task 1: Tests and Backend Timestamps

**Files:**
- Create: `tests/test_installed_list_controls_frontend.py`
- Create: `tests/test_installed_list_timestamps_backend.py`
- Modify: `panel.py`

**Interfaces:**
- Produces: list API objects with `modified_at` numeric timestamps.
- Produces: frontend source markers for `renderAppListControls`, `filterAndSortApps`, and per-list toolbar IDs.

- [ ] **Step 1: Write failing tests**

Add frontend source tests for all four toolbars and shared helper names. Add backend test patching WordPress discovery to confirm `modified_at` is emitted.

- [ ] **Step 2: Run tests to verify failure**

Run: `python3 -m unittest tests.test_installed_list_controls_frontend tests.test_installed_list_timestamps_backend`

Expected: FAIL because controls and timestamp fields are missing.

- [ ] **Step 3: Add timestamp fields**

In `panel.py`, set `entry["modified_at"] = int(os.path.getmtime(site_path))` for WordPress, Laravel, CodeIgniter, and PHP project entries where the path exists.

- [ ] **Step 4: Run backend timestamp test**

Run: `python3 -m unittest tests.test_installed_list_timestamps_backend`

Expected: OK.

### Task 2: Shared Frontend List Controls

**Files:**
- Modify: `index.html`
- Test: `tests/test_installed_list_controls_frontend.py`

**Interfaces:**
- Consumes: arrays from `/api/wordpress/sites`, `/api/laravel/apps`, `/api/codeigniter/apps`, and `/api/php-projects/apps`.
- Produces: `renderAppListControls(type, label)`, `filterAndSortApps(type, items)`, `renderAppListCount(type, shown, total)`, and `clearAppListSearch(type)`.

- [ ] **Step 1: Add shared app list state and helpers**

In `index.html`, add a JS object keyed by `wordpress`, `laravel`, `codeigniter`, and `php-projects` that tracks `items`, `search`, and `sort`.

- [ ] **Step 2: Add toolbar markup above each list container**

Add search input, sort dropdown, clear button, and count span above each installed list container.

- [ ] **Step 3: Render filtered/sorted data in each loader**

Update `loadWPSites`, `loadLaravelApps`, `loadCodeIgniterApps`, and `loadPhpProjects` to store API results and call app-specific render functions.

- [ ] **Step 4: Add no-results empty states**

When filtering returns zero items, show a message that no results matched the search.

- [ ] **Step 5: Run targeted frontend source tests**

Run: `python3 -m unittest tests.test_installed_list_controls_frontend`

Expected: OK.

### Task 3: Verification

**Files:**
- Test: `tests/`

**Interfaces:**
- Consumes: completed Task 1 and Task 2 changes.
- Produces: verified implementation.

- [ ] **Step 1: Run targeted tests**

Run: `python3 -m unittest tests.test_installed_list_controls_frontend tests.test_installed_list_timestamps_backend`

Expected: OK.

- [ ] **Step 2: Run full tests**

Run: `python3 -m unittest discover -s tests`

Expected: OK.
