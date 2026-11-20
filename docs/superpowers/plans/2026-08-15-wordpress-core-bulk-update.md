# WordPress Core Bulk Update Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a shared-cache, bulk WordPress core updater for selected local sites.

**Architecture:** `panel.py` will obtain and cache one official core archive, report each discovered site's installed version, and run selected updates as a background job. A new restricted mode in `wp-install-helper.sh` will perform the privileged core-file replacement while preserving each site's content and configuration. The existing WordPress Installed Sites screen will show cache/version status, selectable outdated sites, and an update job log.

**Tech Stack:** Python 3 standard library HTTP server, Bash, vanilla JavaScript, Bootstrap 5, Python `unittest`.

## Global Constraints

- Update WordPress core only; never update plugins or themes.
- Reuse `cache/wordpress/latest.tar.gz` and `cache/wordpress/latest.version` for all selected sites.
- Preserve `wp-content/`, `wp-config.php`, and database contents.
- Only accept site paths returned by the current WordPress discovery pass.
- Continue processing selected sites after an individual site failure.
- Do not add external Python dependencies.

---

### Task 1: Add Core Update Backend Tests

**Files:**
- Create: `tests/test_wordpress_core_update_backend.py`
- Modify: `panel.py:457-505`, `panel.py:1796-1842`, `panel.py:2034-2063`

**Interfaces:**
- Consumes: `get_wp_sites() -> list[dict]`.
- Produces: `get_wp_core_version(install_path) -> str`, `get_wp_core_update_status() -> dict`, `start_wordpress_core_update(paths) -> str`, and the three `/api/wordpress/core-update*` routes.

- [ ] **Step 1: Write failing backend contract tests**

```python
import os
import re
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PANEL_PATH = os.path.join(PROJECT_ROOT, "panel.py")


class WordPressCoreUpdateBackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(PANEL_PATH) as f:
            cls.source = f.read()

    def test_site_discovery_reads_installed_core_version(self):
        self.assertIn("get_wp_core_version(site_path)", self.source)
        self.assertIn('entry["wp_version"]', self.source)

    def test_status_endpoint_reports_cache_and_site_versions(self):
        self.assertIn("def get_wp_core_update_status():", self.source)
        self.assertIn('path == "/api/wordpress/core-update-status"', self.source)
        self.assertIn('"cached_version"', self.source)
        self.assertIn('"target_version"', self.source)

    def test_update_endpoint_rejects_paths_not_in_current_discovery(self):
        self.assertIn("def start_wordpress_core_update(paths):", self.source)
        self.assertIn("Unknown WordPress site path", self.source)
        self.assertIn('path == "/api/wordpress/core-update"', self.source)

    def test_update_job_is_pollable_and_uses_the_privileged_helper(self):
        self.assertIn("def update_wordpress_core_job(job_id, paths):", self.source)
        self.assertIn("--core-update", self.source)
        self.assertRegex(self.source, r'path\.startswith\("/api/wordpress/core-update/"\)')


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest tests.test_wordpress_core_update_backend -v`

Expected: FAIL because the core update functions and API routes do not exist.

- [ ] **Step 3: Implement the backend contract**

Add these focused helpers above `get_wp_sites()` in `panel.py`:

```python
def get_wp_core_version(install_path):
    version_file = os.path.join(install_path, "wp-includes", "version.php")
    try:
        content = open(version_file, errors="ignore").read()
        match = re.search(r"\$wp_version\s*=\s*'([^']+)'", content)
        return match.group(1) if match else ""
    except OSError:
        return ""


def get_latest_wp_version():
    result = run_cmd("curl -sf https://api.wordpress.org/core/version-check/1.7/", timeout=15)
    if not result["success"]:
        return ""
    try:
        return json.loads(result["stdout"])["offers"][0]["version"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError):
        return ""
```

