# WordPress Auto-Login Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-site install, activate, deactivate, remove, and native-cookie auto-login controls for a temporary normal WordPress plugin.

**Architecture:** Store one small plugin source in the panel repository. The backend installs or removes it through the existing WordPress privileged helper, activates it through a local PHP bootstrap, and creates one-use short-lived login tokens through WordPress. The browser opens the plugin endpoint, which calls native `wp_set_auth_cookie()` and redirects to `/wp-admin/`.

**Tech Stack:** Python `ThreadingHTTPServer`, vanilla JavaScript, PHP WordPress plugin, Bash helper, Python `unittest`.

## Global Constraints

- Never send saved WordPress passwords to the auto-login endpoint.
- Tokens expire after 60 seconds and are deleted after one use.
- Plugin must be removable before site backup.
- Site paths must pass existing safe WordPress path validation.
- Existing native password login remains available.

---

### Task 1: Add Plugin Source

**Files:**
- Create: `wp-auto-login-plugin.php`
- Test: `tests/test_wordpress_auto_login_plugin.py`

- [ ] Write tests for token expiry, one-use consumption, native cookie call, and absence of password handling.
- [ ] Run `python3 -m unittest tests.test_wordpress_auto_login_plugin` and verify failure.
- [ ] Add plugin with activation cleanup, token creation helper, token-consuming endpoint, `wp_set_auth_cookie()`, admin redirect, and uninstall cleanup.
- [ ] Run targeted tests and verify pass.

### Task 2: Add Privileged Plugin Lifecycle Operations

**Files:**
- Modify: `wp-install-helper.sh`
- Modify: `setup-sudo.sh`
- Test: `tests/test_wordpress_auto_login_backend.py`

- [ ] Add `--auto-login-install`, `--auto-login-disable`, and `--auto-login-remove` actions.
- [ ] Validate site path and plugin path inside helper before every operation.
- [ ] Install source from panel repository, activate/deactivate through WordPress PHP, and delete plugin files on remove.
- [ ] Add sudo rule coverage for helper wildcard already used by panel.
- [ ] Add failing backend assertions for safe command construction and action routing.
- [ ] Run targeted tests and verify pass.

### Task 3: Add Backend APIs

**Files:**
- Modify: `panel.py`
- Test: `tests/test_wordpress_auto_login_backend.py`

- [ ] Add plugin status to `get_wp_sites()`.
- [ ] Add POST route `/api/wordpress/auto-login` for `install`, `enable`, `disable`, and `remove`.
- [ ] Add POST route `/api/wordpress/auto-login/token` that runs a temporary PHP bootstrap and returns only a login URL.
- [ ] Validate site path, admin username, action, and plugin status before running commands.
- [ ] Ensure temporary PHP files are deleted in `finally` blocks.
- [ ] Run backend tests and full test suite.

### Task 4: Add Per-Site Controls

**Files:**
- Modify: `index.html`
- Test: `tests/test_wordpress_auto_login_frontend.py`

- [ ] Render status and buttons: `Enable`, `Disable`, `Remove`, and `WP Admin Auto Login`.
- [ ] Disable auto-login button when plugin is inactive or absent.
- [ ] Request token from backend and open returned URL in a user-created popup.
- [ ] Keep copy/paste native login controls unchanged.
- [ ] Add confirmation before remove and warning that remove is required before backup.
- [ ] Run frontend tests and full suite.

### Task 5: Document Backup Safety

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`

- [ ] Document plugin lifecycle and explicit remove-before-backup requirement.
- [ ] Document token expiry and native-cookie behavior.
- [ ] Run full test suite and `git diff --check`.
