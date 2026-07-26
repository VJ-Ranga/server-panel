# App Launcher Navigation Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make App Launcher the single app hub by removing app-specific sidebar links and adding installed counts plus recent project details to each launcher card.

**Architecture:** This is a frontend-only change in `index.html` with static frontend structure tests in `tests/test_app_launcher_frontend.py`. Existing hidden app pages remain unchanged and continue to own full management tables/actions. App Launcher loads summary data from existing app list APIs and renders only counts plus up to three recent/detected projects per app type.

**Tech Stack:** HTML, Bootstrap 5 classes, Bootstrap Icons, vanilla JavaScript, existing Python `unittest` frontend structure tests, Node inline JavaScript syntax checking.

## Global Constraints

- Use **App Launcher Only** for application navigation, and make it an app dashboard with creation actions, installed counts, and recent project details.
- Sidebar sections must be `Overview`, `Server`, and `System`.
- Remove direct sidebar links for `WordPress`, `Laravel`, `CodeIgniter`, and `PHP Projects`.
- Keep `page-wordpress`, `page-laravel`, `page-codeigniter`, and `page-php-projects` markup unchanged except for necessary navigation compatibility.
- Keep `pageTitles` entries for app pages because hidden pages still need correct titles when opened from App Launcher.
- `Create` opens the existing install tab for that app type.
- `View All` opens the existing installed-apps/sites tab for that app type.
- Per-project `Manage` opens the existing installed-apps/sites tab for that app type.
- Show only counts and up to three recent/detected items per app type inside App Launcher.
- Keep full installed-apps/sites lists, deletes, advanced actions, port changes, and logs inside the hidden app-specific pages.
- Do not add backend routes.
- Do not add destructive actions such as delete directly from App Launcher.

---

## File Structure

- Modify `tests/test_app_launcher_frontend.py`: update frontend structure tests for hidden app sidebar links, dashboard placeholders, summary loaders, and routing without app sidebar anchors.
- Modify `index.html`: remove app links from sidebar, rename `Services` to `Server`, add App Launcher summary containers, update navigation helpers, and add App Launcher summary rendering functions.
- Modify `CLAUDE.md`: update App Launcher docs to mention dashboard counts/recent items and hidden app pages.

---

### Task 1: Update App Launcher Frontend Tests

**Files:**
- Modify: `tests/test_app_launcher_frontend.py`

**Interfaces:**
- Produces tests requiring `launcher-*-count` and `launcher-*-recent` elements in `index.html`.
- Produces tests requiring `loadAppLauncherSummary`, `renderAppLauncherCardSummary`, `launcherItemUrl`, and `launcherItemMeta` functions.
- Produces tests requiring `openAppLauncherTarget` to call `showPage(appType, appLauncherLink())` instead of relying on app-specific sidebar anchors.

- [ ] **Step 1: Replace the current tests with hidden-sidebar and dashboard tests**

Replace `tests/test_app_launcher_frontend.py` with:

