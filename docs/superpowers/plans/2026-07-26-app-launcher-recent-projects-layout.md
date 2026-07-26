# App Launcher Recent Projects Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep App Launcher cards compact by moving recent project rows into a grouped Recent Projects section below the cards.

**Architecture:** This is a frontend-only change in `index.html` with static frontend structure tests in `tests/test_app_launcher_frontend.py`. Existing app list APIs, hidden app pages, and App Launcher routing stay unchanged. `renderAppLauncherCardSummary(type, items)` continues to update the count badge and now renders project rows into grouped containers outside the app cards.

**Tech Stack:** HTML, Bootstrap 5 classes, Bootstrap Icons, vanilla JavaScript, Python `unittest` frontend structure tests, Node inline JavaScript syntax checking.

## Global Constraints

- Keep App Launcher cards compact and equal-height by moving recent project details out of each app card into a dedicated grouped section below the cards.
- Top cards should show only app name/icon, short description, default port/requirement line, installed count badge, `Create`, and `View All`.
- Top cards should not render recent project rows or `Open`/per-project `Manage` actions.
- Add a dedicated **Recent Projects** section below the card grid.
- The Recent Projects section should be grouped by app type: WordPress, Laravel, CodeIgniter, PHP Projects.
- Each group should show up to three recent/detected projects for that app type.
- Each project row should show project name, port/path summary, `Open` when a port exists, and `Manage` for the hidden installed-apps/sites tab.
- If an app type has no projects, show compact empty text inside that group.
- Keep existing backend APIs unchanged.
- Keep App Launcher summary loading from existing APIs: `/api/wordpress/sites`, `/api/laravel/apps`, `/api/codeigniter/apps`, and `/api/php-projects/apps`.
- Keep `launcher-*-count` elements inside the top app cards.
- Move `launcher-*-recent` containers out of the app cards and into the new Recent Projects section.
- Keep `renderAppLauncherCardSummary(type, items)` responsible for updating both the top card count and the matching recent-project group.
- Keep `Open` links using `target="_blank" rel="noopener noreferrer"`.
- Do not add delete/destructive actions to App Launcher.
- Do not duplicate full management tables in App Launcher.
- Do not add backend routes.

---

## File Structure

- Modify `tests/test_app_launcher_frontend.py`: update static structure tests so recent containers are required outside cards and the grouped Recent Projects section is required.
- Modify `index.html`: remove recent containers from top cards, add grouped Recent Projects section below the card grid, and keep summary rendering pointed at the moved containers.
- Modify `CLAUDE.md`: update App Launcher documentation to mention recent projects are grouped below the app cards.

---

### Task 1: Update Recent Projects Layout Tests

**Files:**
- Modify: `tests/test_app_launcher_frontend.py`

**Interfaces:**
- Produces tests requiring `id="launcher-recent-projects"` in `index.html`.
- Produces tests requiring `launcher-*-recent` containers to be outside each `launcher-*` card block.
- Keeps existing tests requiring `launcher-*-count` inside each top card.

- [ ] **Step 1: Add helper methods for card and recent-section extraction**

Add these helper methods inside `AppLauncherFrontendTests`, after `assert_page_title_entry`:

```python
    def launcher_card_block(self, card_id):
        start = self.html.index(f'id="{card_id}"')
        next_card = re.search(
            r'id="launcher-(?:wordpress|laravel|codeigniter|php-projects)"',
            self.html[start + 1:],
        )
        app_end = self.html.index('id="launcher-recent-projects"')
        end = start + 1 + next_card.start() if next_card else app_end
        return self.html[start:end]

    def recent_projects_section(self):
        start = self.html.index('id="launcher-recent-projects"')
        end = self.html.index('<!-- ── NGINX', start)
        return self.html[start:end]
```

- [ ] **Step 2: Replace the placeholder test with card-count and external-recent assertions**

Replace `test_all_launcher_cards_have_dashboard_placeholders` with:

```python
    def test_cards_keep_counts_and_recent_containers_move_below_cards(self):
        self.assertIn('id="launcher-recent-projects"', self.html)
        recent_section = self.recent_projects_section()

        for app_type, card_id, label, port, _, noun in self.LAUNCHER_APPS:
            card_block = self.launcher_card_block(card_id)

            self.assertIn(card_id, self.html)
            self.assertIn(label, card_block)
            self.assertIn(f"Starts near {port}", card_block)
            self.assertIn(f'id="launcher-{app_type}-count"', card_block)
            self.assertNotIn(f'id="launcher-{app_type}-recent"', card_block)
            self.assertIn(f'id="launcher-{app_type}-recent"', recent_section)
            self.assertIn(noun, self.html)
```

- [ ] **Step 3: Add a test for grouped Recent Projects section labels**

Add this test after `test_cards_keep_counts_and_recent_containers_move_below_cards`:

```python
    def test_recent_projects_section_is_grouped_by_app_type(self):
        recent_section = self.recent_projects_section()

        for text in [
            "Recent Projects",
            "WordPress",
            "Laravel",
            "CodeIgniter",
            "PHP Projects",
            "No WordPress sites yet",
            "No Laravel apps yet",
            "No CodeIgniter apps yet",
            "No PHP projects yet",
        ]:
            self.assertIn(text, recent_section)
```

- [ ] **Step 4: Update the recent action test to look in the recent section, not card blocks**

Replace the per-card loop at the end of `test_launcher_recent_items_render_manage_actions`:

```python
        for app_type, card_id, _, _, _, _ in self.LAUNCHER_APPS:
            escaped_app_type = re.escape(app_type)
            escaped_card_id = re.escape(card_id)

            self.assert_html_pattern(
                rf'id="{escaped_card_id}"{self.LAUNCHER_CARD_BOUNDARY}'
                rf'id="launcher-{escaped_app_type}-recent"'
            )
```