Set `entry["wp_version"] = get_wp_core_version(site_path)` in `get_wp_sites()`. Add a cache-preparation helper that creates `WP_CACHE_DIR`, compares `get_latest_wp_version()` with `WP_CACHE_VERSION`, downloads to `WP_CACHE_TAR + ".part"` with `curl -fL --retry 3`, then uses `os.replace()` and writes the version marker only after the download succeeds. Return a dictionary with exactly `success`, `target_version`, `cached_version`, `cache_state`, and `sites` keys. Mark `cache_state` as `current`, `refreshed`, `cached-unverified`, or `unavailable`.

Add these routes:

```python
elif path == "/api/wordpress/core-update-status":
    self.send_json(get_wp_core_update_status())

elif path.startswith("/api/wordpress/core-update/"):
    job_id = path.split("/")[-1]
    if job_id in _jobs:
        self.send_json(_jobs[job_id])
    else:
        self.send_json({"error": "Job not found"}, 404)
```

In `do_POST`, validate `data.get("paths")` is a non-empty list of strings. Compare it to `{site["path"] for site in get_wp_sites()}` and return `{"success": False, "error": "Unknown WordPress site path"}` for any mismatch. Create an `_jobs[job_id]` entry and start `update_wordpress_core_job` in a daemon thread.

- [ ] **Step 4: Run the backend contract tests**

Run: `python3 -m unittest tests.test_wordpress_core_update_backend -v`

Expected: PASS.

- [ ] **Step 5: Commit the tested backend API contract**

```bash
git add panel.py tests/test_wordpress_core_update_backend.py
```

### Task 2: Add Safe Privileged Core Replacement

**Files:**
- Create: `tests/test_wordpress_core_update_helper.py`
- Modify: `wp-install-helper.sh:48-130`

**Interfaces:**
- Consumes: `sudo wp-install-helper.sh --core-update <install_path> <archive_path>`.
- Produces: a non-zero exit on unsafe site/archive or failed replacement; a zero exit only after maintenance mode has been removed and ownership repaired.

- [ ] **Step 1: Write failing helper tests**

```python
import os
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HELPER_PATH = os.path.join(PROJECT_ROOT, "wp-install-helper.sh")


class WordPressCoreUpdateHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(HELPER_PATH) as f:
            cls.source = f.read()

    def test_helper_has_restricted_core_update_mode(self):
        self.assertIn('"--core-update"', self.source)
        self.assertIn('ARCHIVE_PATH="$PHP_VER"', self.source)
        self.assertIn('"$INSTALL_PATH/wp-config.php"', self.source)
        self.assertIn('"$INSTALL_PATH/wp-content"', self.source)

    def test_helper_uses_maintenance_mode_and_always_removes_it(self):
        self.assertIn('MAINTENANCE_FILE="$INSTALL_PATH/.maintenance"', self.source)
        self.assertIn('trap \'rm -f "$MAINTENANCE_FILE"', self.source)

    def test_helper_extracts_only_the_official_archive_and_updates_core_paths(self):
        self.assertIn('EXPECTED_ARCHIVE="$SCRIPT_DIR/cache/wordpress/latest.tar.gz"', self.source)
        self.assertIn('tar -xzf "$ARCHIVE_PATH"', self.source)
        self.assertIn('rm -rf "$INSTALL_PATH/wp-admin" "$INSTALL_PATH/wp-includes"', self.source)
        self.assertIn('cp -a "$STAGE_DIR/wordpress/wp-admin"', self.source)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest tests.test_wordpress_core_update_helper -v`

Expected: FAIL because `--core-update` is not implemented.

- [ ] **Step 3: Implement `--core-update` before the ordinary install path**

Insert this mode after `--set-port` and before the final normal-install validation in `wp-install-helper.sh`:

