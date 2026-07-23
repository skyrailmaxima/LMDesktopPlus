# Digitalvapor design system

Digitalvapor is the visual and interaction contract for LMDesktopPlus panels.
It is framework-free and split from machine-specific behavior so new tools can
reuse the same appearance without copying screen-specific CSS.

## Files

| File | Responsibility |
|---|---|
| `digitalvapor.css` | Palette, semantic tokens, spacing, type stacks, effects, components, and desktop chrome |
| `digitalvapor.js` | Matrix rain, safe toasts, tabs, dropdowns, context menus, and modal lifecycle |
| `style.css` | LMDesktopPlus scene layouts and legacy-class compatibility |
| `app.js` | API calls, state rendering, launch actions, and feature-specific event handlers |

## Semantic tokens

Use semantic roles rather than raw colors in new components:

```css
var(--dv-accent)
var(--dv-accent-2)
var(--dv-text)
var(--dv-text-bright)
var(--dv-muted)
var(--dv-line)
var(--dv-line-soft)
var(--dv-panel)
var(--dv-panel-2)
var(--dv-surface)
```

Runtime appearance settings update the accent pair, panel opacity, blur,
radius, font stacks, and rain intensity.

## Component classes

| Surface | Classes |
|---|---|
| Panel/card | `.dv-panel`, `.dv-card`, `.dv-card--mag`, `.dv-card--purple` |
| Button | `.dv-btn`, `--primary`, `--outline`, `--ghost`, `--danger`, `--block` |
| Status | `.dv-tag`, `--mag`, `--cyan`, `--mint`, `--purple`, `--warn`, `--off` |
| Field | `.dv-field`, `.dv-input` |
| Toggle | `.dv-toggle`, `.dv-track` |
| Choice | `.dv-choice`, `.dv-radio`, `.dv-mark` |
| Segmented | `.dv-seg`, `.dv-seg__opt` |
| Slider | `.dv-slider`, `.dv-slider--cyan` |
| Tabs | `.dv-tabs`, `.dv-tab`, `.is-active` |
| Progress | `.dv-progress`, `.dv-progress__bar`, `.dv-spinner` |
| Dropdown | `.dv-dropdown`, `.dv-dropdown__toggle`, `.dv-dropdown__list`, `.dv-dropdown__item` |
| Context menu | `.dv-menu`, `.dv-menu__item`, `.dv-menu__sep` |
| Dialog | `.dv-dialog-backdrop`, `.dv-dialog`, `.dv-dialog__bar`, `.dv-dialog__body`, `.dv-dialog__actions` |
| Toast | `.dv-toasts`, `.dv-toast`, `.dv-toast__head`, `.dv-toast__body` |
| Window | `.dv-window`, `.dv-window__bar`, `.dv-window__body`, `.dv-window__dots` |
| Navigation | `.dv-sidepanel`, `.dv-navitem` |
| Desktop chrome | `.dv-bar`, `.dv-dock`, `.dv-dock__item` |

## Interaction attributes

`digitalvapor.js` delegates events, so dynamically rendered scenes do not need
to register component-library handlers repeatedly.

```text
data-dv-rain
data-dv-dropdown
data-dv-tabs
data-dv-panel
data-dv-panel-content
data-dv-dialog
data-dv-close
data-dv-menu
data-dv-toast-close
```

Programmatic interfaces:

```javascript
Digitalvapor.toast({title, body, tone});
Digitalvapor.openDialog("dialog-id");
Digitalvapor.closeDialog("dialog-id");
Digitalvapor.rain(canvas, {intensity: 55});
```

Toast text is inserted with DOM text nodes rather than unsanitized HTML.

## Panel implementation rules

1. Build new surfaces from semantic tokens and reusable component classes.
2. Keep backend actions in `app.js`; do not add shell strings to HTML.
3. Use allowlisted API operations for any machine-changing action.
4. Use a dialog for passwords, destructive actions, or multi-field input.
5. Use a toast for completion and failure feedback.
6. Add the feature to the UI Kit before deploying it to a production scene.
7. Preserve keyboard focus, `aria-label`, dialog semantics, and reduced-motion
   behavior.
8. Do not embed font binaries in frontend or source packages.

## Adding a new panel

A minimal panel uses the shared `panel()` renderer:

```javascript
panel("SERVICE", `
  <div class="dv-between">
    <span>Worker</span>
    <span class="dv-tag dv-tag--mint">active</span>
  </div>
  <div class="dv-progress dv-mt">
    <span class="dv-progress__bar" style="display:block;width:72%"></span>
  </div>
`)
```

A production panel should then bind its feature-specific actions in
`bindSceneEvents()` or through an existing delegated data attribute.
