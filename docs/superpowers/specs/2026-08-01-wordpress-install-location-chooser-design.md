# WordPress Install Location Chooser Design

## Goal

Add a simple location chooser to the WordPress install form so users can choose where a new site is created without manually typing the full install path.

## Scope

- Add an `Install Location` dropdown to the WordPress install form.
- Offer three safe roots: `/var/www`, `/opt`, and the current panel user's `~/local` path.
- Keep the existing `Install Path` input visible and editable so users can see the generated path and make advanced adjustments.
- Generate the path as `<selected-root>/<sanitized-site-name>` when the site name or selected location changes.
- Leave backend validation and sudo helper behavior aligned with the existing safe root rules.

## UI Behavior

- Default location: `/var/www`.
- Selecting `/var/www` with site name `test` generates `/var/www/test`.
- Selecting `/opt` with site name `test` generates `/opt/test`.
- Selecting `~/local` with site name `test` generates `/home/<panel-user>/local/test`.
- The path input remains a normal text input for transparency and manual override.

## Architecture

- Frontend-only form enhancement in `index.html` for the chooser and path-generation logic.
- Backend remains the source of truth for validation.
- `wp-install-helper.sh` remains the privileged enforcement layer for allowed roots.

## Testing

- Add frontend tests or source assertions confirming the dropdown exists and the expected options are present.
- Keep existing WordPress custom path helper tests passing.
- Run the full `tests` unittest discovery after implementation.