with:

```python
        recent_section = self.recent_projects_section()
        for app_type, _, _, _, _, _ in self.LAUNCHER_APPS:
            self.assertIn(f'id="launcher-{app_type}-recent"', recent_section)
```

- [ ] **Step 5: Run tests and verify the new layout tests fail**

Run:

```bash
python3 -m unittest tests.test_app_launcher_frontend -v
```

Expected: `FAILED` because recent containers are still inside the app cards and `launcher-recent-projects` does not exist.

- [ ] **Step 6: Commit failing tests**

Run:

```bash
git add tests/test_app_launcher_frontend.py
git commit -m "Update app launcher recent layout tests"
```

Expected: one test-only commit.

---

### Task 2: Move Recent Projects Below Cards

**Files:**
- Modify: `index.html`

**Interfaces:**
- Consumes tests from Task 1.
- Keeps existing `renderAppLauncherCardSummary(type, items) -> void`.
- Keeps existing `launcherItemUrl(item) -> string` and `launcherItemMeta(item) -> string`.

- [ ] **Step 1: Remove recent containers from top cards**

In each app card, remove only these lines:

```html
<div id="launcher-wordpress-recent" class="mb-3" style="min-height:74px;"></div>
<div id="launcher-laravel-recent" class="mb-3" style="min-height:74px;"></div>
<div id="launcher-codeigniter-recent" class="mb-3" style="min-height:74px;"></div>
<div id="launcher-php-projects-recent" class="mb-3" style="min-height:74px;"></div>
```

Leave each card's count badge, description, requirement line, `Create`, and `View All` buttons unchanged.

- [ ] **Step 2: Add grouped Recent Projects section below the card row**

Immediately after the closing `</div>` for the app card row and before the closing `</div>` for `page-app-launcher`, add:

```html
        <div id="launcher-recent-projects" class="mt-4">
          <div class="d-flex align-items-center justify-content-between mb-3">
            <div>
              <div class="section-title mb-1"><i class="bi bi-clock-history"></i> Recent Projects</div>
              <div style="font-size:.8rem;color:#6c7086;">Recent detected projects are grouped by app type. Full controls stay in each app's management page.</div>
            </div>
          </div>
          <div class="row g-3">
            <div class="col-md-6 col-xl-3">
              <div class="service-card h-100">
                <div class="section-title"><i class="bi bi-wordpress"></i> WordPress</div>
                <div id="launcher-wordpress-recent" class="mt-3"></div>
              </div>
            </div>
            <div class="col-md-6 col-xl-3">
              <div class="service-card h-100">
                <div class="section-title"><i class="bi bi-code-square"></i> Laravel</div>
                <div id="launcher-laravel-recent" class="mt-3"></div>
              </div>
            </div>
            <div class="col-md-6 col-xl-3">
              <div class="service-card h-100">
                <div class="section-title"><i class="bi bi-braces"></i> CodeIgniter</div>
                <div id="launcher-codeigniter-recent" class="mt-3"></div>
              </div>
            </div>
            <div class="col-md-6 col-xl-3">
              <div class="service-card h-100">
                <div class="section-title"><i class="bi bi-filetype-php"></i> PHP Projects</div>
                <div id="launcher-php-projects-recent" class="mt-3"></div>
              </div>
            </div>
          </div>
        </div>
```

- [ ] **Step 3: Keep render function behavior, adjust row spacing only if needed**

Keep `renderAppLauncherCardSummary(type, items)` using:

```javascript
const countEl = document.getElementById(`launcher-${type}-count`);
const recentEl = document.getElementById(`launcher-${type}-recent`);
```

No API or routing changes are needed because the recent container IDs stay the same after being moved.

- [ ] **Step 4: Run task verification**

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

- [ ] **Step 5: Commit frontend implementation**

Run:

```bash
git add index.html
git commit -m "Move app launcher recent projects below cards"
```

Expected: one commit containing only `index.html`.

---

### Task 3: Documentation, Final Verification, Commit, Push

**Files:**
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes completed App Launcher recent-projects layout.
- Produces documented and pushed layout update.

- [ ] **Step 1: Update CLAUDE.md App Launcher section**

In `CLAUDE.md`, replace the App Launcher bullet:

```markdown
- Shows app cards with requirements, default port range, installed counts, and up to three recent projects
```

with:

```markdown
- Shows compact app cards with requirements, default port range, and installed counts
- Shows up to three recent projects per app type in a grouped Recent Projects section below the cards
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
git add CLAUDE.md docs/superpowers/specs/2026-07-26-app-launcher-recent-projects-layout-design.md docs/superpowers/plans/2026-07-26-app-launcher-recent-projects-layout.md
git commit -m "Document app launcher recent projects layout"
```

Expected: one docs/planning commit.

- [ ] **Step 5: Push**

Run:

```bash
git push
```

Expected: `origin/main` receives the recent-projects layout spec, plan, tests, frontend, and docs commits.

---

## Self-Review

- Spec coverage: tasks cover compact cards, grouped Recent Projects below cards, moved recent containers, existing APIs, no backend changes, no destructive actions, docs, verification, and push.
- Placeholder scan: no incomplete implementation steps remain.
- Type consistency: `renderAppLauncherCardSummary(type, items)`, `launcherItemUrl(item)`, and `launcherItemMeta(item)` stay unchanged and match existing code/tests.
- Scope check: plan changes App Launcher layout only; it does not add backend routes, search/filtering, sorting, or full project tables.
