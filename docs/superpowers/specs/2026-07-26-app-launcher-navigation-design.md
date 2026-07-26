# App Launcher Navigation Design

## Goal

Keep the sidebar short as more application types are added. App-specific entry points should live inside App Launcher instead of becoming permanent sidebar items.

## Chosen Approach

Use **App Launcher Only** for application navigation.

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

The existing app-specific pages stay in `index.html`. They are still opened through App Launcher card actions:

- `Create` opens the existing install tab for that app type.
- `Manage` opens the existing installed-apps/sites tab for that app type.

## User Experience

App Launcher becomes the single app hub. Each app card remains responsible for both app creation and app management entry:

```text
WordPress      [Create] [Manage]
Laravel        [Create] [Manage]
CodeIgniter    [Create] [Manage]
PHP Project    [Create] [Manage]
```

Future apps are added as App Launcher cards, not new sidebar links.

## Technical Design

- Remove only the app-specific sidebar anchors.
- Keep `page-wordpress`, `page-laravel`, `page-codeigniter`, and `page-php-projects` markup unchanged.
- Keep `pageTitles` entries for app pages because hidden pages still need correct titles when opened from App Launcher.
- Update `openAppLauncherTarget` so it does not depend on a sidebar anchor existing for hidden app pages.
- Preserve all existing app install APIs, list APIs, delete actions, port changes, and management pages.
- Do not add backend routes.

## Error Handling

- If an App Launcher target page is missing, show the existing error toast.
- If a target tab is missing, show the existing error toast.
- Navigation should still update the active sidebar state to App Launcher when opening a hidden app page from an App Launcher card.

## Testing

- Update frontend structure tests so app-specific sidebar links are absent.
- Keep tests proving App Launcher cards and Create/Manage mappings exist.
- Add or update tests proving App Launcher navigation no longer requires sidebar links for hidden app pages.
- Run the full Python unittest suite and inline JavaScript syntax check.

## Out Of Scope

- No collapsible sidebar menu.
- No app search/filtering in this change.
- No backend changes.
- No visual redesign of app cards beyond what is necessary for navigation clarity.

## Self-Review

- Placeholder scan: no TBD or TODO items remain.
- Scope check: this is limited to sidebar organization and App Launcher routing.
- Consistency check: App pages remain available but are no longer top-level sidebar entries.
- Ambiguity check: future apps must be added as App Launcher cards, not sidebar items.
