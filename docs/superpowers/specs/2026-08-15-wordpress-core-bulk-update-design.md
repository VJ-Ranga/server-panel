# WordPress Core Bulk Update Design

## Goal

Let the server panel update WordPress core for selected local sites using one cached official WordPress archive. The update preserves site content and configuration and never updates plugins or themes.

## Scope

- Add a core-update area to the WordPress Installed Sites tab.
- Check the official WordPress version API when the update area is loaded or refreshed.
- Keep one archive and its version marker in the existing `cache/wordpress/` directory.
- Reuse the cache when it matches the latest available version.
- Download a replacement archive once when the official latest version is newer or the archive is missing.
- Allow selecting individual sites or all detected outdated sites.
- Run updates in one background job and show a live, per-site progress log.
- Report each site as updated, already current, skipped, or failed, without stopping other selected sites.

## Update Procedure

For every selected site, the backend will:

1. Confirm the path is one of the currently discovered WordPress sites.
2. Read the installed version from the site's `wp-includes/version.php`.
3. Skip the site when it already matches the target cached version.
4. Enable WordPress maintenance mode by writing the standard `.maintenance` file.
5. Extract the cached official archive into a temporary directory.
6. Replace WordPress core directories and root PHP files only.
7. Preserve `wp-content/`, `wp-config.php`, and all other site-specific files.
8. Restore ownership and permissions with the existing privileged WordPress helper.
9. Remove `.maintenance` even when the update fails.

The updater does not perform database upgrades. WordPress will prompt for any required database upgrade when the site administrator next opens `/wp-admin/`.

## Cache Behavior

- The existing `cache/wordpress/latest.tar.gz` archive and `latest.version` marker are the source of the update package.
- If the WordPress version API confirms the cached version is current, no download occurs.
- If a newer version is available, the new archive is downloaded to a temporary `.part` file and atomically replaces the cache only after download success.
- If the API is unavailable and a valid cached archive exists, the panel offers that cached version as the target and labels it as unverified in the UI and logs.
- If no archive is cached and the API or download fails, no update job starts.

## API And UI

- `GET /api/wordpress/core-update-status` returns the available target version, cache state, and installed core version for each discovered site.
- `POST /api/wordpress/core-update` accepts a list of selected discovered site paths and starts a background job.
- `GET /api/wordpress/core-update/<job_id>` returns the shared job status, log lines, and per-site results.
- The Installed Sites tab displays the available version, cache status, and a checkbox for every outdated site.
- An Update Selected button starts the job only after at least one site is selected. The job log remains visible until the user refreshes or starts another update.

## Safety And Failure Handling

- Only paths returned by the current WordPress discovery pass are accepted; request paths cannot target arbitrary directories.
- Archive member paths are validated during extraction to prevent path traversal.
- The panel uses the existing sudo helper for all privileged file replacement and permission repair.
- A failure affects only the current site; the job continues with later selected sites.
- Every site result includes a clear final status and error where applicable.
- This feature does not create database, plugin, theme, or full-file backups. It follows the normal WordPress core-update model requested for the panel.

## Testing

- Status endpoint identifies current, outdated, and unreadable site versions.
- Status uses a current cache without downloading again.
- Status reports a newer remote version and refreshes the cache only after successful download.
- Update request rejects unknown or unsafe paths.
- Core replacement preserves `wp-content/` and `wp-config.php` while updating core files.
- Maintenance mode is removed after success and failure.
- A failed site does not prevent later selected sites from being processed.
- Frontend renders version/cache status, selection controls, and live job output.