```python
import os
import re
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class AppLauncherFrontendTests(unittest.TestCase):
    LAUNCHER_APPS = [
        ("wordpress", "launcher-wordpress", "WordPress", "8090", "sites", "sites"),
        ("laravel", "launcher-laravel", "Laravel", "8100", "apps", "apps"),
        ("codeigniter", "launcher-codeigniter", "CodeIgniter", "8200", "apps", "apps"),
        ("php-projects", "launcher-php-projects", "PHP Project", "8300", "apps", "projects"),
    ]
    LAUNCHER_CARD_BOUNDARY = (
        r'(?:(?!id="launcher-(?:wordpress|laravel|codeigniter|php-projects)").)*?'
    )

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(PROJECT_ROOT, "index.html"), encoding="utf-8") as f:
            cls.html = f.read()
        sidebar_start = cls.html.index('<nav class="sidebar-nav')
        sidebar_end = cls.html.index('</nav>', sidebar_start)
        cls.sidebar = cls.html[sidebar_start:sidebar_end]

    def assert_html_pattern(self, pattern):
        self.assertRegex(self.html, re.compile(pattern, re.S))

    def test_sidebar_keeps_app_launcher_and_hides_app_pages(self):
        for text in [
            "showPage('app-launcher',this)",
            'id="page-app-launcher"',
            "'app-launcher':'App Launcher'",
        ]:
            self.assertIn(text, self.html)

        for hidden_href in [
            'href="#wordpress"',
            'href="#laravel"',
            'href="#codeigniter"',
            'href="#php-projects"',
        ]:
            self.assertNotIn(hidden_href, self.sidebar)

        for text in ["Server", "Nginx", "MySQL", "phpMyAdmin", "Performance", "System", "Settings"]:
            self.assertIn(text, self.sidebar)

    def test_all_launcher_cards_have_dashboard_placeholders(self):
        for app_type, card_id, label, port, _, noun in self.LAUNCHER_APPS:
            self.assertIn(card_id, self.html)
            self.assertIn(label, self.html)
            self.assertIn(f"Starts near {port}", self.html)
            self.assertIn(f'id="launcher-{app_type}-count"', self.html)
            self.assertIn(f'id="launcher-{app_type}-recent"', self.html)
            self.assertIn(noun, self.html)

    def test_launcher_cards_have_create_and_view_all_actions(self):
        for app_type, card_id, _, _, _, _ in self.LAUNCHER_APPS:
            escaped_app_type = re.escape(app_type)
            escaped_card_id = re.escape(card_id)

            self.assert_html_pattern(
                rf'id="{escaped_card_id}"{self.LAUNCHER_CARD_BOUNDARY}'
                rf'<button\b[^>]*onclick="appLauncherCreate\(\'{escaped_app_type}\'\)"[^>]*>'
                rf'.*?\bCreate\b.*?</button>'
            )
            self.assert_html_pattern(
                rf'id="{escaped_card_id}"{self.LAUNCHER_CARD_BOUNDARY}'
                rf'<button\b[^>]*onclick="appLauncherManage\(\'{escaped_app_type}\'\)"[^>]*>'
                rf'.*?\bView All\b.*?</button>'
            )

    def test_launcher_create_and_manage_mappings_target_expected_tabs(self):
        for app_type, _, _, _, manage_tab, _ in self.LAUNCHER_APPS:
            escaped_app_type = re.escape(app_type)
            escaped_manage_tab = re.escape(manage_tab)

            self.assert_html_pattern(
                rf'function appLauncherCreate\([^)]*\)\s*{{'
                rf'(?:(?!function appLauncherManage\().)*?'
                rf'[\'\"]{escaped_app_type}[\'\"]\s*:\s*[\'\"]install[\'\"]'
            )
            self.assert_html_pattern(
                rf'function appLauncherManage\([^)]*\)\s*{{'
                rf'(?:(?!function\s+\w+\().)*?'
                rf'[\'\"]{escaped_app_type}[\'\"]\s*:\s*[\'\"]{escaped_manage_tab}[\'\"]'
            )

    def test_navigation_helpers_do_not_require_hidden_sidebar_links(self):
        for function_name in [
            "function appLauncherLink(",
            "function openAppLauncherTarget(",
            "function appLauncherCreate(",
            "function appLauncherManage(",
        ]:
            self.assertIn(function_name, self.html)

        self.assert_html_pattern(
            r'function openAppLauncherTarget\(appType,\s*tabName\)\s*{'
            r'.*?showPage\(appType,\s*appLauncherLink\(\)\)'
            r'.*?switchTab\(appType,\s*tabName,'
        )

    def test_app_launcher_summary_functions_use_existing_apis(self):
        for function_name in [
            "async function loadAppLauncherSummary(",
            "function renderAppLauncherCardSummary(",
            "function launcherItemUrl(",
            "function launcherItemMeta(",
        ]:
            self.assertIn(function_name, self.html)

        for api_path in [
            "/api/wordpress/sites",
            "/api/laravel/apps",
            "/api/codeigniter/apps",
            "/api/php-projects/apps",
        ]:
            self.assertIn(api_path, self.html)

        self.assertIn(".slice(0, 3)", self.html)
        self.assertIn("appLauncherManage(type)", self.html)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the updated tests and verify they fail**

Run:

```bash
python3 -m unittest tests.test_app_launcher_frontend -v
```

Expected: `FAILED` because the sidebar still contains app links and App Launcher summary placeholders/functions are not implemented yet.

- [ ] **Step 3: Commit failing tests**

Run:

```bash
git add tests/test_app_launcher_frontend.py
git commit -m "Update app launcher navigation tests"
```

Expected: one test-only commit.

---

### Task 2: Implement Sidebar Cleanup And App Launcher Dashboard

**Files:**
- Modify: `index.html`

**Interfaces:**
- Consumes tests from Task 1.
- Produces `function appLauncherLink() -> Element|null`.
- Produces `async function loadAppLauncherSummary() -> Promise<void>`.
- Produces `function renderAppLauncherCardSummary(type: string, data: object) -> void`.
- Produces `function launcherItemUrl(item: object) -> string`.
- Produces `function launcherItemMeta(item: object) -> string`.

- [ ] **Step 1: Remove app-specific links from sidebar and rename Services to Server**

In `index.html`, replace the sidebar service section:

```html
<div class="nav-section">Services</div>
<a href="#nginx" onclick="showPage('nginx',this); return false;"><i class="bi bi-arrow-left-right"></i> Nginx</a>
<a href="#mysql" onclick="showPage('mysql',this); return false;"><i class="bi bi-database"></i> MySQL</a>
<a href="#wordpress" onclick="showPage('wordpress',this); return false;"><i class="bi bi-wordpress"></i> WordPress</a>
<a href="#laravel" onclick="showPage('laravel',this); return false;"><i class="bi bi-code-square"></i> Laravel</a>
<a href="#codeigniter" onclick="showPage('codeigniter',this); return false;"><i class="bi bi-braces"></i> CodeIgniter</a>
<a href="#php-projects" onclick="showPage('php-projects',this); return false;"><i class="bi bi-filetype-php"></i> PHP Projects</a>
<a href="#phpmyadmin" onclick="showPage('phpmyadmin',this); return false;"><i class="bi bi-database-gear"></i> phpMyAdmin</a>
<a href="#performance" onclick="showPage('performance',this); return false;"><i class="bi bi-speedometer2"></i> Performance</a>
```

with:

```html
<div class="nav-section">Server</div>
<a href="#nginx" onclick="showPage('nginx',this); return false;"><i class="bi bi-arrow-left-right"></i> Nginx</a>
<a href="#mysql" onclick="showPage('mysql',this); return false;"><i class="bi bi-database"></i> MySQL</a>
<a href="#phpmyadmin" onclick="showPage('phpmyadmin',this); return false;"><i class="bi bi-database-gear"></i> phpMyAdmin</a>
<a href="#performance" onclick="showPage('performance',this); return false;"><i class="bi bi-speedometer2"></i> Performance</a>
```

- [ ] **Step 2: Replace App Launcher card body markup with count and recent containers**

In each `launcher-*` card, keep the app name, description, and start line, then replace the action area with this pattern.

For WordPress:

```html
<div class="d-flex align-items-center justify-content-between mb-3">
  <span id="launcher-wordpress-count" class="svc-status status-unknown">Loading sites...</span>
