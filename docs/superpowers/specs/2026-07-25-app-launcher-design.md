# App Launcher Design

## Goal

Add a unified **App Launcher** page where the user can start creating any supported local app type from one place: WordPress, Laravel, CodeIgniter, and plain PHP Projects.

## Scope

- Add a new sidebar item named **App Launcher** under Overview or Services.
- The App Launcher is create-focused, not a replacement for the existing detailed management pages.
- Keep existing app-specific sections for installed app lists, advanced controls, logs, deletes, and port changes.
- Reuse existing frontend install forms and backend install APIs.
- Do not create new backend install routes in this version.

## UI Design

The App Launcher page shows a grid of app cards:

- WordPress
- Laravel
- CodeIgniter
- PHP Project

Each card includes:

- app name and icon
- short description
- key requirements, such as Composer for Laravel and CodeIgniter
- default port range:
  - WordPress: starts near `8090`
  - Laravel: starts near `8100`
  - CodeIgniter: starts near `8200`
  - PHP Project: starts near `8300`
- primary `Create` button
- secondary `Manage` button

## Navigation Behavior

Clicking `Create` should navigate to the existing app-specific create tab:

- WordPress: open `#wordpress`, switch to the install tab, load next port and plugin library.
- Laravel: open `#laravel`, switch to the install tab, load next port.
- CodeIgniter: open `#codeigniter`, switch to the install tab, load next port.
- PHP Project: open `#php-projects`, switch to the install tab, load next port.

Clicking `Manage` should navigate to the existing installed-apps tab for that app type.

## Naming

Use **App Launcher** for the sidebar and page title.

Reasoning:

- It is clearer than **App Store**, because the panel is not downloading third-party marketplace apps.
- It is more action-oriented than **App Catalog**.
- It fits both framework apps and plain PHP projects.

## Architecture

This is a frontend-only feature:

- Add `page-app-launcher` markup in `index.html`.
- Add `app_launcher: 'App Launcher'` or equivalent page title mapping.
- Add helper JavaScript functions to route users to existing tabs.
- Reuse `showPage`, `switchTab`, and existing loader functions.
- No changes to install job code or helper scripts are required.

## Error Handling

- If a target tab or page is missing, show an error toast instead of failing silently.
- Create buttons should still work after page refresh because navigation uses existing page IDs and tabs.

## Testing

- Add frontend structure tests confirming:
  - sidebar item exists
  - `page-app-launcher` exists
  - all four app cards exist
  - create/manage routing functions exist
  - target page IDs are referenced
- Run existing backend/frontend tests.
- Run frontend JavaScript syntax validation with Node.
- Manually verify each card navigates to the correct create or manage tab.