```bash
if [ "$INSTALL_PATH" = "--core-update" ]; then
    INSTALL_PATH="$SITE_NAME"
    ARCHIVE_PATH="$PHP_VER"
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
    EXPECTED_ARCHIVE="$SCRIPT_DIR/cache/wordpress/latest.tar.gz"
    if ! is_safe_wp_path "$INSTALL_PATH" || [ ! -f "$INSTALL_PATH/wp-config.php" ]; then
        echo "Error: unsafe WordPress site path"
        exit 1
    fi
    if [ "$ARCHIVE_PATH" != "$EXPECTED_ARCHIVE" ] || [ ! -r "$ARCHIVE_PATH" ]; then
        echo "Error: invalid WordPress core archive"
        exit 1
    fi

    STAGE_DIR="$(mktemp -d /tmp/_panel_wp_update.XXXXXX)"
    MAINTENANCE_FILE="$INSTALL_PATH/.maintenance"
    cleanup() {
        rm -f "$MAINTENANCE_FILE"
        rm -rf "$STAGE_DIR"
    }
    trap 'rm -f "$MAINTENANCE_FILE"; rm -rf "$STAGE_DIR"' EXIT

    printf '<?php $upgrading = %s; ?>\n' "$(date +%s)" > "$MAINTENANCE_FILE"
    tar -xzf "$ARCHIVE_PATH" -C "$STAGE_DIR"
    [ -d "$STAGE_DIR/wordpress/wp-admin" ] && [ -d "$STAGE_DIR/wordpress/wp-includes" ] || {
        echo "Error: invalid WordPress archive layout"
        exit 1
    }
    rm -rf "$INSTALL_PATH/wp-admin" "$INSTALL_PATH/wp-includes"
    cp -a "$STAGE_DIR/wordpress/wp-admin" "$STAGE_DIR/wordpress/wp-includes" "$INSTALL_PATH/"
    for file in index.php license.txt readme.html wp-activate.php wp-blog-header.php wp-comments-post.php wp-config-sample.php wp-cron.php wp-links-opml.php wp-load.php wp-login.php wp-mail.php wp-settings.php wp-signup.php wp-trackback.php xmlrpc.php; do
        [ -f "$STAGE_DIR/wordpress/$file" ] && cp -a "$STAGE_DIR/wordpress/$file" "$INSTALL_PATH/$file"
    done
    chown -R www-data:www-data "$INSTALL_PATH/wp-admin" "$INSTALL_PATH/wp-includes"
    set_wp_update_perms
    echo "[helper] WordPress core updated for $INSTALL_PATH"
    exit 0
fi
```

Keep `wp-content/` and `wp-config.php` out of every removal and copy operation. Do not run WordPress database upgrades in the helper.

- [ ] **Step 4: Run the helper tests**

Run: `python3 -m unittest tests.test_wordpress_core_update_helper -v`

Expected: PASS.

- [ ] **Step 5: Commit the helper change**

```bash
git add wp-install-helper.sh tests/test_wordpress_core_update_helper.py
```

### Task 3: Complete Background Job Behavior

**Files:**
- Modify: `panel.py:1410-1667`
- Modify: `tests/test_wordpress_core_update_backend.py`

**Interfaces:**
- Consumes: `update_wordpress_core_job(job_id: str, paths: list[str])` and the cache result from `get_wp_core_update_status()`.
- Produces: job data with `status`, `logs`, and `result = {"sites": [{"path", "name", "status", "error"}]}`.

- [ ] **Step 1: Extend the failing backend test with job requirements**

```python
    def test_update_job_skips_current_sites_and_continues_after_errors(self):
        self.assertIn('"already-current"', self.source)
        self.assertIn('"failed"', self.source)
        self.assertIn('for site_path in paths:', self.source)
        self.assertIn('results.append(', self.source)

    def test_update_job_passes_only_the_cached_archive_to_the_helper(self):
        expected = 'sudo {shell_quote(helper)} --core-update {shell_quote(site_path)} {shell_quote(WP_CACHE_TAR)}'
        self.assertIn(expected, self.source)
```