</div>
<div id="launcher-wordpress-recent" class="mb-3" style="min-height:74px;"></div>
<div class="d-flex gap-2 flex-wrap"><button class="btn btn-sm btn-primary" onclick="appLauncherCreate('wordpress')"><i class="bi bi-plus-circle"></i> Create</button><button class="btn btn-sm btn-outline-secondary" onclick="appLauncherManage('wordpress')"><i class="bi bi-grid"></i> View All</button></div>
```

For Laravel:

```html
<div class="d-flex align-items-center justify-content-between mb-3">
  <span id="launcher-laravel-count" class="svc-status status-unknown">Loading apps...</span>
</div>
<div id="launcher-laravel-recent" class="mb-3" style="min-height:74px;"></div>
<div class="d-flex gap-2 flex-wrap"><button class="btn btn-sm btn-primary" onclick="appLauncherCreate('laravel')"><i class="bi bi-plus-circle"></i> Create</button><button class="btn btn-sm btn-outline-secondary" onclick="appLauncherManage('laravel')"><i class="bi bi-grid"></i> View All</button></div>
```

For CodeIgniter:

```html
<div class="d-flex align-items-center justify-content-between mb-3">
  <span id="launcher-codeigniter-count" class="svc-status status-unknown">Loading apps...</span>
