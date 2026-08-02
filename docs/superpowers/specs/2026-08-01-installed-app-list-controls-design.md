# Installed App List Controls Design

## Goal

Make large installed website/app lists easier to scan by adding search and sort controls to every installed-list page.

## Scope

- Add list controls to WordPress Sites, Laravel Apps, CodeIgniter Apps, and PHP Projects.
- Search filters cards by visible operational fields: name, path, database, database user, port, nginx site, and app-specific labels such as template or version.
- Sort choices are: Newest first, Oldest first, Name A-Z, Name Z-A, Port low-high, and Port high-low.
- Show a count such as `Showing 4 of 18` next to each toolbar.
- Add a Clear button to reset search.
- Keep filtering and sorting frontend-side after API data loads.

## Data Requirements

- Each frontend list stores the latest API response in a local JS array.
- WordPress, Laravel, and CodeIgniter list responses include `modified_at` from the install directory mtime.
- PHP Projects already include `created_at`; add `modified_at` fallback for consistent sorting.
- Newest/oldest sorting uses `created_at || modified_at || 0`.

## UI Behavior

- Search updates the card list immediately as the user types.
- Sort changes re-render the same loaded results without a new API call.
- Refresh reloads data from the API and keeps the current search/sort controls.
- If search hides every item, show an empty-state message for that filtered list.

## Testing

- Add frontend source tests confirming all four list toolbars exist and expose search, sort, clear, and count elements.
- Add frontend source tests confirming shared filter/sort functions exist.
- Add backend tests confirming WordPress site responses include `modified_at`.
- Run full Python unittest discovery.
