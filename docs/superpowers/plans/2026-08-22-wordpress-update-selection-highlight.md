# WordPress Update Selection Highlight Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Visually highlight selected WordPress core-update site cards.

**Architecture:** Keep selected paths in existing frontend state and re-render the WordPress site cards after checkbox changes. A scoped CSS class supplies the selected border, tint, and label.

**Tech Stack:** Vanilla JavaScript, CSS, Python `unittest` source-contract tests.

## Global Constraints

- Change only the WordPress core-update selection presentation.
- A selected card uses a blue border, subtle blue tint, and selected label.
- Do not change update API or validation behavior.

---

### Task 1: Add Selected Card State

**Files:**
- Modify: `index.html`
- Modify: `tests/test_wordpress_core_update_frontend.py`

**Interfaces:**
- Consumes: checked `.wp-core-update-choice` inputs.
- Produces: `wpCoreUpdateState.selectedPaths` and `toggleWpCoreUpdateSelection(path, checked)`.

- [ ] **Step 1: Write the failing test**

```python
def test_selected_update_sites_render_a_highlighted_card(self):
    self.assertIn("wp-update-selected", self.source)
    self.assertIn("function toggleWpCoreUpdateSelection(path, checked)", self.source)
    self.assertIn("wpCoreUpdateState.selectedPaths", self.source)
```

- [ ] **Step 2: Run the failing test**

Run: `python3 -m unittest tests.test_wordpress_core_update_frontend.WordPressCoreUpdateFrontendTests.test_selected_update_sites_render_a_highlighted_card -v`

Expected: FAIL because selection-highlight state does not exist.

- [ ] **Step 3: Add minimal implementation**

```css
.wp-card.wp-update-selected {
  border-color: #89b4fa;
  background: #1e2a45;
  box-shadow: 0 0 0 1px rgba(137, 180, 250, .2);
}
```

```javascript
function toggleWpCoreUpdateSelection(path, checked) {
  const selected = new Set(wpCoreUpdateState.selectedPaths || []);
  if (checked) selected.add(path); else selected.delete(path);
  wpCoreUpdateState.selectedPaths = [...selected];
  renderWordPressSites();
}
```

Make each update checkbox call `toggleWpCoreUpdateSelection(this.value, this.checked)`, retain its checked state on render, and add the selected class and `Selected for update` label when its path is selected.

- [ ] **Step 4: Run all frontend tests**

Run: `python3 -m unittest tests.test_wordpress_core_update_frontend -v`

Expected: PASS.

- [ ] **Step 5: Verify the panel manually**

Run: `python3 panel.py`

Expected: checking a selectable site immediately adds the blue selected-card highlight and unchecking removes it.