- [ ] **Step 2: Run the targeted test to verify it fails**

Run: `python3 -m unittest tests.test_wordpress_core_update_backend.WordPressCoreUpdateBackendTests.test_update_job_skips_current_sites_and_continues_after_errors -v`

Expected: FAIL because no update job implementation exists.

- [ ] **Step 3: Implement the job**

Add this function before `class Handler`:

```python
def update_wordpress_core_job(job_id, paths):
    job = _jobs[job_id]
    results = []

    def log(message):
        job["logs"].append(message)
        print(message)

    try:
        status = get_wp_core_update_status()
        target_version = status.get("target_version", "")
        if not status.get("success") or not target_version or not os.path.exists(WP_CACHE_TAR):
            raise RuntimeError(status.get("error") or "No WordPress core archive is available")

        known_sites = {site["path"]: site for site in get_wp_sites()}
        helper = os.path.join(SCRIPT_DIR, "wp-install-helper.sh")
        for site_path in paths:
            site = known_sites[site_path]
            name = site["name"]
            installed = site.get("wp_version", "")
            if installed == target_version:
                log(f"{name}: already on WordPress {target_version}; skipped.")
                results.append({"path": site_path, "name": name, "status": "already-current", "error": ""})
                continue
            log(f"{name}: updating WordPress {installed or 'unknown'} to {target_version}...")
            result = run_cmd(
                f"sudo {shell_quote(helper)} --core-update {shell_quote(site_path)} {shell_quote(WP_CACHE_TAR)}",
                timeout=180,
            )
            if result["success"]:
                log(f"{name}: updated successfully.")
                results.append({"path": site_path, "name": name, "status": "updated", "error": ""})
            else:
                error = (result["stderr"] or result["stdout"] or "Unknown update failure").strip()
                log(f"{name}: failed: {error}")
                results.append({"path": site_path, "name": name, "status": "failed", "error": error})
        job["status"] = "done"
        job["result"] = {"success": True, "target_version": target_version, "sites": results}
    except Exception as exc:
        log(f"Core update could not start: {exc}")
        job["status"] = "error"
        job["result"] = {"success": False, "error": str(exc), "sites": results}
```

Ensure the status helper never overwrites a valid cache when a remote check or download fails. The job must record an individual error and continue rather than raising inside the per-site loop.

- [ ] **Step 4: Run all core-update backend tests**

Run: `python3 -m unittest tests.test_wordpress_core_update_backend -v`

Expected: PASS.

- [ ] **Step 5: Commit the job behavior**

```bash
git add panel.py tests/test_wordpress_core_update_backend.py
```

### Task 4: Add Installed-Sites Update Controls

**Files:**
- Create: `tests/test_wordpress_core_update_frontend.py`
- Modify: `index.html:457-478`, `index.html:1825-1906`

**Interfaces:**
- Consumes: `GET /api/wordpress/core-update-status`, `POST /api/wordpress/core-update`, and poll response from `GET /api/wordpress/core-update/<job_id>`.
- Produces: `loadWpCoreUpdateStatus()`, `startWpCoreUpdate()`, and `pollWpCoreUpdate(jobId)`.

- [ ] **Step 1: Write failing frontend contract tests**

```python
import os
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_PATH = os.path.join(PROJECT_ROOT, "index.html")


class WordPressCoreUpdateFrontendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(INDEX_PATH) as f:
            cls.source = f.read()

    def test_installed_sites_has_core_update_area(self):
        self.assertIn('id="wp-core-update-status"', self.source)
        self.assertIn('id="wp-core-update-log"', self.source)
        self.assertIn('id="wp-core-update-btn"', self.source)
        self.assertIn('onclick="startWpCoreUpdate()"', self.source)

    def test_frontend_loads_status_and_starts_selected_paths(self):
        self.assertIn("async function loadWpCoreUpdateStatus()", self.source)
        self.assertIn("'/api/wordpress/core-update-status'", self.source)
        self.assertIn("async function startWpCoreUpdate()", self.source)
        self.assertIn("'/api/wordpress/core-update', 'POST', { paths }", self.source)

    def test_frontend_polls_and_renders_update_results(self):
        self.assertIn("async function pollWpCoreUpdate(jobId)", self.source)
        self.assertIn('`/api/wordpress/core-update/${jobId}`', self.source)
        self.assertIn("loadWPSites();", self.source)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest tests.test_wordpress_core_update_frontend -v`

