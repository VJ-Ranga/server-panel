# WordPress Plugin Auto-Install Design

## Goal

Add a local WordPress plugin library to the server panel. The user can place plugin zip files in a project folder, then select plugins during WordPress site creation. Selected plugins are installed and activated automatically after WordPress itself is configured.

## Plugin Library

- Folder: `wp-plugin-library/` inside the server panel project.
- Accepted files: `.zip` only.
- The backend scans zip files and detects plugin metadata from the plugin header in the main PHP file:
  - plugin name
  - version
  - slug/folder name
  - main plugin file path
- Invalid zip files or zips without a detectable plugin header are skipped and reported in the API response.

## UI Changes

- Add a **Plugins** section to the WordPress install form.
- Show detected plugins as checkboxes with name, version, and zip filename.
- Add a refresh button to rescan the plugin library.
- The selected plugin slugs/zip names are included in the `/api/wordpress/install` request.

## Install Flow

After WordPress is installed and the admin user is configured:

1. For each selected plugin, extract its zip into `wp-content/plugins/`.
2. Set permissions using the existing WordPress site permission rules.
3. Activate the plugin using a PHP script loaded inside the new WordPress site.
4. Log success or failure for each plugin in the install progress log.

Plugin activation failures should not roll back the whole WordPress site. They should be logged clearly so the site still completes installation.

## Security And Safety

- Only zip files from `wp-plugin-library/` can be selected.
- Request values are matched against scanned library entries; arbitrary paths are not accepted.
- Extraction is protected against zip-slip paths by validating extracted member paths stay inside `wp-content/plugins/`.
- No upload endpoint is added in this version; plugin files are added manually to the folder by the local user.

## Testing

- Scan a valid plugin zip and verify name/version display.
- Scan an invalid zip and verify it does not break the page.
- Install a WordPress site with no plugins selected.
- Install a WordPress site with one valid selected plugin and verify it is active.
- Install with an activation-failing plugin and verify the site still completes with a clear log message.