</div>
<div id="launcher-codeigniter-recent" class="mb-3" style="min-height:74px;"></div>
<div class="d-flex gap-2 flex-wrap"><button class="btn btn-sm btn-primary" onclick="appLauncherCreate('codeigniter')"><i class="bi bi-plus-circle"></i> Create</button><button class="btn btn-sm btn-outline-secondary" onclick="appLauncherManage('codeigniter')"><i class="bi bi-grid"></i> View All</button></div>
```

For PHP Projects:

```html
<div class="d-flex align-items-center justify-content-between mb-3">
  <span id="launcher-php-projects-count" class="svc-status status-unknown">Loading projects...</span>
</div>
<div id="launcher-php-projects-recent" class="mb-3" style="min-height:74px;"></div>
<div class="d-flex gap-2 flex-wrap"><button class="btn btn-sm btn-primary" onclick="appLauncherCreate('php-projects')"><i class="bi bi-plus-circle"></i> Create</button><button class="btn btn-sm btn-outline-secondary" onclick="appLauncherManage('php-projects')"><i class="bi bi-grid"></i> View All</button></div>
```

- [ ] **Step 3: Update navigation helper so hidden app pages keep App Launcher active**

Replace `openAppLauncherTarget` with:

```javascript
function appLauncherLink() {
  return document.querySelector('.sidebar-nav a[href="#app-launcher"]');
}

function openAppLauncherTarget(appType, tabName) {
  if (!validPage(appType)) { toast('Target page not found', 'error'); return; }
  showPage(appType, appLauncherLink());
  const btn = document.querySelector(`#page-${appType} .custom-tabs button[onclick*="'${tabName}'"]`);
  if (!btn) { toast('Target tab not found', 'error'); return; }
  switchTab(appType, tabName, btn);
}
```

Keep `appLauncherCreate` and `appLauncherManage` mappings unchanged except that the button label now says `View All` in the markup.

- [ ] **Step 4: Load App Launcher summaries when App Launcher opens**

Add this line to `onPageLoad(name)`:

```javascript
if (name === 'app-launcher') { loadAppLauncherSummary(); }
```

- [ ] **Step 5: Add App Launcher summary rendering functions near the navigation helpers**

Add this block after `appLauncherManage`:

```javascript
const appLauncherSummaryConfig = {
  'wordpress': { endpoint: '/api/wordpress/sites', key: 'sites', noun: 'site', empty: 'No WordPress sites yet' },
  'laravel': { endpoint: '/api/laravel/apps', key: 'apps', noun: 'app', empty: 'No Laravel apps yet' },
  'codeigniter': { endpoint: '/api/codeigniter/apps', key: 'apps', noun: 'app', empty: 'No CodeIgniter apps yet' },
  'php-projects': { endpoint: '/api/php-projects/apps', key: 'apps', noun: 'project', empty: 'No PHP projects yet' },
};

async function loadAppLauncherSummary() {
  await Promise.all(Object.entries(appLauncherSummaryConfig).map(async ([type, config]) => {
    try {
      const r = await api(config.endpoint);
      if (!r.success) throw new Error(r.error || 'Error');
      renderAppLauncherCardSummary(type, { ...config, items: r[config.key] || [] });
    } catch (err) {
      const countEl = document.getElementById(`launcher-${type}-count`);
      const recentEl = document.getElementById(`launcher-${type}-recent`);
      if (countEl) { countEl.className = 'svc-status status-stopped'; countEl.textContent = 'Load failed'; }
      if (recentEl) recentEl.innerHTML = `<div class="empty-state" style="padding:10px;font-size:.78rem;"><i class="bi bi-exclamation-circle"></i>${esc(err.message || 'Failed to load')}</div>`;
    }
  }));
}

function renderAppLauncherCardSummary(type, data) {
  const countEl = document.getElementById(`launcher-${type}-count`);
  const recentEl = document.getElementById(`launcher-${type}-recent`);
  if (!countEl || !recentEl) return;
  const items = Array.isArray(data.items) ? data.items : [];
  const noun = items.length === 1 ? data.noun : `${data.noun}s`;
  countEl.className = items.length ? 'svc-status status-running' : 'svc-status status-unknown';
  countEl.textContent = `${items.length} ${noun}`;
  if (!items.length) {
    recentEl.innerHTML = `<div style="color:#6c7086;font-size:.8rem;line-height:1.35;">${esc(data.empty)}</div>`;
    return;
  }
  recentEl.innerHTML = items.slice(0, 3).map(item => {
    const url = launcherItemUrl(item);
    return `<div class="d-flex align-items-center justify-content-between gap-2 py-1" style="border-top:1px solid #2d3158;">
      <div style="min-width:0;">
        <div style="color:#cdd6f4;font-size:.82rem;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${esc(item.name || 'Untitled')}</div>
        <div style="color:#6c7086;font-size:.72rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${launcherItemMeta(item)}</div>
      </div>
      <div class="d-flex gap-1 flex-shrink-0">
        ${url ? `<a class="btn btn-sm btn-outline-secondary" style="padding:2px 7px;font-size:.72rem;" href="${url}" target="_blank">Open</a>` : ''}
        <button class="btn btn-sm btn-outline-primary" style="padding:2px 7px;font-size:.72rem;" onclick="appLauncherManage('${esc(type)}')">Manage</button>
      </div>
    </div>`;
  }).join('');
}