Expected: FAIL because the update area and JavaScript functions do not exist.

- [ ] **Step 3: Implement the UI and client flow**

Place this card above the sites container in the WordPress Sites tab:

```html
<div class="service-card mb-3">
  <div class="d-flex align-items-center justify-content-between gap-2 flex-wrap">
    <div>
      <div class="section-title mb-1"><i class="bi bi-arrow-up-circle"></i> WordPress Core Updates</div>
      <div id="wp-core-update-status" style="font-size:.8rem;color:#6c7086;">Checking available version…</div>
    </div>
    <button id="wp-core-update-btn" class="btn btn-sm btn-primary" onclick="startWpCoreUpdate()" disabled>
      <i class="bi bi-arrow-up-circle"></i> Update Selected
    </button>
  </div>
  <div id="wp-core-update-log" class="log-box mt-3" style="display:none;height:160px;color:#cdd6f4;"></div>
</div>
```

Add a checkbox to each rendered outdated card in `renderWordPressSites()` using `s.wp_version !== wpCoreUpdateState.targetVersion`, with the exact class `wp-core-update-choice` and `value="${esc(s.path)}"`. Show `s.wp_version || 'unknown'` in the site's metadata.

Add this client state and functions near the other WordPress list functions:

```javascript
let wpCoreUpdateState = { targetVersion: '', status: null, poll: null };

async function loadWpCoreUpdateStatus() {
  const statusEl = document.getElementById('wp-core-update-status');
  const button = document.getElementById('wp-core-update-btn');
  const r = await api('/api/wordpress/core-update-status');
  wpCoreUpdateState.status = r;
  wpCoreUpdateState.targetVersion = r.target_version || '';
  if (!r.success) {
    statusEl.textContent = 'Core update unavailable: ' + (r.error || 'unknown error');
    button.disabled = true;
    return;
  }
  const note = r.cache_state === 'cached-unverified' ? ' Cached version is unverified.' : '';
  statusEl.textContent = `Target: WordPress ${r.target_version}. Cache: ${r.cache_state}.${note}`;
  button.disabled = !r.target_version;
  renderWordPressSites();
}

async function startWpCoreUpdate() {
  const paths = [...document.querySelectorAll('.wp-core-update-choice:checked')].map(el => el.value);
  if (!paths.length) {
    toast('Select at least one outdated WordPress site', 'error');
    return;
  }
  const button = document.getElementById('wp-core-update-btn');
  const log = document.getElementById('wp-core-update-log');
  button.disabled = true;
  log.style.display = 'block';
  log.textContent = 'Starting core update…\n';
  const r = await api('/api/wordpress/core-update', 'POST', { paths });
  if (!r.success) {
    log.textContent += 'Error: ' + (r.error || 'Failed to start');
    button.disabled = false;
    return;
  }
  pollWpCoreUpdate(r.job_id);
}

async function pollWpCoreUpdate(jobId) {
  if (wpCoreUpdateState.poll) clearInterval(wpCoreUpdateState.poll);
  const log = document.getElementById('wp-core-update-log');
  wpCoreUpdateState.poll = setInterval(async () => {
    const job = await api(`/api/wordpress/core-update/${jobId}`);
    log.textContent = (job.logs || []).join('\n');
    log.scrollTop = log.scrollHeight;
    if (job.status === 'done' || job.status === 'error') {
      clearInterval(wpCoreUpdateState.poll);
      wpCoreUpdateState.poll = null;
      toast(job.status === 'done' ? 'WordPress core update finished' : 'WordPress core update failed', job.status === 'done' ? 'success' : 'error');
      await loadWPSites();
      await loadWpCoreUpdateStatus();
    }
  }, 800);
}
```

