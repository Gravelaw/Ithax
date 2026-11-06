# Design system

A small design system for the Phase 1 interface: colour tokens, type, spacing, layout, controls, block and port styles, and the light and dark themes. It serves spec 3 "Design before building" (fourth item). The canvas behaviour it styles is in `canvas-interactions.md`; the accessibility checks are in `accessibility.md`.

Principles, from spec 0 and the interface study (`docs/research/spec-3-interface-study.md`):

1. **Plain and calm.** Students and business users with no code are the main users (spec 0 "Users"). One accent colour, flat surfaces, no decoration that carries no meaning.
2. **Never colour alone.** Every state shown in colour also has a shape, an icon or a word (WCAG 2.2 success criterion 1.4.1).
3. **Readable at a distance and on a low-tier laptop.** Text sizes start at 12 px and scale with the text-size setting; no effect depends on graphics hardware (spec 3 "Hardware tiers").
4. **Works offline.** System fonts only; no web fonts are downloaded (spec 0 principle 6).

## Colour tokens

The single source is `docs/design/tokens.json`. Interface code reads token names, never raw colours. Each theme defines every token.

| Token | Light | Dark | Used for |
| --- | --- | --- | --- |
| `canvas` | `#F4F5F7` | `#121519` | Canvas background |
| `canvas-grid` | `#C3C8D0` | `#4A525D` | Dot grid on the canvas (decorative) |
| `surface` | `#FFFFFF` | `#1C2027` | Panels, blocks, dialogs, cards |
| `surface-alt` | `#EEF0F3` | `#262B33` | Navigation rail, table headers, hovered rows |
| `border` | `#D4D8DE` | `#363D47` | Dividers between panels (decorative) |
| `border-strong` | `#6E7682` | `#8A94A3` | Outlines of inputs, checkboxes and blocks |
| `text` | `#1B1F24` | `#E7EAEE` | Body text |
| `text-muted` | `#4F5866` | `#AAB2BD` | Secondary text, hints, footers |
| `accent` | `#1D5BBF` | `#7EB0FF` | Primary buttons, links, selection, current nav item |
| `on-accent` | `#FFFFFF` | `#0E1116` | Text on an `accent` background |
| `focus` | `#1D5BBF` | `#7EB0FF` | Keyboard focus ring |
| `edge` | `#5F6773` | `#9AA3AF` | Connections, ports |
| `error`, `error-bg` | `#B3261E`, `#FCE8E6` | `#FF8F86`, `#3A1D1B` | Errors |
| `warning`, `warning-bg` | `#8A5300`, `#FFF3D6` | `#F2C063`, `#3A2C0F` | Warnings |
| `success`, `success-bg` | `#1B7332`, `#E4F4E8` | `#79D18E`, `#173222` | Saved, run done |
| `learn` | `#8A3FB8` | `#D29BFF` | Learn-mode step highlight |
| `cat-flow` | `#20727F` | `#5FC3D1` | Category stripe: `source`, `sink`, `delay`, `branch` |
| `cat-work` | `#5B45B0` | `#AC9BFF` | Category stripe: `server`, `queue`, `batch`, `unbatch`, `store` |
| `cat-resource` | `#8C5413` | `#E0A563` | Category stripe: `resource_pool`, `schedule`, `failure` |

The block categories group spec 2's block reference by role: what moves items (flow), what holds or works on them (work), and what changes other blocks without items passing through (resource). The palette uses the same three groups. A block type that a future adapter adds with no category falls under "Other", drawn with `edge`.

**Charts** use, in order, `accent`, `cat-flow`, `cat-work`, `cat-resource` for up to four scenarios, each with its own marker shape (circle, square, triangle, diamond) and a direct label. Beyond four scenarios the colours repeat and the shape and label tell them apart.

### Themes

