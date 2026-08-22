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

    def test_frontend_can_refresh_the_shared_update_package(self):
        self.assertIn('id="wp-core-refresh-btn"', self.source)
        self.assertIn("async function refreshWpCorePackage()", self.source)
        self.assertIn("'/api/wordpress/core-update/refresh', 'POST'", self.source)
        self.assertIn("wpCoreUpdateState.refreshOnly = true", self.source)
        self.assertIn("pollWpCoreUpdate(r.job_id)", self.source)

    def test_selected_update_sites_render_a_highlighted_card(self):
        self.assertIn("wp-update-selected", self.source)
        self.assertIn("function toggleWpCoreUpdateSelection(path, checked)", self.source)
        self.assertIn("wpCoreUpdateState.selectedPaths", self.source)

    def test_frontend_polls_and_renders_update_results(self):
        self.assertIn("async function pollWpCoreUpdate(jobId)", self.source)
        self.assertIn('`/api/wordpress/core-update/${jobId}`', self.source)
        self.assertIn("loadWPSites();", self.source)

    def test_readme_describes_cached_core_updates(self):
        with open(os.path.join(PROJECT_ROOT, "README.md")) as f:
            readme = f.read()
        self.assertIn("Update WordPress core", readme)
        self.assertIn("cached official archive", readme)

    # ── M1: frontend checkbox only for strictly older sites ───────────────

    def test_frontend_has_js_version_comparator(self):
        self.assertIn("function compareWpVersions(", self.source)

    def test_checkbox_requires_both_versions_and_strictly_older(self):
        # The checkbox must only render when both installed and target versions
        # are non-empty AND installed is strictly older than target.
        self.assertIn("!!s.wp_version", self.source)
        self.assertIn("!!wpCoreUpdateState.targetVersion", self.source)
        self.assertIn("compareWpVersions(s.wp_version, wpCoreUpdateState.targetVersion) < 0", self.source)
        # Old unsafe logic must be gone.
        self.assertNotIn("s.wp_version !== wpCoreUpdateState.targetVersion", self.source)

    # ── M2: toast/report distinguishes partial and failed batches ─────────

    def test_poll_reports_partial_success_with_counts(self):
        # When some sites fail, the toast must include counts of updated,
        # current, and failed sites.
        poll_body = self.source.split("async function pollWpCoreUpdate(jobId)")[1].split("\n}\n")[0]
        self.assertIn("failed", poll_body)
        self.assertIn("updated", poll_body)
        self.assertIn("current", poll_body)
        self.assertIn("partial", poll_body)

    def test_poll_uses_result_success_for_toast_type(self):
        # Toast type must depend on per-site failure count, not just job.status.
        poll_body = self.source.split("async function pollWpCoreUpdate(jobId)")[1].split("\n}\n")[0]
        self.assertIn("failed === 0", poll_body)
        self.assertIn("toast(msg, (job.status === 'done' && failed === 0) ? 'success' : 'error')", poll_body)

    # ── UI polling fix: stop and report missing/error job response ────────

    def test_poll_stops_on_missing_job_response(self):
        # When the job endpoint returns empty/invalid data repeatedly, the
        # poll must stop and show an error toast instead of spinning forever.
        poll_body = self.source.split("async function pollWpCoreUpdate(jobId)")[1].split("\n}\n")[0]
        self.assertIn("missingCount", poll_body)
        self.assertIn("Job response missing", poll_body)
        self.assertIn("clearInterval", poll_body)

    def test_poll_reenables_button_on_completion(self):
        # The update button must be re-enabled when polling ends (success,
        # error, or lost job) so the user can retry.
        poll_body = self.source.split("async function pollWpCoreUpdate(jobId)")[1].split("\n}\n")[0]
        self.assertIn("button.disabled = false", poll_body)


class WordPressVersionComparatorFrontendTests(unittest.TestCase):
    """Behavioral tests for the JS compareWpVersions function."""

    @classmethod
    def setUpClass(cls):
        with open(INDEX_PATH) as f:
            src = f.read()
        fn_src = src.split("function compareWpVersions(a, b) {")[1]
        # Find the matching closing brace.
        depth = 1
        i = 0
        while depth > 0 and i < len(fn_src):
            if fn_src[i] == '{':
                depth += 1
            elif fn_src[i] == '}':
                depth -= 1
            i += 1
        cls.fn_src = "function compareWpVersions(a, b) {" + fn_src[:i]

    def _call(self, a, b):
        import subprocess
        js = f'{self.fn_src}\nconsole.log(compareWpVersions({a!r}, {b!r}));'
        r = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=5)
        return int(r.stdout.strip())

    def test_equal_releases(self):
        self.assertEqual(self._call("6.4.2", "6.4.2"), 0)

    def test_trailing_zero_equivalence(self):
        self.assertEqual(self._call("6.5", "6.5.0"), 0)
        self.assertEqual(self._call("6.5.0", "6.5"), 0)

    def test_numeric_older(self):
        self.assertEqual(self._call("6.4.2", "6.5"), -1)
        self.assertEqual(self._call("6.4.2", "6.4.3"), -1)

    def test_numeric_newer(self):
        self.assertEqual(self._call("6.5", "6.4.2"), 1)

    def test_prerelease_older_than_release(self):
        self.assertEqual(self._call("6.5-alpha", "6.5"), -1)
        self.assertEqual(self._call("6.5-RC1", "6.5"), -1)

    def test_empty_versions(self):
        self.assertEqual(self._call("", "6.5"), -1)
        self.assertEqual(self._call("", ""), 0)
        self.assertEqual(self._call("6.5", ""), 1)

    def test_never_downgrade_invariants(self):
        for installed, target in [
            ("6.5", "6.5"),
            ("6.5.0", "6.5"),
            ("6.5", "6.5.0"),
            ("6.5.1", "6.5"),
            ("6.6", "6.5"),
            ("6.5", "6.5-RC1"),
        ]:
            with self.subTest(installed=installed, target=target):
                self.assertGreaterEqual(self._call(installed, target), 0)


if __name__ == "__main__":
    unittest.main()