Call `loadWpCoreUpdateStatus()` at the end of successful `loadWPSites()` after `appListState.wordpress.items` is updated. Do not display update checkboxes until `wpCoreUpdateState.targetVersion` is populated.

- [ ] **Step 4: Run the frontend contract tests**

Run: `python3 -m unittest tests.test_wordpress_core_update_frontend -v`

Expected: PASS.

- [ ] **Step 5: Commit the UI**

```bash
git add index.html tests/test_wordpress_core_update_frontend.py
```

### Task 5: Document and Verify the Complete Feature

**Files:**
- Modify: `README.md:101-117`
- Modify: `CLAUDE.md:73-96`, `CLAUDE.md:177-186`
- Modify: `tests/test_wordpress_core_update_backend.py`
- Modify: `tests/test_wordpress_core_update_helper.py`
- Modify: `tests/test_wordpress_core_update_frontend.py`

**Interfaces:**
- Consumes: completed core-update API, helper, and UI.
- Produces: accurate project documentation and full regression evidence.

- [ ] **Step 1: Add a failing documentation assertion**

Append this to `tests/test_wordpress_core_update_frontend.py`:

```python
    def test_readme_describes_cached_core_updates(self):
        with open(os.path.join(PROJECT_ROOT, "README.md")) as f:
            readme = f.read()
        self.assertIn("Update WordPress core", readme)
        self.assertIn("cached official archive", readme)
```

- [ ] **Step 2: Run the documentation assertion to verify it fails**

Run: `python3 -m unittest tests.test_wordpress_core_update_frontend.WordPressCoreUpdateFrontendTests.test_readme_describes_cached_core_updates -v`

Expected: FAIL because the README does not document core updates.

- [ ] **Step 3: Update documentation**

Add these two bullets to the WordPress list in `README.md`:

```markdown
- Update WordPress core for selected local sites without changing plugins, themes, `wp-content`, or `wp-config.php`.
- Reuse one cached official archive across updates, refreshing it only when WordPress releases a newer version.
```

Add `GET /api/wordpress/core-update-status`, `POST /api/wordpress/core-update`, and `GET /api/wordpress/core-update/<job_id>` to the WordPress API table in `CLAUDE.md`. Add the shared-cache bulk core update workflow to its WordPress feature list.

- [ ] **Step 4: Run all relevant tests**

Run: `python3 -m unittest tests.test_wordpress_core_update_backend tests.test_wordpress_core_update_helper tests.test_wordpress_core_update_frontend tests.test_wordpress_custom_path -v`

Expected: PASS.

- [ ] **Step 5: Run the whole test suite**

Run: `python3 -m unittest discover -s tests -v`

Expected: PASS with no failures.

- [ ] **Step 6: Perform a manual local verification**

Run: `python3 panel.py`

Expected: the panel starts on `http://127.0.0.1:8765`.

Verify in the browser:

1. Open App Launcher, then WordPress Manage.
2. Confirm the Core Updates card displays target version and cache state.
3. Confirm current sites have no selectable update checkbox and outdated sites do.
4. Select one outdated disposable site and start the update.
5. Confirm the log reports maintenance/update completion, `wp-content/` and `wp-config.php` remain present, and the site's version matches the target after Refresh.
6. Stop the temporary server after verification with `kill $(lsof -ti:8765)`.

- [ ] **Step 7: Commit documentation and verification tests**

```bash
git add README.md CLAUDE.md tests/test_wordpress_core_update_backend.py tests/test_wordpress_core_update_helper.py tests/test_wordpress_core_update_frontend.py
```
