# App Launcher Navigation Design

## Goal

Keep the sidebar short as more application types are added. App-specific entry points should live inside App Launcher instead of becoming permanent sidebar items.

## Chosen Approach

Use **App Launcher Only** for application navigation, and make it an app dashboard with creation actions, installed counts, and recent project details.

The sidebar becomes:

```text
Overview
- Dashboard
- App Launcher

Server
- Nginx
- MySQL
- phpMyAdmin
- Performance

System
- Settings
```

Remove these direct sidebar links:

- WordPress
- Laravel
- CodeIgniter
- PHP Projects

The existing app-specific pages stay in `index.html`. They are still opened through App Launcher actions:

- `Create` opens the existing install tab for that app type.
- `View All` opens the existing installed-apps/sites tab for that app type.
- Per-project `Manage` opens the existing installed-apps/sites tab for that app type.

## User Experience

App Launcher becomes the single app hub. It shows a quick create section first, followed by installed counts and recent project details for each app type.

```text
App Launcher

Quick Create

WordPress      3 sites      [Create] [View All]
- demo-site       [Open] [Manage]
- client-site     [Open] [Manage]

Laravel        1 app        [Create] [View All]
- crm-app         [Open] [Manage]

CodeIgniter    0 apps       [Create]

PHP Projects   4 projects   [Create] [View All]
- test-api        [Open] [Manage]
- landing-demo    [Open] [Manage]
```

Future apps are added as App Launcher cards, not new sidebar links.

Each card should show:

- App name and icon.
- Installed count label: `0 sites`, `1 app`, `4 projects`, etc.
- Short requirement/status line such as default port range and whether Composer/MySQL is needed.
- `Create` button.
- `View All` button when at least one project exists.
- Up to three recent/detected projects with name, port/path summary, `Open`, and `Manage` actions.

If an app type has no installed projects, show a compact empty state inside the card instead of a blank area.

## Technical Design

- Remove only the app-specific sidebar anchors.
- Keep `page-wordpress`, `page-laravel`, `page-codeigniter`, and `page-php-projects` markup unchanged.
- Keep `pageTitles` entries for app pages because hidden pages still need correct titles when opened from App Launcher.
- Update `openAppLauncherTarget` so it does not depend on a sidebar anchor existing for hidden app pages.
- Load App Launcher summary data from the existing frontend loader functions and existing backend APIs:
  - WordPress: use `/api/wordpress/sites` data.
  - Laravel: use `/api/laravel/apps` data.
  - CodeIgniter: use `/api/codeigniter/apps` data.
  - PHP Projects: use `/api/php-projects/apps` data.
- Do not duplicate full management tables inside App Launcher. Show only counts and up to three recent/detected items per app type.
- Keep the full installed-apps/sites lists, deletes, advanced actions, port changes, and logs inside the hidden app-specific pages.
- Preserve all existing app install APIs, list APIs, delete actions, port changes, and management pages.
- Do not add backend routes.

## Error Handling

- If an App Launcher target page is missing, show the existing error toast.
- If a target tab is missing, show the existing error toast.
- Navigation should still update the active sidebar state to App Launcher when opening a hidden app page from an App Launcher card.
- If one app summary API fails, show an error state only in that app card and keep the other cards usable.
- If an app has no installed projects, show a zero count and empty-state text.

## Testing

- Update frontend structure tests so app-specific sidebar links are absent.
- Keep tests proving App Launcher cards and Create/Manage mappings exist.
- Add or update tests proving App Launcher navigation no longer requires sidebar links for hidden app pages.
- Add tests proving App Launcher contains installed-count placeholders and recent-project containers for each app type.
- Add tests proving summary loader functions exist for App Launcher and call existing app list APIs.
- Run the full Python unittest suite and inline JavaScript syntax check.

## Out Of Scope

- No collapsible sidebar menu.
- No app search/filtering in this change.
- No backend changes.
- No full duplicate app management tables inside App Launcher.
- No destructive actions such as delete directly from App Launcher.
- No visual redesign beyond what is necessary for the dashboard card layout.

## Self-Review

- Placeholder scan: no TBD or TODO items remain.
- Scope check: this is limited to sidebar organization, App Launcher routing, and lightweight app summary display.
- Consistency check: App pages remain available but are no longer top-level sidebar entries; App Launcher shows summaries only, not full management duplicates.
- Ambiguity check: future apps must be added as App Launcher cards, not sidebar items.