function launcherItemUrl(item) {
  return item && item.port ? `http://localhost:${esc(item.port)}/` : '';
}

function launcherItemMeta(item) {
  const parts = [];
  if (item.port) parts.push(`:${item.port}`);
  if (item.path) parts.push(item.path);
  if (!parts.length && item.db_name) parts.push(item.db_name);
  return esc(parts.join(' · ') || 'No port detected');
}
```

- [ ] **Step 6: Run task verification**

Run:

```bash
python3 -m unittest tests.test_app_launcher_frontend -v
python3 - <<'PY'
from pathlib import Path
html = Path('index.html').read_text()
start = html.index('<script>') + len('<script>')
end = html.rindex('</script>')
Path('/tmp/opencode/server-panel-inline.js').write_text(html[start:end])
PY
node --check "/tmp/opencode/server-panel-inline.js"
```

Expected: App Launcher tests report `OK`; Node exits `0` with no output.

- [ ] **Step 7: Commit frontend implementation**

Run:

```bash
git add index.html
git commit -m "Make app launcher the app dashboard"
```

Expected: one commit containing only `index.html`.

---

### Task 3: Documentation, Final Verification, Commit, Push

**Files:**
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes completed App Launcher dashboard frontend.
- Produces documented and pushed navigation/dashboard update.

- [ ] **Step 1: Update CLAUDE.md App Launcher section**

In `CLAUDE.md`, replace the current App Launcher section with:

```markdown
### App Launcher
- Single app hub for WordPress, Laravel, CodeIgniter, and PHP Projects
- Keeps app-specific pages out of the sidebar so future app types do not make navigation longer
- Shows app cards with requirements, default port range, installed counts, and up to three recent projects
- Create opens existing install forms; View All/Manage opens existing hidden app-specific management pages
- Full app lists, deletes, port changes, and advanced controls stay on the app-specific pages
```

- [ ] **Step 2: Run final verification**

Run:

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
git status --short
```

Expected:

```text
panel.py compiles
all unittest tests pass
all shell scripts pass bash -n
inline frontend JS passes node --check
git status shows only intended uncommitted CLAUDE.md and plan/spec files, if any
```

- [ ] **Step 3: Inspect git state before committing**

Run:

```bash
git status --short
git diff
git log --oneline -10
```

Expected: no unexpected worktree changes. Do not modify or revert unrelated user changes if any appear.

- [ ] **Step 4: Commit docs and plan**

Run:

```bash
git add CLAUDE.md docs/superpowers/specs/2026-07-26-app-launcher-navigation-design.md docs/superpowers/plans/2026-07-26-app-launcher-navigation-dashboard.md
git commit -m "Document app launcher dashboard navigation"
```

Expected: one docs/planning commit.

- [ ] **Step 5: Push**

Run:

```bash
git push
```

Expected: `origin/main` receives the design, plan, test, frontend, and docs commits.

---

## Self-Review

- Spec coverage: tasks cover sidebar cleanup, hidden app page routing, counts, recent items, existing APIs, no backend routes, no destructive App Launcher actions, docs, verification, and push.
- Placeholder scan: no TBD or incomplete implementation steps remain.
- Type consistency: `appLauncherLink`, `openAppLauncherTarget`, `loadAppLauncherSummary`, `renderAppLauncherCardSummary`, `launcherItemUrl`, and `launcherItemMeta` names are consistent across tests and implementation steps.
- Scope check: plan is a single frontend feature with docs and tests; no backend or broad redesign tasks are included.
