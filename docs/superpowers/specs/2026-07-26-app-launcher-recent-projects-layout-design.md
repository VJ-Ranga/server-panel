# App Launcher Recent Projects Layout Design

## Goal

Keep App Launcher cards compact and equal-height by moving recent project details out of each app card into a dedicated grouped section below the cards.

## Current Problem

Recent project rows currently render inside each app card. Apps with several projects become much taller than apps with no projects, which makes the card grid visually uneven and harder to scan.

## Chosen Approach

Use a two-section App Launcher layout:

```text
App Launcher

App Cards
[ WordPress      8 sites      Create | View All ]
[ Laravel        1 app        Create | View All ]
[ CodeIgniter    0 apps       Create | View All ]
[ PHP Project    0 projects   Create | View All ]

Recent Projects

WordPress
- globalnaturalherbal     :8100 · /var/www/globalnaturalherbal     Open | Manage
- experilanka             :8099 · /var/www/experilanka             Open | Manage
- minoliecom              :8097 · /var/www/minoliecom              Open | Manage

Laravel
- burger                  :8101 · /var/www/burger                  Open | Manage

CodeIgniter
No CodeIgniter apps yet

PHP Projects
No PHP projects yet
```

## App Cards

Each top card should show only:

- App name and icon.
- Short description.
- Default port/requirement line.
- Installed count badge.
- `Create` button.
- `View All` button.

Top cards should not render recent project rows or `Open`/per-project `Manage` actions.

## Recent Projects Section

Add a dedicated **Recent Projects** section below the card grid.

The section should be grouped by app type:

- WordPress
- Laravel
- CodeIgniter
- PHP Projects

Each group should show up to three recent/detected projects for that app type.

Each project row should show:

- Project name.
- Port/path summary from existing item data.
- `Open` action when a port exists.
- `Manage` action that opens the hidden installed-apps/sites tab for that app type.

If an app type has no projects, show compact empty text inside that group.

## Technical Design

- Keep the existing backend APIs unchanged.
- Keep App Launcher summary loading from existing APIs:
  - WordPress: `/api/wordpress/sites`
  - Laravel: `/api/laravel/apps`
  - CodeIgniter: `/api/codeigniter/apps`
  - PHP Projects: `/api/php-projects/apps`
- Keep `launcher-*-count` elements inside the top app cards.
- Move `launcher-*-recent` containers out of the app cards and into the new Recent Projects section.
- Keep `renderAppLauncherCardSummary(type, items)` responsible for updating both the top card count and the matching recent-project group.
- Keep `Open` links using `target="_blank" rel="noopener noreferrer"`.
- Do not add delete/destructive actions to App Launcher.
- Do not duplicate full management tables in App Launcher.

## Error Handling

- If one app summary API fails, show `Load failed` in that app card count badge.
- Show the error state in that app type's Recent Projects group only.
- Other app groups should still load normally.

## Testing

- Update App Launcher frontend tests so recent containers are required outside the app card blocks.
- Keep tests proving app cards have count badges, `Create`, and `View All` actions.
- Keep tests proving recent project rows render names, metadata, `Open`, and `Manage` actions.
- Keep tests proving recent `Open` links use `rel="noopener noreferrer"`.
- Run the full Python unittest suite and inline JavaScript syntax check.

## Out Of Scope

- No backend changes.
- No search/filtering for recent projects.
- No sorting change beyond using the first three items returned by each existing API.
- No full project tables inside App Launcher.
- No delete buttons or destructive actions inside App Launcher.

## Self-Review

- Placeholder scan: no TBD or TODO items remain.
- Scope check: this only changes App Launcher layout, not backend behavior.
- Consistency check: cards remain create/status focused; recent project details move below into grouped sections.
- Ambiguity check: `launcher-*-recent` containers must be outside the app cards, not merely visually separated inside them.
