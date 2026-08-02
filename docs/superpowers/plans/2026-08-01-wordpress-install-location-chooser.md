# WordPress Install Location Chooser Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a WordPress install location chooser that generates safe install paths for `/var/www`, `/opt`, and the current user's `~/local` directory.

**Architecture:** This is a frontend form enhancement in `index.html`. The backend and sudo helper remain the validation and enforcement layers, with existing helper tests covering the `~/local` allowlist.

**Tech Stack:** Python `unittest`, vanilla JavaScript, Bootstrap-themed static HTML.

## Global Constraints

- No new external dependencies.
- Preserve the existing Bootstrap dark form style.
- Keep the install path input visible and editable.
- Safe roots must match helper behavior: `/var/www/*`, `/opt/*`, and `/home/<panel-user>/local/*`.

---

### Task 1: WordPress Location Chooser

**Files:**
- Modify: `index.html`
- Test: `tests/test_wordpress_location_chooser_frontend.py`

**Interfaces:**
- Consumes: existing `wpAutoFill()` called by the WordPress site-name input.
- Produces: `getWpInstallBase()` returning a string base path and updated `wpAutoFill()` path generation.

- [ ] **Step 1: Write the failing frontend source test**

Create `tests/test_wordpress_location_chooser_frontend.py` with assertions that `index.html` contains `wp-install-location`, the three expected location options, and `getWpInstallBase()`.

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest tests.test_wordpress_location_chooser_frontend`

Expected: FAIL because `wp-install-location` is not present yet.

- [ ] **Step 3: Add the chooser markup**

In `index.html`, insert an `Install Location` select before the existing `Install Path` field:

```html
<select id="wp-install-location" class="input-dark" onchange="wpAutoFill(true)">
  <option value="/var/www" selected>/var/www</option>
  <option value="/opt">/opt</option>
  <option value="home-local">~/local</option>
</select>
```

- [ ] **Step 4: Add path-generation logic**

Update `wpAutoFill()` to call `getWpInstallBase()` and generate `${base}/${name}`. Add `getWpInstallBase()` using `window.__PANEL_USER__ || 'vjranga'` only as a local fallback if the panel does not expose a username.

- [ ] **Step 5: Run targeted tests**

Run: `python3 -m unittest tests.test_wordpress_location_chooser_frontend tests.test_wordpress_custom_path`

Expected: OK.

- [ ] **Step 6: Run all tests**

Run: `python3 -m unittest discover -s tests`

Expected: OK.
