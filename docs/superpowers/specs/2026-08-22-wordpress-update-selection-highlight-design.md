# WordPress Update Selection Highlight Design

## Goal

Make selected WordPress update targets visually distinct in the Installed Sites list.

## Behavior

- Checking a WordPress core-update checkbox adds a blue border and subtle blue background to that site's card.
- Unchecking it immediately restores the normal card appearance.
- A small selected label appears only on selected cards.
- No update API, selection validation, or other application behavior changes.

## Implementation

- Add a scoped `.wp-card.wp-update-selected` CSS rule in `index.html`.
- Re-render the WordPress cards from the checkbox change handler so the selected state is reflected.
- Keep selected paths in a small frontend array so rendering does not clear checked selections.

## Testing

- Verify the WordPress card render includes the selected class only for selected paths.
- Verify the checkbox change handler updates the selected-path state and re-renders.
