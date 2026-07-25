# App Launcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a unified App Launcher page for starting WordPress, Laravel, CodeIgniter, and PHP Project creation from one place.

**Architecture:** This is a frontend-only feature in `index.html`. It adds an App Launcher sidebar/page, cards for each app type, and small navigation helpers that reuse existing app-specific pages, tabs, and next-port loader functions.

**Tech Stack:** HTML, Bootstrap 5 classes, Bootstrap Icons, vanilla JavaScript, existing Python `unittest` frontend structure tests, Node syntax checking for inline JavaScript.

## Global Constraints

- Add a new sidebar item named **App Launcher**.
- The App Launcher is create-focused, not a replacement for existing detailed management pages.
- Keep existing app-specific sections for installed app lists, advanced controls, logs, deletes, and port changes.
- Reuse existing frontend install forms and backend install APIs.
- Do not create new backend install routes in this version.
- App cards: WordPress, Laravel, CodeIgniter, PHP Project.
- Create buttons navigate to the existing install tab for each app type.
- Manage buttons navigate to the existing installed-apps tab for each app type.

---

## File Structure

- Modify `index.html`: add App Launcher sidebar item, page markup, page title, page loader handling, and navigation helper functions.
- Create `tests/test_app_launcher_frontend.py`: frontend structure tests for the App Launcher page, cards, and helper routes.
- Modify `CLAUDE.md`: document the App Launcher feature after implementation.

---

### Task 1: Add App Launcher Frontend Tests

**Files:**
- Create: `tests/test_app_launcher_frontend.py`

**Interfaces:**
- Produces tests that require `page-app-launcher`, `openAppLauncherTarget`, `appLauncherCreate`, and `appLauncherManage` to exist in `index.html`.
- Produces tests that require card IDs `launcher-wordpress`, `launcher-laravel`, `launcher-codeigniter`, and `launcher-php-projects`.

- [ ] **Step 1: Write failing frontend tests**

Create `tests/test_app_launcher_frontend.py`:

```python
import os
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class AppLauncherFrontendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(PROJECT_ROOT, "index.html"), encoding="utf-8") as f:
            cls.html = f.read()

    def test_sidebar_page_and_title_exist(self):
        for text in [
            "showPage('app-launcher',this)",
            'id="page-app-launcher"',
            "'app-launcher':'App Launcher'",
        ]:
            self.assertIn(text, self.html)

    def test_all_launcher_cards_exist(self):
        for card_id in [
            "launcher-wordpress",
            "launcher-laravel",
            "launcher-codeigniter",
            "launcher-php-projects",
        ]:
            self.assertIn(card_id, self.html)

        for label in [
            "WordPress",
            "Laravel",
            "CodeIgniter",
            "PHP Project",
            "Starts near 8090",
            "Starts near 8100",
            "Starts near 8200",
            "Starts near 8300",
        ]:
            self.assertIn(label, self.html)

    def test_navigation_helpers_exist_and_target_existing_pages(self):
        for function_name in [
            "function openAppLauncherTarget(",
            "function appLauncherCreate(",
            "function appLauncherManage(",
        ]:
            self.assertIn(function_name, self.html)

        for target in [
            "wordpress",
            "laravel",
            "codeigniter",
            "php-projects",
            "install",
            "sites",
            "apps",
        ]:
            self.assertIn(target, self.html)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python3 -m unittest tests.test_app_launcher_frontend -v`

Expected: FAIL because the App Launcher page and helper functions are not in `index.html` yet.

---

### Task 2: Add App Launcher Page And Navigation

**Files:**
- Modify: `index.html`

**Interfaces:**
- Consumes existing `showPage(name, el)`, `switchTab(page, tab, el)`, `loadNextPort`, `loadWpPluginLibrary`, `loadLaravelNextPort`, `loadCodeIgniterNextPort`, and `loadPhpProjectNextPort`.
- Produces `openAppLauncherTarget(page: string, tab: string) -> void`.
- Produces `appLauncherCreate(type: string) -> void`.
- Produces `appLauncherManage(type: string) -> void`.

- [ ] **Step 1: Add sidebar item**

Add under Dashboard in the Overview section:

```html
<a href="#app-launcher" onclick="showPage('app-launcher',this); return false;"><i class="bi bi-rocket-takeoff"></i> App Launcher</a>
```

- [ ] **Step 2: Add page markup**

Add `page-app-launcher` near the Dashboard page, before service-specific pages:

