import os
import re
import subprocess
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ProjectsFrontendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(PROJECT_ROOT, "index.html"), encoding="utf-8") as f:
            cls.html = f.read()

        sidebar_start = cls.html.index('<nav class="sidebar-nav')
        sidebar_end = cls.html.index('</nav>', sidebar_start)
        cls.sidebar = cls.html[sidebar_start:sidebar_end]

    def test_sidebar_item_placed_right_after_app_launcher(self):
        self.assertIn('href="#projects"', self.sidebar)
        self.assertIn('bi-kanban', self.sidebar)
        self.assertIn("showPage('projects',this)", self.sidebar)

        # Ensure Projects item is placed right after App Launcher item
        launcher_pos = self.sidebar.find('href="#app-launcher"')
        projects_pos = self.sidebar.find('href="#projects"')
        server_sec_pos = self.sidebar.find('<div class="nav-section">Server</div>')

        self.assertNotEqual(launcher_pos, -1, "Missing app-launcher in sidebar")
        self.assertNotEqual(projects_pos, -1, "Missing projects in sidebar")
        self.assertTrue(launcher_pos < projects_pos < server_sec_pos,
                        "Projects link must be right after App Launcher in Overview section")

    def test_page_projects_and_page_titles_exist(self):
        self.assertIn('id="page-projects"', self.html)
        self.assertRegex(self.html, r"projects\s*:\s*['\"]Projects['\"]")
        self.assertIn("if (name === 'projects')", self.html)
        self.assertIn("loadProjects()", self.html)

    def test_toolbar_elements_exist(self):
        self.assertIn('id="projects-search-input"', self.html)
        self.assertIn('oninput="filterProjects()"', self.html)
        self.assertIn('onclick="openProjectModal()"', self.html)
        self.assertIn('id="projects-list-container"', self.html)

    def test_modal_elements_and_fields_exist(self):
        self.assertIn('id="project-modal"', self.html)
        self.assertIn('id="project-form-name"', self.html)
        self.assertIn('id="project-form-client"', self.html)
        self.assertIn('id="project-form-status"', self.html)
        self.assertIn('id="project-form-vault-path"', self.html)
        self.assertIn('id="project-form-notes"', self.html)
        self.assertIn('id="project-add-part-btn"', self.html)
        self.assertIn('id="project-modal-parts-container"', self.html)
        self.assertIn('onclick="saveProject()"', self.html)
        self.assertIn('onclick="closeProjectModal()"', self.html)

    def test_javascript_functions_exist(self):
        required_functions = [
            "function sanitizeHttpUrl(",
            "function formatGitRepoUrl(",
            "function copyToClipboard(",
            "function copyFromElement(",
            "function projectStatusBadge(",
            "function projectRoleBadge(",
            "async function fetchLocalSites(",
            "function buildLocalSiteSelectOptions(",
            "function onLinkLocalSiteSelect(",
            "function renderProjectPartFormRow(",
            "function addProjectPart(",
            "function removeProjectPart(",
            "async function openProjectModal(",
            "function closeProjectModal(",
            "async function saveProject(",
            "function deleteProject(",
            "async function loadProjects(",
            "function filterProjects(",
            "function projectMatchesSearch(",
            "function renderProjects(",
            "function renderProjectCard(",
            "function renderProjectPartRow(",
        ]
        for fn in required_functions:
            self.assertIn(fn, self.html, f"Missing function: {fn}")

    def test_git_url_to_https_conversion_node(self):
        # Extract sanitizeHttpUrl and formatGitRepoUrl from index.html
        start = self.html.index("function sanitizeHttpUrl(url)")
        end = self.html.index("function copyToClipboard(", start)
        code = self.html[start:end]

        test_script = code + """
const assert = require('node:assert/strict');

// git@ SSH form conversions
assert.equal(formatGitRepoUrl('git@github.com:facebook/react.git'), 'https://github.com/facebook/react');
assert.equal(formatGitRepoUrl('git@github.com:owner/repo'), 'https://github.com/owner/repo');
assert.equal(formatGitRepoUrl('git@gitlab.com:org/subgroup/project.git'), 'https://gitlab.com/org/subgroup/project');
assert.equal(formatGitRepoUrl('git@bitbucket.org:user/repo.git'), 'https://bitbucket.org/user/repo');
assert.equal(formatGitRepoUrl('git@custom-host.org:team/repo'), 'https://custom-host.org/team/repo');

// https:// remains valid https://
assert.equal(formatGitRepoUrl('https://github.com/facebook/react'), 'https://github.com/facebook/react');
assert.equal(formatGitRepoUrl('https://gitlab.com/org/repo.git'), 'https://gitlab.com/org/repo.git');

// Invalid or non-http schemes return empty string
assert.equal(formatGitRepoUrl('javascript:alert(1)'), '');
assert.equal(formatGitRepoUrl('ssh://git@github.com/repo'), '');
assert.equal(formatGitRepoUrl(''), '');
assert.equal(formatGitRepoUrl(null), '');
"""
        run = subprocess.run(["node", "-e", test_script], capture_output=True, text=True, timeout=5)
        self.assertEqual(run.returncode, 0, run.stderr)

    def test_non_http_urls_are_not_linked_node(self):
        start = self.html.index("function sanitizeHttpUrl(url)")
        end = self.html.index("function copyToClipboard(", start)
        code = self.html[start:end]

        test_script = code + """
const assert = require('node:assert/strict');

assert.equal(sanitizeHttpUrl('http://localhost:8080/'), 'http://localhost:8080/');
assert.equal(sanitizeHttpUrl('https://example.com/site'), 'https://example.com/site');
assert.equal(sanitizeHttpUrl('javascript:alert(1)'), '');
assert.equal(sanitizeHttpUrl('data:text/html,<script>alert(1)</script>'), '');
assert.equal(sanitizeHttpUrl('file:///etc/passwd'), '');
assert.equal(sanitizeHttpUrl('ftp://example.com'), '');
assert.equal(sanitizeHttpUrl('//example.com'), '');
assert.equal(sanitizeHttpUrl('not-a-url'), '');
assert.equal(sanitizeHttpUrl(''), '');
assert.equal(sanitizeHttpUrl(null), '');
"""
        run = subprocess.run(["node", "-e", test_script], capture_output=True, text=True, timeout=5)
        self.assertEqual(run.returncode, 0, run.stderr)

    def test_part_row_rendering_skips_non_http_urls_node(self):
        # Extract sanitizeHttpUrl, formatGitRepoUrl, esc, projectRoleBadge, and renderProjectPartRow
        start_fn = self.html.index("function sanitizeHttpUrl(url)")
        end_fn = self.html.index("function copyToClipboard(", start_fn)

        start_badge = self.html.index("function projectRoleBadge(role)")
        end_badge = self.html.index("async function fetchLocalSites(", start_badge)

        start_render = self.html.index("function renderProjectPartRow(part)")
        end_render = self.html.index("// ══ Utility", start_render)

        start_esc = self.html.index("function esc(s)")
        end_esc = self.html.index("// ══ Theme", start_esc)

        test_script = (
            self.html[start_esc:end_esc]
            + self.html[start_fn:end_fn]
            + self.html[start_badge:end_badge]
            + self.html[start_render:end_render]
            + """
const assert = require('node:assert/strict');

// Part with malicious / non-http URLs
const dangerousPart = {
  role: 'wordpress',
  label: 'API',
  local_url: 'javascript:alert("local")',
  live_url: 'data:text/html,<script>alert("live")</script>',
  staging_url: 'file:///etc/passwd',
  git_url: 'javascript:alert("git")',
  hosting_url: 'ftp://hosting.example.com',
};

const html = renderProjectPartRow(dangerousPart);
assert.ok(!html.includes('href="javascript:'), 'Must not link javascript:');
assert.ok(!html.includes('href="data:'), 'Must not link data:');
assert.ok(!html.includes('href="file:'), 'Must not link file:');
assert.ok(!html.includes('href="ftp:'), 'Must not link ftp:');
assert.ok(!html.includes('btn-compact"><i class="bi bi-laptop"></i> Local</a>'), 'No Local button for invalid url');
assert.ok(!html.includes('Live</a>'), 'No Live button for invalid url');
assert.ok(!html.includes('Staging</a>'), 'No Staging button for invalid url');
assert.ok(!html.includes('Repo</a>'), 'No Repo button for invalid url');
assert.ok(!html.includes('Hosting</a>'), 'No Hosting button for invalid url');

// Part with valid URLs
const validPart = {
  role: 'wordpress',
  label: 'Blog',
  local_url: 'http://localhost:8080/',
  live_url: 'https://example.com',
  staging_url: 'https://staging.example.com',
  git_url: 'git@github.com:myorg/myrepo.git',
  hosting_url: 'https://dash.cloudflare.com',
  hosting_name: 'Cloudflare',
  local_running: true,
};

const validHtml = renderProjectPartRow(validPart);
assert.ok(validHtml.includes('href="http://localhost:8080/"'), 'Must link local url');
assert.ok(validHtml.includes('href="https://example.com"'), 'Must link live url');
assert.ok(validHtml.includes('href="https://staging.example.com"'), 'Must link staging url');
assert.ok(validHtml.includes('href="https://github.com/myorg/myrepo"'), 'Must convert git@ to https repo link');
assert.ok(validHtml.includes('href="https://dash.cloudflare.com"'), 'Must link hosting url');
assert.ok(validHtml.includes('target="_blank" rel="noopener noreferrer"'), 'Must open in new tab with noopener noreferrer');
assert.ok(validHtml.includes('dot-green'), 'Must show green dot when local_running is true');
"""
        )
        run = subprocess.run(["node", "-e", test_script], capture_output=True, text=True, timeout=5)
        self.assertEqual(run.returncode, 0, run.stderr)

    def test_search_filtering_logic_node(self):
        start = self.html.index("function projectMatchesSearch(project, q)")
        end = self.html.index("function filterProjects()", start)
        code = self.html[start:end]

        test_script = code + """
const assert = require('node:assert/strict');

const project = {
  name: 'Acme Portal',
  client: 'Acme Corp',
  parts: [
    {
      label: 'Main Website',
      local_url: 'http://localhost:8090/',
      live_url: 'https://acme.com',
      staging_url: 'https://staging.acme.com',
      git_url: 'git@github.com:acme/portal.git',
      hosting_url: 'https://vercel.com/acme',
    },
    {
      label: 'Store Backend',
      local_url: 'http://localhost:8091/',
      live_url: '',
      staging_url: '',
      git_url: '',
      hosting_url: '',
    }
  ]
};

// Search by project name
assert.equal(projectMatchesSearch(project, 'acme'), true);
assert.equal(projectMatchesSearch(project, 'portal'), true);

// Search by client
assert.equal(projectMatchesSearch(project, 'corp'), true);

// Search by part label
assert.equal(projectMatchesSearch(project, 'website'), true);
assert.equal(projectMatchesSearch(project, 'backend'), true);

// Search by URLs
assert.equal(projectMatchesSearch(project, '8090'), true);
assert.equal(projectMatchesSearch(project, 'staging.acme'), true);
assert.equal(projectMatchesSearch(project, 'github.com:acme'), true);
assert.equal(projectMatchesSearch(project, 'vercel'), true);

// Non-matching
assert.equal(projectMatchesSearch(project, 'unrelated'), false);
assert.equal(projectMatchesSearch(project, '9999'), false);

// Empty query matches all
assert.equal(projectMatchesSearch(project, ''), true);
"""
        run = subprocess.run(["node", "-e", test_script], capture_output=True, text=True, timeout=5)
        self.assertEqual(run.returncode, 0, run.stderr)

    def test_esc_used_for_rendering_node(self):
        start_render_card = self.html.index("function renderProjectCard(project)")
        end_render_card = self.html.index("function renderProjectPartRow(part)", start_render_card)

        start_status_badge = self.html.index("function projectStatusBadge(status)")
        end_status_badge = self.html.index("function projectRoleBadge(role)", start_status_badge)

        start_role_badge = self.html.index("function projectRoleBadge(role)")
        end_role_badge = self.html.index("async function fetchLocalSites(", start_role_badge)

        start_render_part = self.html.index("function renderProjectPartRow(part)")
        end_render_part = self.html.index("// ══ Utility", start_render_part)

        start_url_fn = self.html.index("function sanitizeHttpUrl(url)")
        end_url_fn = self.html.index("function copyToClipboard(", start_url_fn)

        start_esc = self.html.index("function esc(s)")
        end_esc = self.html.index("// ══ Theme", start_esc)

        test_script = (
            self.html[start_esc:end_esc]
            + self.html[start_url_fn:end_url_fn]
            + self.html[start_status_badge:end_status_badge]
            + self.html[start_role_badge:end_role_badge]
            + self.html[start_render_part:end_render_part]
            + self.html[start_render_card:end_render_card]
            + """
const assert = require('node:assert/strict');

const xssProject = {
  id: 'abc12345',
  name: '<script>alert("xss")</script>',
  client: '"><img src=x onerror=alert(1)>',
  status: 'building',
  vault_path: '/path/"with quotes"/and<tag>',
  notes: 'Notes with <style>body{color:red}</style> & ampersand',
  parts: [
    {
      role: 'wordpress',
      label: '<b onmouseover=alert(1)>Hover</b>',
      local_url: 'http://localhost:8080/',
      local_path: '/var/www/<test>',
      notes: '<script>bad()</script>'
    }
  ]
};

const cardHtml = renderProjectCard(xssProject);

// Assert raw unescaped HTML characters are not present in rendered strings
assert.ok(!cardHtml.includes('<script>alert("xss")</script>'), 'Project name must be escaped');
assert.ok(cardHtml.includes('&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;'), 'Project name must be HTML-entity encoded');

assert.ok(!cardHtml.includes('"><img src=x onerror=alert(1)>'), 'Client must be escaped');
assert.ok(cardHtml.includes('&quot;&gt;&lt;img src=x onerror=alert(1)&gt;'), 'Client must be HTML-entity encoded');

assert.ok(!cardHtml.includes('<style>body{color:red}</style>'), 'Notes must be escaped');
assert.ok(cardHtml.includes('&amp; ampersand'), 'Ampersand must be escaped');

assert.ok(!cardHtml.includes('<b onmouseover=alert(1)>'), 'Part label must be escaped');
assert.ok(cardHtml.includes('&lt;b onmouseover=alert(1)&gt;Hover&lt;/b&gt;'), 'Part label must be encoded');
"""
        )
        run = subprocess.run(["node", "-e", test_script], capture_output=True, text=True, timeout=5)
        self.assertEqual(run.returncode, 0, run.stderr)

    def test_link_local_site_autofill_logic_node(self):
        start_fn = self.html.index("function onLinkLocalSiteSelect(selectEl)")
        end_fn = self.html.index("function renderProjectPartFormRow(", start_fn)

        test_script = start_fn and """
const localSitesCache = [
  { type: 'wordpress', role: 'wordpress', name: 'my-wp', port: 8090, path: '/var/www/my-wp' },
  { type: 'laravel', role: 'laravel', name: 'my-lv', port: 8100, path: '/var/www/my-lv' },
  { type: 'codeigniter', role: 'codeigniter', name: 'my-ci', port: 8200, path: '/var/www/my-ci' },
  { type: 'php-projects', role: 'php', name: 'my-php', port: 8300, path: '/var/www/my-php' },
];
""" + self.html[start_fn:end_fn] + """
const assert = require('node:assert/strict');

function makeMockRow() {
  const inputs = {
    '.part-local-url': { value: '' },
    '.part-local-path': { value: '' },
    '.part-role': { value: 'other' },
    '.part-label': { value: '' },
  };
  return {
    querySelector: sel => inputs[sel] || null,
    inputs,
  };
}

// Test selecting WordPress site (index 0)
const rowWp = makeMockRow();
const selectWp = {
  value: '0',
  closest: () => rowWp,
};
onLinkLocalSiteSelect(selectWp);
assert.equal(rowWp.inputs['.part-local-url'].value, 'http://localhost:8090/');
assert.equal(rowWp.inputs['.part-local-path'].value, '/var/www/my-wp');
assert.equal(rowWp.inputs['.part-role'].value, 'wordpress');
assert.equal(rowWp.inputs['.part-label'].value, 'my-wp');

// Test selecting Laravel app (index 1)
const rowLv = makeMockRow();
const selectLv = {
  value: '1',
  closest: () => rowLv,
};
onLinkLocalSiteSelect(selectLv);
assert.equal(rowLv.inputs['.part-local-url'].value, 'http://localhost:8100/');
assert.equal(rowLv.inputs['.part-local-path'].value, '/var/www/my-lv');
assert.equal(rowLv.inputs['.part-role'].value, 'laravel');

// Test selecting CodeIgniter app (index 2)
const rowCi = makeMockRow();
const selectCi = {
  value: '2',
  closest: () => rowCi,
};
onLinkLocalSiteSelect(selectCi);
assert.equal(rowCi.inputs['.part-local-url'].value, 'http://localhost:8200/');
assert.equal(rowCi.inputs['.part-role'].value, 'codeigniter');

// Test selecting PHP project (index 3)
const rowPhp = makeMockRow();
const selectPhp = {
  value: '3',
  closest: () => rowPhp,
};
onLinkLocalSiteSelect(selectPhp);
assert.equal(rowPhp.inputs['.part-local-url'].value, 'http://localhost:8300/');
assert.equal(rowPhp.inputs['.part-role'].value, 'php');
"""
        run = subprocess.run(["node", "-e", test_script], capture_output=True, text=True, timeout=5)
        self.assertEqual(run.returncode, 0, run.stderr)

    def test_running_dot_rendering_node(self):
        start_badge = self.html.index("function projectRoleBadge(role)")
        end_badge = self.html.index("async function fetchLocalSites(", start_badge)

        start_render = self.html.index("function renderProjectPartRow(part)")
        end_render = self.html.index("// ══ Utility", start_render)

        start_esc = self.html.index("function esc(s)")
        end_esc = self.html.index("// ══ Theme", start_esc)

        start_url_fn = self.html.index("function sanitizeHttpUrl(url)")
        end_url_fn = self.html.index("function copyToClipboard(", start_url_fn)

        test_script = (
            self.html[start_esc:end_esc]
            + self.html[start_url_fn:end_url_fn]
            + self.html[start_badge:end_badge]
            + self.html[start_render:end_render]
            + """
const assert = require('node:assert/strict');

// running: true -> green dot
const rTrue = renderProjectPartRow({ role: 'wordpress', local_running: true });
assert.ok(rTrue.includes('dot-green'), 'local_running true must render green dot');
assert.ok(rTrue.includes('title="Local site is running"'));

// running: false -> gray dot
const rFalse = renderProjectPartRow({ role: 'wordpress', local_running: false });
assert.ok(rFalse.includes('dot-gray'), 'local_running false must render gray dot');
assert.ok(rFalse.includes('title="Local site is stopped"'));

// running: null / undefined -> no dot
const rNull = renderProjectPartRow({ role: 'wordpress', local_running: null });
assert.ok(!rNull.includes('status-dot'), 'local_running null must render no dot');

const rUndef = renderProjectPartRow({ role: 'wordpress' });
assert.ok(!rUndef.includes('status-dot'), 'local_running undefined must render no dot');
"""
        )
        run = subprocess.run(["node", "-e", test_script], capture_output=True, text=True, timeout=5)
        self.assertEqual(run.returncode, 0, run.stderr)

    def test_delete_project_wires_into_custom_confirm_modal(self):
        self.assertIn("function deleteProject(", self.html)
        self.assertIn("_delPending = { type: 'project', id, name }", self.html)
        self.assertIn("Delete Project", self.html)
        self.assertIn("delete-modal", self.html)

        # Confirm delete checks for project type
        self.assertIn("if (_delPending.type === 'project')", self.html)
        self.assertIn("apiDelete(`/api/projects/${encodeURIComponent(id)}`)", self.html)

    def test_save_project_routes_and_keeps_modal_open_on_error(self):
        start = self.html.index("async function saveProject()")
        end = self.html.index("function deleteProject(", start)
        save_code = self.html[start:end]

        self.assertIn("POST", save_code)
        self.assertIn("/api/projects", save_code)
        self.assertIn("r.success", save_code)
        self.assertIn("toast(r.error ||", save_code)
        self.assertIn("partObj.id = partId", save_code)


    def test_load_projects_accepts_list_response_without_success_flag(self):
        start = self.html.index("async function loadProjects(")
        body = self.html[start:self.html.index("\n}", start)]
        self.assertNotIn("if (!r.success)", body)
        self.assertIn("Array.isArray(r.projects)", body)

if __name__ == "__main__":
    unittest.main()