- **Light, Dark and System** (default: System, which follows the operating system's preference). Set in Settings, "Appearance".
- Both themes define every token, and both pass the contrast table below.
- The canvas, panels and charts change together; nothing keeps a light background in the dark theme.

### Contrast

Computed by `python scripts/contrast.py` from `tokens.json`, with the WCAG 2.2 formulas for relative luminance and contrast ratio. Text pairs need 4.5:1 (success criterion 1.4.3, Level AA). Outlines, focus rings, markers, connections and category stripes need 3:1 against what is next to them (success criterion 1.4.11, Level AA). Decorative tokens (`canvas-grid`, `border`) carry no information and are not listed. `tests/test_design.py` runs the script with `--check` and fails if this table and the script's output differ.

<!-- contrast:start -->

| Theme | Foreground | Background | Used for | Ratio | Needed | Criterion | Result |
| --- | --- | --- | --- | --- | --- | --- | --- |
| light | `text` | `surface` | Body text on panels and blocks | 16.56:1 | 4.5:1 | 1.4.3 | pass |
| light | `text` | `surface-alt` | Text on the nav rail, table headers, hovered rows | 14.51:1 | 4.5:1 | 1.4.3 | pass |
| light | `text` | `canvas` | Text placed on the canvas (notices, empty-canvas hint) | 15.18:1 | 4.5:1 | 1.4.3 | pass |
| light | `text-muted` | `surface` | Secondary text: block type line, hints, footer | 7.19:1 | 4.5:1 | 1.4.3 | pass |
| light | `text-muted` | `surface-alt` | Secondary text on the nav rail and table headers | 6.30:1 | 4.5:1 | 1.4.3 | pass |
| light | `text-muted` | `canvas` | Secondary text on the canvas | 6.59:1 | 4.5:1 | 1.4.3 | pass |
| light | `accent` | `surface` | Links and accent text | 6.36:1 | 4.5:1 | 1.4.3 | pass |
| light | `on-accent` | `accent` | Text on primary buttons (Run, Continue) | 6.36:1 | 4.5:1 | 1.4.3 | pass |
| light | `error` | `surface` | Error text and inline field errors | 6.54:1 | 4.5:1 | 1.4.3 | pass |
| light | `error` | `error-bg` | Error text in the problems list and banners | 5.55:1 | 4.5:1 | 1.4.3 | pass |
| light | `warning` | `surface` | Warning text | 6.33:1 | 4.5:1 | 1.4.3 | pass |
| light | `warning` | `warning-bg` | Warning text in the problems list and banners | 5.74:1 | 4.5:1 | 1.4.3 | pass |
| light | `success` | `surface` | Run done, saved state | 5.92:1 | 4.5:1 | 1.4.3 | pass |
| light | `success` | `success-bg` | Success banner text | 5.19:1 | 4.5:1 | 1.4.3 | pass |
| light | `learn` | `surface` | Learn-mode step label | 6.03:1 | 4.5:1 | 1.4.3 | pass |
| light | `border-strong` | `surface` | Input, checkbox and block outlines | 4.59:1 | 3.0:1 | 1.4.11 | pass |
| light | `border-strong` | `canvas` | Block outline against the canvas | 4.21:1 | 3.0:1 | 1.4.11 | pass |
| light | `focus` | `surface` | Focus ring on panels | 6.36:1 | 3.0:1 | 1.4.11 | pass |
| light | `focus` | `canvas` | Focus ring and selection outline on the canvas | 5.83:1 | 3.0:1 | 1.4.11 | pass |
| light | `edge` | `canvas` | Connection lines and ports | 5.24:1 | 3.0:1 | 1.4.11 | pass |
| light | `edge` | `surface` | Port circles on a block | 5.72:1 | 3.0:1 | 1.4.11 | pass |
| light | `error` | `canvas` | Error marker on the canvas | 5.99:1 | 3.0:1 | 1.4.11 | pass |
| light | `warning` | `canvas` | Warning marker on the canvas | 5.80:1 | 3.0:1 | 1.4.11 | pass |
| light | `learn` | `canvas` | Learn-mode highlight ring | 5.53:1 | 3.0:1 | 1.4.11 | pass |
| light | `cat-flow` | `surface` | Category stripe and icon: flow blocks | 5.56:1 | 3.0:1 | 1.4.11 | pass |
| light | `cat-work` | `surface` | Category stripe and icon: work blocks | 7.18:1 | 3.0:1 | 1.4.11 | pass |
| light | `cat-resource` | `surface` | Category stripe and icon: resource blocks | 6.19:1 | 3.0:1 | 1.4.11 | pass |
| light | `accent` | `surface` | Selected nav item marker, toggle on | 6.36:1 | 3.0:1 | 1.4.11 | pass |
| dark | `text` | `surface` | Body text on panels and blocks | 13.54:1 | 4.5:1 | 1.4.3 | pass |
| dark | `text` | `surface-alt` | Text on the nav rail, table headers, hovered rows | 11.79:1 | 4.5:1 | 1.4.3 | pass |
| dark | `text` | `canvas` | Text placed on the canvas (notices, empty-canvas hint) | 15.17:1 | 4.5:1 | 1.4.3 | pass |
| dark | `text-muted` | `surface` | Secondary text: block type line, hints, footer | 7.63:1 | 4.5:1 | 1.4.3 | pass |
| dark | `text-muted` | `surface-alt` | Secondary text on the nav rail and table headers | 6.65:1 | 4.5:1 | 1.4.3 | pass |
| dark | `text-muted` | `canvas` | Secondary text on the canvas | 8.55:1 | 4.5:1 | 1.4.3 | pass |
| dark | `accent` | `surface` | Links and accent text | 7.42:1 | 4.5:1 | 1.4.3 | pass |
| dark | `on-accent` | `accent` | Text on primary buttons (Run, Continue) | 8.59:1 | 4.5:1 | 1.4.3 | pass |
| dark | `error` | `surface` | Error text and inline field errors | 7.41:1 | 4.5:1 | 1.4.3 | pass |
| dark | `error` | `error-bg` | Error text in the problems list and banners | 6.95:1 | 4.5:1 | 1.4.3 | pass |
| dark | `warning` | `surface` | Warning text | 9.72:1 | 4.5:1 | 1.4.3 | pass |
| dark | `warning` | `warning-bg` | Warning text in the problems list and banners | 8.08:1 | 4.5:1 | 1.4.3 | pass |
| dark | `success` | `surface` | Run done, saved state | 8.81:1 | 4.5:1 | 1.4.3 | pass |
| dark | `success` | `success-bg` | Success banner text | 7.47:1 | 4.5:1 | 1.4.3 | pass |
| dark | `learn` | `surface` | Learn-mode step label | 7.68:1 | 4.5:1 | 1.4.3 | pass |
| dark | `border-strong` | `surface` | Input, checkbox and block outlines | 5.33:1 | 3.0:1 | 1.4.11 | pass |
| dark | `border-strong` | `canvas` | Block outline against the canvas | 5.97:1 | 3.0:1 | 1.4.11 | pass |
| dark | `focus` | `surface` | Focus ring on panels | 7.42:1 | 3.0:1 | 1.4.11 | pass |
| dark | `focus` | `canvas` | Focus ring and selection outline on the canvas | 8.32:1 | 3.0:1 | 1.4.11 | pass |
| dark | `edge` | `canvas` | Connection lines and ports | 7.18:1 | 3.0:1 | 1.4.11 | pass |
| dark | `edge` | `surface` | Port circles on a block | 6.40:1 | 3.0:1 | 1.4.11 | pass |
| dark | `error` | `canvas` | Error marker on the canvas | 8.30:1 | 3.0:1 | 1.4.11 | pass |
| dark | `warning` | `canvas` | Warning marker on the canvas | 10.89:1 | 3.0:1 | 1.4.11 | pass |
| dark | `learn` | `canvas` | Learn-mode highlight ring | 8.61:1 | 3.0:1 | 1.4.11 | pass |
| dark | `cat-flow` | `surface` | Category stripe and icon: flow blocks | 7.95:1 | 3.0:1 | 1.4.11 | pass |
| dark | `cat-work` | `surface` | Category stripe and icon: work blocks | 6.91:1 | 3.0:1 | 1.4.11 | pass |
| dark | `cat-resource` | `surface` | Category stripe and icon: resource blocks | 7.57:1 | 3.0:1 | 1.4.11 | pass |
| dark | `accent` | `surface` | Selected nav item marker, toggle on | 7.42:1 | 3.0:1 | 1.4.11 | pass |

<!-- contrast:end -->

The lowest text pair is 5.19:1 (light `success` on `success-bg`); the lowest non-text pair is 4.21:1 (light `border-strong` against `canvas`). No pair relies on the large-text exception.

## Type

| Role | Size | Weight | Line height | Used for |
| --- | --- | --- | --- | --- |
| Title | 24 px | 600 | 32 px | Screen titles ("Results"), first-start notice heading |
| Heading | 20 px | 600 | 28 px | Panel and section headings |
| Subheading | 16 px | 600 | 24 px | Card titles, block-type names in the palette |
| Body | 14 px | 400 | 21 px | Forms, lists, findings, block titles (600) |
| Small | 12 px | 400 | 18 px | Block type line, port and route labels, results footer, table notes |
| Mono | 13 px | 400 | 20 px | Component ids, metric names (`till.wait.mean`), run ids |

- **Families.** Sans: `system-ui, "Segoe UI", "Noto Sans", Cantarell, "DejaVu Sans", sans-serif`. Mono: `ui-monospace, "Cascadia Mono", "DejaVu Sans Mono", monospace`. All ship with Windows or common Linux desktops.
- **Units.** Sizes are set in `rem` against a 16 px root. The text-size setting (100%, 125%, 150%, 175%, 200%) changes the root size, so all text scales together (success criterion 1.4.4).
- **Numbers** use tabular figures in tables and the run monitor, so columns line up.
- **Units in text.** Values are shown with display units ("4.5 min", "75%"), as spec 4 asks for finding text.

## Spacing and layout

- **Spacing scale:** 4, 8, 12, 16, 24, 32, 48 px. Inside controls 8 px; between controls 12 px; between sections 24 px.
- **Radius:** 4 px for controls and blocks, 8 px for cards and dialogs.
- **Elevation:** none. Panels are separated by 1 px `border` lines. Dialogs sit on a scrim of `#000000` at 40% opacity.
- **Window:** designed at 1280 × 800 and usable at 1024 × 640. Below 1024 px wide the side panel becomes an overlay that opens on selection.

| Region | Size at 1280 × 800 | Content |
| --- | --- | --- |
| Navigation rail | 72 px wide, left | The seven screens of spec 3: Home, Canvas, Data, Experiment, Run monitor, Results, Settings; icon and word for each |
| Top bar | 48 px high | Project name, save state, experiment selector, Run button with its reason text |
| Palette | 208 px wide (Canvas screen only) | Block types in three groups, with a filter box |
| Main area | The rest | The current screen |
| Side panel | 320 px wide, right (Canvas screen only) | The selection's settings, or the model's parameters when nothing is selected |
| Problems list | 160 px high, under the canvas, resizable, collapsible | Issues from the last validation |

## Controls

| Control | Style |
| --- | --- |
| Primary button | `accent` background, `on-accent` text, 36 px high, 16 px side padding; one per view (Run, Continue, Start run) |
| Secondary button | `surface` background, 1 px `border-strong` outline, `text` |
| Disabled button | `surface-alt` background, `text-muted` text, and the reason as visible text beside it (spec 3 "Run") |
| Text field | 32 px high, 1 px `border-strong` outline, label above, hint below in `text-muted`, error below in `error` with an error icon |
| Quantity field | Text field holding number and unit together, as in the model file ("2 min"); spec 1 units |
| Distribution field | A type picker (`exponential`, `normal`, ...) and the fields that type needs (spec 1 distribution list) |
| Parameter link | A toggle "Use parameter" beside a number or quantity field; when on, the field becomes a picker of the model's parameters (`{"$param": "id"}`, spec 1) |
| Tabs, lists, tables | Row height 32 px; selected row `surface-alt` with a 3 px `accent` marker at the left |
| Notice (one line) | `surface` with a 4 px stripe in `accent`, `warning` or `error`, an icon, the text, and a close button |
| Focus ring | 2 px solid `focus`, 2 px offset, on every focusable element |

Every pointer target is at least 24 × 24 px (success criterion 2.5.8); buttons are 36 px high.

## Block styles

A block draws one model component (spec 1 "Components and ports").

```text
 4 px category stripe
 |
 +-------------------------------------+
 |  [icon] till                    (!) |   title: label if set, else id (Body, 600)
 o in     server · capacity 1    out  o|   type line (Small, text-muted)
 |                                     |
 +-------------------------------------+
   176 x 72 px, radius 4, 1 px border-strong outline on surface
```

- **Size.** 176 × 72 px at 100% zoom. A `branch` with more than two routes grows by 20 px per extra route, so each route port has its own row.
- **Title.** The component's `label` when it has one, otherwise its `id`. When a label is shown, the id appears in Mono in the type line, so the id that findings and metrics use is always visible.
- **Type line.** The type and one key setting: `server · capacity 1`, `source · every 2 min (exponential)`, `delay · 5 min (triangular)`. A setting that names a parameter shows its name: `capacity = tills`.
- **Icon.** 16 px, in the category colour, one per block type. The type word is always printed, so the icon is never the only cue.
- **Blocks without ports** (`resource_pool`, `schedule`, `failure`; spec 2 "Block reference") have a dashed outline and no port circles, and are 176 × 56 px. Their references are drawn as reference lines (below).

### Block states

| State | Shown by |
| --- | --- |
| Default | 1 px `border-strong` outline |
| Hover | Outline 2 px |
| Selected | 2 px `accent` outline and `surface-alt` title row |
| Keyboard focus | 2 px `focus` ring, 2 px outside the outline (with selection both show) |
| Error | 2 px `error` outline and a 20 px round badge at the top right: `error` fill with a "!" in `surface` (the same pair as `error` on `surface` in the table below), and the number of errors beside it |
| Warning (no errors) | A 20 px triangular badge at the top right: `warning` fill with a "!" in `surface` (the same pair as `warning` on `surface`), and the number of warnings beside it |
| Learn highlight | 3 px `learn` ring and a tag above the block, "Step 2 of 5" |
| Run in progress | No change on blocks; progress is on the Run monitor |

Badges sit inside the block's bounding box so they are never clipped at low zoom; below 50% zoom the title and type line are hidden and only the stripe, icon and badges remain.

## Port styles

- **Input ports** on the left edge, **output ports** on the right edge, vertically centred; spec 1: most blocks have `in` and `out`, a `source` only `out`, a `sink` only `in`, a `branch` one output per route.
- **Circle:** 12 px, 2 px `edge` outline, `surface` fill. Connected ports are filled with `edge`.
- **Hit target:** 24 × 24 px around each circle (success criterion 2.5.8).
- **Labels:** a `branch` route port shows its route id in Small text inside the block, beside the port. Other ports are labelled only in their accessible name ("till, output port out").
- **While connecting:** ports that can accept the connection get a 2 px `accent` ring; others are unchanged. An output port that is already connected shows its current target in the tooltip and in the side panel, because the new connection replaces it (spec 3 "Connect").
- **Errors are shown on the block, not the port.** A spec 1 issue names a component and a `path`, not a port, so port-level markers would have to guess from the message text.

## Connection styles

- **Connection:** 2 px `edge` line, right-angled with rounded corners, from an output port to an input port, with a small arrowhead at the input end.
- **Hover:** 3 px. **Selected:** 3 px `accent`.
- **Reference line:** a dashed 1.5 px `edge` line with no arrowhead and a Small label (`pool`, `target`), from a `server` to its `pool`, and from a `schedule` or `failure` to its `target` (spec 2). A reference line is not a connection: it cannot be selected or deleted on the canvas, and it changes only when the setting changes in the side panel.

## Motion

None is needed. Panels open without animation; the canvas pans and zooms directly. When "reduce motion" is set in the operating system, any later animation must be removed (success criterion 2.3.3 is Level AAA; it is followed anyway because it costs nothing).

## Changes

- 2026-11-06: first version (AKS-118).