```html
<div id="page-app-launcher" class="page">
  <div class="d-flex align-items-center justify-content-between mb-4">
    <div>
      <div class="section-title mb-1"><i class="bi bi-rocket-takeoff"></i> App Launcher</div>
      <div style="font-size:.86rem;color:#6c7086;">Create a new local site or app from one place.</div>
    </div>
  </div>
  <div class="row g-3">
    <div class="col-md-6 col-xl-3">
      <div id="launcher-wordpress" class="service-card h-100">
        <div class="section-title"><i class="bi bi-wordpress"></i> WordPress</div>
        <p style="color:#a6adc8;font-size:.86rem;min-height:58px;">Create a WordPress site with database, admin user, Nginx site, and optional plugins.</p>
        <div style="font-size:.76rem;color:#6c7086;margin-bottom:14px;">Starts near 8090 · MySQL required</div>
        <div class="d-flex gap-2 flex-wrap"><button class="btn btn-sm btn-primary" onclick="appLauncherCreate('wordpress')"><i class="bi bi-plus-circle"></i> Create</button><button class="btn btn-sm btn-outline-secondary" onclick="appLauncherManage('wordpress')"><i class="bi bi-grid"></i> Manage</button></div>
      </div>
    </div>
    <div class="col-md-6 col-xl-3">
      <div id="launcher-laravel" class="service-card h-100">
        <div class="section-title"><i class="bi bi-code-square"></i> Laravel</div>
        <p style="color:#a6adc8;font-size:.86rem;min-height:58px;">Create a Laravel app with Composer, database credentials, and an Nginx public webroot.</p>
        <div style="font-size:.76rem;color:#6c7086;margin-bottom:14px;">Starts near 8100 · Composer required</div>
        <div class="d-flex gap-2 flex-wrap"><button class="btn btn-sm btn-primary" onclick="appLauncherCreate('laravel')"><i class="bi bi-plus-circle"></i> Create</button><button class="btn btn-sm btn-outline-secondary" onclick="appLauncherManage('laravel')"><i class="bi bi-grid"></i> Manage</button></div>
      </div>
    </div>
    <div class="col-md-6 col-xl-3">
      <div id="launcher-codeigniter" class="service-card h-100">
        <div class="section-title"><i class="bi bi-braces"></i> CodeIgniter</div>
        <p style="color:#a6adc8;font-size:.86rem;min-height:58px;">Create a CodeIgniter 4 app with Composer, `.env`, database, and Nginx public webroot.</p>
        <div style="font-size:.76rem;color:#6c7086;margin-bottom:14px;">Starts near 8200 · Composer required</div>
        <div class="d-flex gap-2 flex-wrap"><button class="btn btn-sm btn-primary" onclick="appLauncherCreate('codeigniter')"><i class="bi bi-plus-circle"></i> Create</button><button class="btn btn-sm btn-outline-secondary" onclick="appLauncherManage('codeigniter')"><i class="bi bi-grid"></i> Manage</button></div>
      </div>
    </div>
    <div class="col-md-6 col-xl-3">
      <div id="launcher-php-projects" class="service-card h-100">
        <div class="section-title"><i class="bi bi-filetype-php"></i> PHP Project</div>
        <p style="color:#a6adc8;font-size:.86rem;min-height:58px;">Create a plain PHP project from Blank, PHP Only, or PHP + DB templates.</p>
        <div style="font-size:.76rem;color:#6c7086;margin-bottom:14px;">Starts near 8300 · DB optional</div>
        <div class="d-flex gap-2 flex-wrap"><button class="btn btn-sm btn-primary" onclick="appLauncherCreate('php-projects')"><i class="bi bi-plus-circle"></i> Create</button><button class="btn btn-sm btn-outline-secondary" onclick="appLauncherManage('php-projects')"><i class="bi bi-grid"></i> Manage</button></div>
      </div>
    </div>
  </div>
</div>
```

- [ ] **Step 3: Add page title and navigation helpers**

Add `'app-launcher':'App Launcher'` to `pageTitles`.

Add JavaScript functions near navigation helpers:

```javascript
function openAppLauncherTarget(page, tab) {
  const link = document.querySelector(`.sidebar-nav a[href="#${page}"]`);
  if (!validPage(page)) { toast('Target page not found', 'error'); return; }
  showPage(page, link);
  const btn = document.querySelector(`#page-${page} .custom-tabs button[onclick*="'${tab}'"]`);
  if (!btn) { toast('Target tab not found', 'error'); return; }
  switchTab(page, tab, btn);
}

function appLauncherCreate(type) {
  const targets = {
    wordpress: ['wordpress', 'install'],
    laravel: ['laravel', 'install'],
    codeigniter: ['codeigniter', 'install'],
    'php-projects': ['php-projects', 'install'],
  };
  const target = targets[type];
  if (!target) { toast('Unknown app type', 'error'); return; }
  openAppLauncherTarget(target[0], target[1]);
}

function appLauncherManage(type) {
  const targets = {
    wordpress: ['wordpress', 'sites'],
    laravel: ['laravel', 'apps'],
    codeigniter: ['codeigniter', 'apps'],
    'php-projects': ['php-projects', 'apps'],
  };
  const target = targets[type];
  if (!target) { toast('Unknown app type', 'error'); return; }
  openAppLauncherTarget(target[0], target[1]);
}
```

- [ ] **Step 4: Verify App Launcher frontend**

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

Expected: tests report `OK`; Node exits `0` with no output.

---

### Task 3: Documentation, Verification, Commit, Push

**Files:**
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes completed App Launcher frontend.
- Produces documented and pushed App Launcher feature.

- [ ] **Step 1: Update docs**

Add a short **App Launcher** feature section to `CLAUDE.md`:

```markdown
### App Launcher
- Unified create-focused page for WordPress, Laravel, CodeIgniter, and PHP Projects
- Shows app cards with requirements, default port range, Create, and Manage actions
- Reuses existing app-specific install forms and management pages
```

- [ ] **Step 2: Run final verification**

Run:

```bash
python3 -m py_compile panel.py
python3 -m unittest discover -s tests -v
bash -n setup-sudo.sh wp-install-helper.sh wp-delete-helper.sh laravel-helper.sh codeigniter-helper.sh php-project-helper.sh perf-helper.sh start-panel.sh
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
```

- [ ] **Step 3: Commit and push**

Run:

```bash
git status --short
git diff
git log --oneline -10
git add index.html CLAUDE.md tests/test_app_launcher_frontend.py docs/superpowers/plans/2026-07-25-app-launcher.md
git commit -m "Add app launcher page"
git push
```

Expected: push updates `origin/main` with the design spec commit and implementation commit.

---

## Self-Review

- Spec coverage: this plan covers the App Launcher page, cards, Create/Manage navigation, frontend-only scope, docs, tests, verification, commit, and push.
- Placeholder scan: no TBD/TODO/fill-in-later steps remain.
- Type consistency: page ID, helper function names, card IDs, and app type keys are consistent across tasks.
