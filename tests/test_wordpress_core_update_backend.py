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

    # ── Review-fix contract tests ──────────────────────────────────────────

    def test_status_get_never_downloads_the_archive(self):
        self.assertIn("_prepare_wp_cache(allow_download=False)", self.source)
        status_body = self.source.split("def get_wp_core_update_status():")[1].split("\ndef ")[0]
        self.assertNotIn("curl -fL", status_body)

    def test_failed_download_preserves_existing_cache(self):
        cache_fn = self.source.split("def _prepare_wp_cache(")[1].split("\ndef ")[0]
        self.assertIn("allow_download=True", cache_fn)
        self.assertIn("cached-unverified", cache_fn)
        self.assertIn('"target_version": cached_ver or ""', cache_fn)
        self.assertGreaterEqual(cache_fn.count("if has_tar:"), 2)

    def test_update_job_skips_current_sites_and_continues_after_errors(self):
        self.assertIn('"already-current"', self.source)
        self.assertIn('"failed"', self.source)
        self.assertIn('for site_path in paths:', self.source)
        self.assertIn('results.append(', self.source)

    def test_update_job_passes_only_the_cached_archive_to_the_helper(self):
        expected = 'sudo {shell_quote(helper)} --core-update {shell_quote(site_path)} {shell_quote(WP_CACHE_TAR)}'
        self.assertIn(expected, self.source)

    def test_update_job_prepares_cache_with_allow_download(self):
        job_body = self.source.split("def update_wordpress_core_job(")[1].split("\ndef ")[0]
        self.assertIn("_prepare_wp_cache(log_func=log, allow_download=True)", job_body)
        self.assertNotIn("get_wp_core_update_status()", job_body)

    def test_update_job_records_disappeared_sites_and_continues(self):
        job_body = self.source.split("def update_wordpress_core_job(")[1].split("\ndef ")[0]
        self.assertIn("known_sites.get(site_path)", job_body)
        self.assertIn('"status": "failed"', job_body)
        self.assertIn('"error": "Site no longer found in WordPress discovery"', job_body)
        self.assertIn("continue", job_body)

    # ── M1: never downgrade core ──────────────────────────────────────────

    def test_compare_wp_versions_function_exists(self):
        self.assertIn("def compare_wp_versions(a, b):", self.source)

    def test_status_needs_update_uses_strict_older_comparison(self):
        status_body = self.source.split("def get_wp_core_update_status():")[1].split("\ndef ")[0]
        self.assertIn("compare_wp_versions(installed_ver, target_ver) < 0", status_body)
        self.assertNotIn("installed_ver != cache_info", status_body)

    def test_status_needs_update_requires_both_versions(self):
        status_body = self.source.split("def get_wp_core_update_status():")[1].split("\ndef ")[0]
        self.assertIn("and installed_ver", status_body)
        self.assertIn("and compare_wp_versions", status_body)

    def test_job_skips_newer_or_equal_sites_never_downgrades(self):
        job_body = self.source.split("def update_wordpress_core_job(")[1].split("\ndef ")[0]
        self.assertIn("compare_wp_versions(installed, target_version)", job_body)
        self.assertIn("cmp >= 0", job_body)
        self.assertIn("never downgrade", job_body)

    def test_job_marks_unknown_installed_version_as_failed(self):
        job_body = self.source.split("def update_wordpress_core_job(")[1].split("\ndef ")[0]
        self.assertIn("Installed WordPress version is unknown", job_body)

    # ── M2: job result reflects partial/failed batches ────────────────────

    def test_job_result_success_false_when_any_site_fails(self):
        job_body = self.source.split("def update_wordpress_core_job(")[1].split("\ndef ")[0]
        self.assertIn('any(r.get("status") == "failed" for r in results)', job_body)
        self.assertIn('"success": not any_failed', job_body)
        self.assertNotIn('"success": True, "target_version"', job_body)

    def test_job_result_reports_all_current_flag(self):
        job_body = self.source.split("def update_wordpress_core_job(")[1].split("\ndef ")[0]
        self.assertIn('"all_current"', job_body)


def _load_compare():
    """Load compare_wp_versions from panel.py without importing the whole module."""
    with open(PANEL_PATH) as f:
        src = f.read()
    fn_src = src.split("def compare_wp_versions(a, b):")[1].split("\n\ndef ")[0]
    full_src = "def compare_wp_versions(a, b):" + fn_src
    ns = {"re": re}
    exec(full_src, ns)
    return ns["compare_wp_versions"]


class WordPressVersionComparatorTests(unittest.TestCase):
    """Behavioral tests for compare_wp_versions — the core of M1."""

    @classmethod
    def setUpClass(cls):
        cls.compare = staticmethod(_load_compare())

    def test_equal_releases(self):
        self.assertEqual(self.compare("6.4.2", "6.4.2"), 0)

    def test_trailing_zero_equivalence(self):
        self.assertEqual(self.compare("6.5", "6.5.0"), 0)
        self.assertEqual(self.compare("6.5.0", "6.5"), 0)

    def test_numeric_older(self):
        self.assertEqual(self.compare("6.4.2", "6.5"), -1)
        self.assertEqual(self.compare("6.4.2", "6.4.3"), -1)
        self.assertEqual(self.compare("5.9", "6.0"), -1)

    def test_numeric_newer(self):
        self.assertEqual(self.compare("6.5", "6.4.2"), 1)
        self.assertEqual(self.compare("6.4.3", "6.4.2"), 1)

    def test_prerelease_older_than_release(self):
        self.assertEqual(self.compare("6.5-alpha", "6.5"), -1)
        self.assertEqual(self.compare("6.5-beta", "6.5"), -1)
        self.assertEqual(self.compare("6.5-RC1", "6.5"), -1)

    def test_prerelease_ordering(self):
        self.assertEqual(self.compare("6.5-alpha", "6.5-beta"), -1)
        self.assertEqual(self.compare("6.5-beta", "6.5-RC1"), -1)
        self.assertEqual(self.compare("6.5-RC1", "6.5"), -1)

    def test_prerelease_higher_number_still_older(self):
        self.assertEqual(self.compare("6.6-RC1", "6.5"), 1)
        self.assertEqual(self.compare("6.6-RC1", "6.6"), -1)

    def test_empty_versions(self):
        self.assertEqual(self.compare("", "6.5"), -1)
        self.assertEqual(self.compare("", ""), 0)
        self.assertEqual(self.compare("6.5", ""), 1)

    def test_never_downgrade_invariants(self):
        same_or_newer = [
            ("6.5", "6.5"),
            ("6.5.0", "6.5"),
            ("6.5", "6.5.0"),
            ("6.5.1", "6.5"),
            ("6.6", "6.5"),
            ("6.5", "6.5-RC1"),
            ("6.5", "6.5-beta"),
        ]
        for installed, target in same_or_newer:
            with self.subTest(installed=installed, target=target):
                self.assertGreaterEqual(self.compare(installed, target), 0)

    def test_always_update_when_strictly_older(self):
        older_pairs = [
            ("6.4.2", "6.5"),
            ("6.4.2", "6.4.3"),
            ("5.9", "6.0"),
            ("6.5-RC1", "6.5"),
            ("6.5-beta", "6.5"),
            ("6.5-alpha", "6.5-beta"),
        ]
        for installed, target in older_pairs:
            with self.subTest(installed=installed, target=target):
                self.assertEqual(self.compare(installed, target), -1)


if __name__ == "__main__":
    unittest.main()
