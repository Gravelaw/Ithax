# Design system

The design system for the Phase 1 interface: colour tokens, type, icons, spacing, layout, controls, block, port and line styles, motion, charts, and the light and dark themes. It serves spec 3 "Design before building" (fourth item). The canvas behaviour it styles is in `canvas-interactions.md`; the accessibility checks are in `accessibility.md`.

Version 2, from the owner design review of 2026-11-06 (`docs/DECISIONS.md`, "Owner design review"). The owner found version 1 functional but plain, "like a traditional ERP interface", and approved the look shown in the review's preview (`preview/owner-review.html`, section "Proposed new look"). The research behind it is in `docs/research/spec-3-wada-palette.md`, `spec-3-engaging-design.md`, `spec-3-icons-and-type.md` and `spec-3-results-visualization.md`.

Principles, from spec 0, the interface study and the owner review:

1. **Warm, clear and alive.** Students and business users with no code are the main users (spec 0 "Users"). The interface should invite them back: a warm paper-and-ink palette, rounded shapes with meaning, icons on every button, a model that visibly works after a run. Every flourish carries information or can be turned off.
2. **Never colour alone.** Every state shown in colour also has a shape, a pattern, an icon or a word (WCAG 2.2 success criterion 1.4.1).
3. **Readable at a distance and on a low-tier laptop.** Text sizes start at 12 px and scale with the text-size setting; no effect depends on graphics hardware (spec 3 "Hardware tiers").
4. **Works offline.** Fonts and icons are bundled with the app; nothing is downloaded at run time (spec 0 principle 6).

## Colour tokens

The single source is `docs/design/tokens.json`. Interface code reads token names, never raw colours. Each theme defines every token.

The palette is drawn from Sanzo Wada's *A Dictionary of Color Combinations* (*Haishoku Sōkan*, 1933 to 1934), mainly combinations 247 (Raw Sienna, Apricot Yellow, Benzol Green, Deep Lyons Blue) and 335 (Vandyke Red, Yellow Orange, Violet, Slate Color), with 38 and 344 for success and Learn. Values come from the MIT-licensed dataset `mattdesl/dictionary-of-colour-combinations` 1.0.2; they approximate printed inks. "Derived" means a Wada colour lightened, darkened or mixed so that it passes its contrast threshold. The dark theme uses softer, less saturated versions of the Wada hues, at the owner's request ("too sharp to the eye"). Wada is credited here as the source only; no theme or feature is named after him.

| Token | Light | Light source | Dark | Dark source | Used for |
| --- | --- | --- | --- | --- | --- |
| `canvas` | `#F9F3E5` | Ivory Buff tint | `#1B2023` | Slate Color with Black | Canvas background |
| `canvas-grid` | `#BBB49D` | Ivory Buff with Warm Gray | `#4A5A5B` | Slate Color with Andover Green | Dot grid (decorative) |
| `surface` | `#FDFAF4` | Ivory Buff tint | `#232B2F` | Slate Color with Black | Panels, blocks, dialogs, cards |
| `surface-alt` | `#F7EEDC` | Ivory Buff tint | `#2B353A` | Slate Color with Black | Navigation rail highlight, table headers, hovered rows |
| `border` | `#CABD9E` | Ivory Buff with Warm Gray | `#3A4A4F` | Slate Color with Andover Green | Dividers (decorative) |
| `border-strong` | `#6D7E77` | Andover Green | `#7D8A88` | Mineral Gray, derived | Outlines of inputs and blocks |
| `text` | `#34454C` | Slate Color | `#D8D1AD` | Sulpher Yellow, softened | Body text |
| `text-muted` | `#547076` | Dark Medici Blue | `#A4ADAF` | Neutral Gray, softened | Secondary text, hints, footers |
| `accent`, `focus` | `#1C4286` | Deep Lyons Blue | `#96A8BE` | Salvia Blue, softened | Primary buttons, links, selection, focus ring |
| `on-accent` | `#FDFAF4` | = `surface` | `#1B2023` | = `canvas` | Text on an `accent` background |
| `edge` | `#547076` | Dark Medici Blue | `#95A3A0` | Mineral Gray, softened | Flow connections, ports |
| `error`, `error-bg` | `#82241F`, `#F1E5DF` | Vandyke Red | `#D2908A`, `#3A2A2A` | Coral Red, softened | Errors, bottleneck tag |
| `warning`, `warning-bg` | `#915604`, `#FCEBD1` | Yellow Orange, derived | `#C99B39`, `#312C21` | Orange Yellow, softened | Warnings |
| `success`, `success-bg` | `#1A7444`, `#E9EEE4` | Diamine Green | `#96C0A4`, `#20382F` | Cobalt Green, softened | Saved, run done, "Added" review mark |
| `learn` | `#8F5891` | Aconite Violet, derived | `#B588AD` | Lilac, softened | Learn-mode highlight |
| `cat-flow` | `#00978D` | Benzol Green | `#69A9A5` | Venice Green, softened | Flow blocks |
| `cat-work` | `#4F4086` | Violet | `#B2AFCD` | Grayish Lavender A, softened | Work blocks |
| `cat-resource` | `#BB7125` | Raw Sienna | `#CBA786` | Pinkish Cinnamon, softened | Resource blocks and their reference lines |
| `chart-1` to `chart-4` | `#1C4286`, `#BB7125`, `#00978D`, `#8F5891` | Deep Lyons Blue, Raw Sienna, Benzol Green, Aconite Violet | `#96A8BE`, `#CBA786`, `#69A9A5`, `#B588AD` | Softened | Chart series, in order |
| `chart-cb-1` to `chart-cb-4` | `#0072B2`, `#C35A00`, `#008061`, `#B5528F` | Okabe and Ito hues, darkened | `#56B4E9`, `#E69F00`, `#2CB38A`, `#D98CBA` | Okabe and Ito hues | Chart series, colour-blind safe option |

The block categories group spec 2's block reference by role: what moves items (flow), what holds or works on them (work), and what changes other blocks without items passing through (resource). The palette uses the same three groups (owner review choice 12). A block type that a future adapter adds with no category falls under "Other", drawn with `edge`.

### Charts

- **Library:** Apache ECharts (Apache-2.0), drawn with SVG or canvas, never WebGL (`docs/research/spec-3-results-visualization.md`). Recorded for M9, not yet added.
- **Series colours:** `chart-1` to `chart-4` in order, each series with its own marker shape (circle, square, triangle, diamond) and a direct label. Beyond four series the colours repeat and the shape and label tell them apart.
- **Colour-blind safe option** (owner review): Settings, Appearance, "Colour-blind safe charts". When on, charts use `chart-cb-1` to `chart-cb-4`, hues chosen by Okabe and Ito to stay distinct for the common forms of colour blindness. It is off by default; shapes and labels are always on, so charts never rely on colour alone either way.
- **Every chart has a data table** beside it with the same numbers ("Show as table").
- **The charts per screen** are listed in `docs/research/spec-3-results-visualization.md` "Decision": the Data histogram with the fitted curve, live key-number trends on the Run monitor, the search's best-so-far chart (one dot per candidate, filled when feasible, hollow when not), one dot per replication with the mean and its interval on Results, and the sortable table of all search candidates. Uncertainty is shown in plain words: "likely range of the average", not "95% confidence interval" (the term appears in the hover explanation).

### Themes

- **Light, Dark and System** (default: System). Set in Settings, "Appearance".
- Both themes define every token, and both pass the contrast table below.
- The canvas, panels and charts change together.

### Contrast

Computed by `python scripts/contrast.py` from `tokens.json`, with the WCAG 2.2 formulas for relative luminance and contrast ratio. Text pairs need 4.5:1 (success criterion 1.4.3, Level AA). Outlines, focus rings, markers, lines, category colours and chart series need 3:1 against what is next to them (success criterion 1.4.11, Level AA). Decorative tokens (`canvas-grid`, `border`) carry no information and are not listed. `tests/test_design.py` runs the script with `--check` and fails if this table and the script's output differ.

<!-- contrast:start -->

| Theme | Foreground | Background | Used for | Ratio | Needed | Criterion | Result |
| --- | --- | --- | --- | --- | --- | --- | --- |
| light | `text` | `surface` | Body text on panels and blocks | 9.59:1 | 4.5:1 | 1.4.3 | pass |
| light | `text` | `surface-alt` | Text on the nav rail, table headers, hovered rows | 8.66:1 | 4.5:1 | 1.4.3 | pass |
| light | `text` | `canvas` | Text placed on the canvas (notices, empty-canvas hint) | 9.03:1 | 4.5:1 | 1.4.3 | pass |
| light | `text-muted` | `surface` | Secondary text: block type line, hints, footer | 5.09:1 | 4.5:1 | 1.4.3 | pass |
| light | `text-muted` | `surface-alt` | Secondary text on the nav rail and table headers | 4.60:1 | 4.5:1 | 1.4.3 | pass |
| light | `text-muted` | `canvas` | Secondary text on the canvas | 4.79:1 | 4.5:1 | 1.4.3 | pass |
| light | `accent` | `surface` | Links and accent text | 9.27:1 | 4.5:1 | 1.4.3 | pass |
| light | `on-accent` | `accent` | Text on primary buttons (Run, Continue) | 9.27:1 | 4.5:1 | 1.4.3 | pass |
| light | `error` | `surface` | Error text and inline field errors | 9.07:1 | 4.5:1 | 1.4.3 | pass |
| light | `error` | `error-bg` | Error text in the problems list and banners | 7.65:1 | 4.5:1 | 1.4.3 | pass |
| light | `warning` | `surface` | Warning text | 5.69:1 | 4.5:1 | 1.4.3 | pass |
| light | `warning` | `warning-bg` | Warning text in the problems list and banners | 5.07:1 | 4.5:1 | 1.4.3 | pass |
| light | `success` | `surface` | Run done, saved state | 5.55:1 | 4.5:1 | 1.4.3 | pass |
| light | `success` | `success-bg` | Success banner text | 4.91:1 | 4.5:1 | 1.4.3 | pass |
| light | `learn` | `surface` | Learn-mode step label | 5.07:1 | 4.5:1 | 1.4.3 | pass |
| light | `border-strong` | `surface` | Input, checkbox and block outlines | 4.11:1 | 3.0:1 | 1.4.11 | pass |
| light | `border-strong` | `canvas` | Block outline against the canvas | 3.87:1 | 3.0:1 | 1.4.11 | pass |
| light | `focus` | `surface` | Focus ring on panels | 9.27:1 | 3.0:1 | 1.4.11 | pass |
| light | `focus` | `canvas` | Focus ring and selection outline on the canvas | 8.73:1 | 3.0:1 | 1.4.11 | pass |
| light | `edge` | `canvas` | Connection lines and ports | 4.79:1 | 3.0:1 | 1.4.11 | pass |
| light | `edge` | `surface` | Port circles on a block | 5.09:1 | 3.0:1 | 1.4.11 | pass |
| light | `error` | `canvas` | Error marker on the canvas | 8.54:1 | 3.0:1 | 1.4.11 | pass |
| light | `warning` | `canvas` | Warning marker on the canvas | 5.36:1 | 3.0:1 | 1.4.11 | pass |
| light | `learn` | `canvas` | Learn-mode highlight ring | 4.77:1 | 3.0:1 | 1.4.11 | pass |
| light | `cat-flow` | `surface` | Category stripe and icon: flow blocks | 3.46:1 | 3.0:1 | 1.4.11 | pass |
| light | `cat-work` | `surface` | Category stripe and icon: work blocks | 8.36:1 | 3.0:1 | 1.4.11 | pass |
| light | `cat-resource` | `surface` | Category stripe and icon: resource blocks | 3.66:1 | 3.0:1 | 1.4.11 | pass |
| light | `accent` | `surface` | Selected nav item marker, toggle on | 9.27:1 | 3.0:1 | 1.4.11 | pass |
| light | `cat-resource` | `canvas` | Resource reference lines (pool, schedule, failure) on the canvas | 3.44:1 | 3.0:1 | 1.4.11 | pass |
| light | `chart-1` | `surface` | Chart series 1 (Sanzo Wada order) | 9.27:1 | 3.0:1 | 1.4.11 | pass |
| light | `chart-2` | `surface` | Chart series 2 (Sanzo Wada order) | 3.66:1 | 3.0:1 | 1.4.11 | pass |
| light | `chart-3` | `surface` | Chart series 3 (Sanzo Wada order) | 3.46:1 | 3.0:1 | 1.4.11 | pass |
| light | `chart-4` | `surface` | Chart series 4 (Sanzo Wada order) | 5.07:1 | 3.0:1 | 1.4.11 | pass |
| light | `chart-cb-1` | `surface` | Chart series 1, colour-blind safe option (Okabe and Ito hues) | 4.97:1 | 3.0:1 | 1.4.11 | pass |
| light | `chart-cb-2` | `surface` | Chart series 2, colour-blind safe option (Okabe and Ito hues) | 4.21:1 | 3.0:1 | 1.4.11 | pass |
| light | `chart-cb-3` | `surface` | Chart series 3, colour-blind safe option (Okabe and Ito hues) | 4.73:1 | 3.0:1 | 1.4.11 | pass |
| light | `chart-cb-4` | `surface` | Chart series 4, colour-blind safe option (Okabe and Ito hues) | 4.41:1 | 3.0:1 | 1.4.11 | pass |
| dark | `text` | `surface` | Body text on panels and blocks | 9.35:1 | 4.5:1 | 1.4.3 | pass |
| dark | `text` | `surface-alt` | Text on the nav rail, table headers, hovered rows | 8.15:1 | 4.5:1 | 1.4.3 | pass |
| dark | `text` | `canvas` | Text placed on the canvas (notices, empty-canvas hint) | 10.67:1 | 4.5:1 | 1.4.3 | pass |
| dark | `text-muted` | `surface` | Secondary text: block type line, hints, footer | 6.29:1 | 4.5:1 | 1.4.3 | pass |
| dark | `text-muted` | `surface-alt` | Secondary text on the nav rail and table headers | 5.48:1 | 4.5:1 | 1.4.3 | pass |
| dark | `text-muted` | `canvas` | Secondary text on the canvas | 7.18:1 | 4.5:1 | 1.4.3 | pass |
| dark | `accent` | `surface` | Links and accent text | 5.92:1 | 4.5:1 | 1.4.3 | pass |
| dark | `on-accent` | `accent` | Text on primary buttons (Run, Continue) | 6.76:1 | 4.5:1 | 1.4.3 | pass |
| dark | `error` | `surface` | Error text and inline field errors | 5.55:1 | 4.5:1 | 1.4.3 | pass |
| dark | `error` | `error-bg` | Error text in the problems list and banners | 5.24:1 | 4.5:1 | 1.4.3 | pass |
| dark | `warning` | `surface` | Warning text | 5.64:1 | 4.5:1 | 1.4.3 | pass |
| dark | `warning` | `warning-bg` | Warning text in the problems list and banners | 5.44:1 | 4.5:1 | 1.4.3 | pass |
| dark | `success` | `surface` | Run done, saved state | 7.11:1 | 4.5:1 | 1.4.3 | pass |
| dark | `success` | `success-bg` | Success banner text | 6.21:1 | 4.5:1 | 1.4.3 | pass |
| dark | `learn` | `surface` | Learn-mode step label | 4.86:1 | 4.5:1 | 1.4.3 | pass |
| dark | `border-strong` | `surface` | Input, checkbox and block outlines | 4.02:1 | 3.0:1 | 1.4.11 | pass |
| dark | `border-strong` | `canvas` | Block outline against the canvas | 4.58:1 | 3.0:1 | 1.4.11 | pass |
| dark | `focus` | `surface` | Focus ring on panels | 5.92:1 | 3.0:1 | 1.4.11 | pass |
| dark | `focus` | `canvas` | Focus ring and selection outline on the canvas | 6.76:1 | 3.0:1 | 1.4.11 | pass |
| dark | `edge` | `canvas` | Connection lines and ports | 6.28:1 | 3.0:1 | 1.4.11 | pass |
| dark | `edge` | `surface` | Port circles on a block | 5.50:1 | 3.0:1 | 1.4.11 | pass |
| dark | `error` | `canvas` | Error marker on the canvas | 6.33:1 | 3.0:1 | 1.4.11 | pass |
| dark | `warning` | `canvas` | Warning marker on the canvas | 6.44:1 | 3.0:1 | 1.4.11 | pass |
| dark | `learn` | `canvas` | Learn-mode highlight ring | 5.54:1 | 3.0:1 | 1.4.11 | pass |
| dark | `cat-flow` | `surface` | Category stripe and icon: flow blocks | 5.36:1 | 3.0:1 | 1.4.11 | pass |
| dark | `cat-work` | `surface` | Category stripe and icon: work blocks | 6.79:1 | 3.0:1 | 1.4.11 | pass |
| dark | `cat-resource` | `surface` | Category stripe and icon: resource blocks | 6.45:1 | 3.0:1 | 1.4.11 | pass |
| dark | `accent` | `surface` | Selected nav item marker, toggle on | 5.92:1 | 3.0:1 | 1.4.11 | pass |
| dark | `cat-resource` | `canvas` | Resource reference lines (pool, schedule, failure) on the canvas | 7.36:1 | 3.0:1 | 1.4.11 | pass |
| dark | `chart-1` | `surface` | Chart series 1 (Sanzo Wada order) | 5.92:1 | 3.0:1 | 1.4.11 | pass |
| dark | `chart-2` | `surface` | Chart series 2 (Sanzo Wada order) | 6.45:1 | 3.0:1 | 1.4.11 | pass |
| dark | `chart-3` | `surface` | Chart series 3 (Sanzo Wada order) | 5.36:1 | 3.0:1 | 1.4.11 | pass |
| dark | `chart-4` | `surface` | Chart series 4 (Sanzo Wada order) | 4.86:1 | 3.0:1 | 1.4.11 | pass |
| dark | `chart-cb-1` | `surface` | Chart series 1, colour-blind safe option (Okabe and Ito hues) | 6.24:1 | 3.0:1 | 1.4.11 | pass |
| dark | `chart-cb-2` | `surface` | Chart series 2, colour-blind safe option (Okabe and Ito hues) | 6.39:1 | 3.0:1 | 1.4.11 | pass |
| dark | `chart-cb-3` | `surface` | Chart series 3, colour-blind safe option (Okabe and Ito hues) | 5.43:1 | 3.0:1 | 1.4.11 | pass |
| dark | `chart-cb-4` | `surface` | Chart series 4, colour-blind safe option (Okabe and Ito hues) | 5.76:1 | 3.0:1 | 1.4.11 | pass |

<!-- contrast:end -->

The lowest text pairs are 4.60:1 (light `text-muted` on `surface-alt`) and 4.86:1 (dark `learn` on `surface`); the lowest non-text pairs are 3.44:1 (light `cat-resource` on `canvas`) and 4.02:1 (dark `border-strong` on `surface`). No pair relies on the large-text exception. The light `text-muted` on `surface-alt` margin is thin; a later palette change must keep it at or above 4.5:1.

## Type

Fonts are bundled with the app and never downloaded at run time (owner review choice 11). All three are under the SIL Open Font License 1.1 (`docs/research/spec-3-icons-and-type.md`).

| Role | Family | Size | Weight | Line height | Used for |
| --- | --- | --- | --- | --- | --- |
| Title | Bricolage Grotesque | 24 px | 700 | 32 px | Screen titles, the results headline card, first-start notice heading |
| Heading | Bricolage Grotesque | 20 px | 650 | 28 px | Panel and section headings |
| Subheading | Atkinson Hyperlegible Next | 16 px | 700 | 24 px | Card titles, block-type names in the palette |
| Body | Atkinson Hyperlegible Next | 14 px | 400 | 21 px | Forms, lists, findings, block titles (700) |
| Small | Atkinson Hyperlegible Next | 12 px | 400 | 18 px | Block type line, port and line labels, results footer, table notes |
| Mono | JetBrains Mono | 13 px | 400 | 20 px | Component ids, metric names (`till.wait.mean`), run ids |

- **Why these.** Bricolage Grotesque gives headings character without hurting reading. Atkinson Hyperlegible Next was designed for readers with low vision; its I, l and 1, and O and 0, are clearly different, which matters for ids such as `till_1`. JetBrains Mono lines up digits and separates similar characters.
- **Fallback stacks.** Sans: `"Atkinson Hyperlegible Next", system-ui, "Segoe UI", "Noto Sans", sans-serif`. Display: `"Bricolage Grotesque", system-ui, sans-serif`. Mono: `"JetBrains Mono", ui-monospace, "Cascadia Mono", "DejaVu Sans Mono", monospace`.
- **Units.** Sizes are set in `rem` against a 16 px root. The text-size setting (100% to 200%) changes the root size, so all text scales together (success criterion 1.4.4).
- **Numbers** use tabular figures in tables and the run monitor.
- **Plain words.** The interface uses everyday words and explains the technical one on hover or focus: "repeat runs" (replications), "settling-in time" (warm-up), "likely range of the average" (confidence interval), "how well the pattern fits" (fit score). Ids and metric names stay as they are, in Mono.

## Icons

Phosphor Icons (`@phosphor-icons/react`, MIT), bundled with the app (`docs/research/spec-3-icons-and-type.md`). Regular weight on buttons, fill weight for the current screen in the navigation rail, duotone on blocks and in the palette. Every icon has a visible word beside it or an accessible name; no icon is the only cue.

| Where | Item | Icon |
| --- | --- | --- |
| Navigation rail | Home, Canvas, Data, Experiment, Run monitor, Results, Settings | `House`, `FlowArrow`, `Table`, `Flask`, `Pulse`, `ChartBar`, `GearSix` |
| Canvas buttons | Zoom in, Zoom out, Fit, Undo, Redo, Run, Delete, Connect, Find | `MagnifyingGlassPlus`, `MagnifyingGlassMinus`, `CornersOut`, `ArrowUUpLeft`, `ArrowUUpRight`, `Play`, `Trash`, `PlugsConnected`, `MagnifyingGlass` |
| Flow blocks | `source`, `sink`, `delay`, `branch` | `SignIn`, `SignOut`, `Timer`, `ArrowsSplit` |
| Work blocks | `server`, `queue`, `batch`, `unbatch`, `store` | `UserGear`, `Rows`, `BoxArrowDown`, `BoxArrowUp`, `Warehouse` |
| Resource blocks | `resource_pool`, `schedule`, `failure` | `UsersThree`, `CalendarDots`, `Wrench` |
| States | Saved, error, warning, finding headline | `CheckCircle`, `WarningCircle`, warning triangle badge, `Trophy` |
| Review of an outside change (AKS-137) | "N changes to review" and the Changed and Removed chips, Added chip, Accept, Reject | `ListChecks`, `Plus`, `Check`, `ArrowCounterClockwise` |
| Optimization views (AKS-137) | Table view, Diagram view, Decisions, Goal, Limits, Add, Remove | `Table`, `Graph`, `SlidersHorizontal`, `Target`, `Gauge`, `Plus`, `Trash` |

`failure` uses a wrench, not a warning triangle, because the triangle marks warnings. `Rows` for `queue` is to be checked by eye at M9; if it does not read as a queue, a custom icon on Phosphor's 256-unit grid replaces it.

## Spacing and layout

- **Spacing scale:** 4, 8, 12, 16, 24, 32, 48 px. Inside controls 8 px; between controls 12 px; between sections 24 px.
- **Radius:** 8 px for controls, 14 px for work blocks and cards, full (pill) for primary buttons, chips and flow blocks.
- **Depth:** panels and cards sit on soft shadows instead of grey divider lines (light: `0 1px 2px` and `0 4px 14px` of `text` at 8 to 10%; dark: black at 35 to 40%). Dialogs sit on a scrim of `#000000` at 40% opacity.
- **Window:** designed at 1280 × 800 and usable at 1024 × 640. Below 1024 px wide the side panel becomes an overlay that opens on selection.

| Region | Size at 1280 × 800 | Content |
| --- | --- | --- |
| Navigation rail | 76 px wide, left | The seven screens of spec 3, each an icon with its word under it; the current screen has a tinted rounded background and a filled icon |
| Top bar | 52 px high | Project name, save state, "N changes to review" when present, Undo, Redo, experiment selector, Run with its reason text |
| Palette | 190 to 208 px wide (Canvas screen only) | Block types in three groups, each with an icon disc, and a filter box |
| Main area | The rest | The current screen |
| Side panel | 250 to 320 px wide, right (Canvas screen only) | The selection's settings, or the model's parameters when nothing is selected, or "Changes to review" |
| Problems list | 160 px high, under the canvas, resizable, collapsible | Issues from the last validation |

## Controls

| Control | Style |
| --- | --- |
| Primary button | `accent` background, `on-accent` text, pill shape, 36 px high, icon then word (Run, Continue, Start run); one per view |
| Secondary button | `surface` background, 1 px `border-strong` outline, `text` |
| Icon button | 34 × 34 px, 8 px radius, icon with an accessible name and a tooltip |
| Disabled button | `surface-alt` background, `text-muted` text, and the reason as visible text beside it (spec 3 "Run"). Pointer: "not allowed" (circle with a line) when blocked by errors; "progress" (arrow with spinner) while saving or checking (owner review choice 9) |
| Destructive button | `error` background, `surface` text, with an icon (Delete) |
| Text field | 32 px high, 1 px `border-strong` outline, label above, hint below in `text-muted`, error below in `error` with an error icon |
| Quantity field | Text field holding number and unit together ("2 min"); spec 1 units |
| Distribution field | A type picker and the fields that type needs (spec 1 distribution list) |
| Parameter link | A toggle "Use parameter" beside a number or quantity field. Next to it, a "Try a change" button creates the parameter and a scenario in one step (`canvas-interactions.md`, "Trying a change") |
| Tabs, lists, tables | Row height 32 px; selected row `surface-alt` with a 3 px `accent` marker at the left |
| Notice (one line) | `surface` with a 4 px stripe in `accent`, `warning` or `error`, an icon, the text, and a close button |
| Chip | Pill, Small text, an icon and a word: "Bottleneck", "Queue avg 4.5 min", "Added", "Changed", "Removed" |
| Confirmation dialog | 8 px radius card on the scrim; title, one sentence saying what will happen, optional "Don't ask me again" tick box, Cancel and the action; focus starts on Cancel |
| Focus ring | 2 px solid `focus`, 2 px offset, on every focusable element |

Every pointer target is at least 24 × 24 px (success criterion 2.5.8); buttons are 34 to 36 px high.

## Block styles

A block draws one model component (spec 1 "Components and ports"). Each category has its own shape, so the category reads without colour (owner review, Step 5).

| Category | Shape | Outline |
| --- | --- | --- |
| Flow (`source`, `sink`, `delay`, `branch`) | Capsule (fully rounded ends) | 1.5 px, category colour mixed with `border-strong` |
| Work (`server`, `queue`, `batch`, `unbatch`, `store`) | Rounded rectangle, 14 px radius | Same |
| Resource (`resource_pool`, `schedule`, `failure`) | Tag: 4 px radius on the left, 16 px on the right, dashed outline | Same, dashed |
| Other (future adapters) | Rounded rectangle | `edge` |

```text
 ( (icon) Arrivals          o)     capsule: flow
 [o (icon) Till            o]      rounded: work
 [ (icon) Baristas         >       tag, dashed: resource
```

- **Size.** About 176 × 64 px at 100% zoom; a `branch` with more than two routes grows by 20 px per extra route.
- **Icon disc.** A 34 px circle at the left, filled with the category colour at 18% and holding the block's duotone icon in the category colour.
- **Title.** The component's `label` when it has one, otherwise its `id` (Body, 700). When a label is shown, the id appears in Mono in the type line.
- **Type line.** The type and one key setting: `server · capacity = tills`, `source · every 2 min`.
- **Resource blocks each look different** (owner review choice 3): `resource_pool` shows a people icon and a count badge ("3 baristas"); `schedule` shows a calendar icon and a small strip of on and off hours; `failure` shows a wrench icon and a striped edge.

### After a run

When the Results of a run are open, the canvas shows that run on the blocks, read from its `summary.json`:

- **Work blocks** show a ring with their utilization ("75%"), filled in proportion. At or above the bottleneck threshold (spec 4) the ring is drawn in `error` and a "Bottleneck" chip with a warning icon sits above the block.
- **Queues and servers** show a chip with the mean wait ("Queue avg 4.5 min").
- **Flow lines** show items moving along them (see "Motion"); with motion off, each line shows a count of items instead.
- A bar at the bottom right names the run shown ("Showing run 2026-11-06-01") with "Pause flow" and "Hide run".

### Block states

| State | Shown by |
| --- | --- |
| Default | Outline as in the category table |
| Hover | Outline 2 px |
| Selected | 2.5 px `accent` outline, 3 px offset |
| Keyboard focus | 2 px `focus` ring, 2 px outside the outline (with selection both show) |
| Error | 2 px `error` outline and a 20 px round badge at the top right with "!" and the number of errors |
| Warning (no errors) | A 20 px triangular badge at the top right with "!" and the number of warnings |
| Learn highlight | 3 px `learn` ring and a tag above the block, "Step 2 of 5" |
| Review: added | Dashed 2 px `success` box around the block and an "Added" chip |
| Review: changed | Dashed 2 px `accent` box and a "Changed" chip; changed fields marked in the side panel with the old value beside the new |
| Review: removed | A ghost outline (dashed `border-strong`, no fill) where the block was, and a "Removed" chip |

Badges and chips sit inside the block's bounding box or just above it so they are never clipped; below 50% zoom the title and type line are hidden and only the shape, icon disc, badges and chips remain.

## Port styles

- **Input ports** on the left edge, **output ports** on the right edge, vertically centred; a `source` has only `out`, a `sink` only `in`, a `branch` one output per route.
- **Circle:** 12 px, `edge` fill with a 2 px `surface` ring. Unconnected ports are hollow.
- **Hit target:** 24 × 24 px around each circle (success criterion 2.5.8).
- **Labels:** a `branch` route port shows its route id in Small text. Other ports are labelled only in their accessible name.
- **While connecting:** ports that can accept the connection get a 2 px `accent` ring.
- **Errors are shown on the block, not the port.**

## Line styles

| Line | Pattern | Colour | Ends | Label |
| --- | --- | --- | --- | --- |
| Flow connection | Solid 2.5 px, right-angled with rounded corners | `edge` | Arrowhead at the input | None |
| `resource_pool` reference (from a server's `pool`) | Long dashes, 1.5 px | `cat-resource` | Small round dot on the target, no arrowhead | Chip with the people icon: "staffs" |
| `schedule` reference (`target`) | Dots, 1.5 px | `cat-resource` | Round dot, no arrowhead | Chip with the calendar icon: "sets hours" |
| `failure` reference (`target`) | Dash-dot, 1.5 px | `cat-resource` | Round dot, no arrowhead | Chip with the wrench icon: "breaks down" |

Hover: 3 px. Selected flow connection: 3 px `accent`. A reference line is not a connection: it cannot be selected or deleted on the canvas, and it changes only when the setting changes in the side panel. The three reference lines differ by pattern, icon and word, so they read in greyscale (owner review choice 3). Giving each its own colour is left for later if needed.

## Motion

- **What moves.** Items flowing along connections while a run's results are shown; short feedback on buttons and panels (100 to 300 ms); a small celebration on a first finished run and a finished lesson. Nothing moves while the user is editing.
- **Setting:** Settings, Appearance, "Motion": Full, Reduced, Off. The default follows the operating system's "reduce motion" preference (Reduced when it is set). Reduced keeps the flow dots but removes celebrations and transitions; Off removes all motion and shows counts on lines instead.
- **Pausing.** Moving items always have a visible "Pause flow" control (success criterion 2.2.2).

## Changes

- 2026-11-06: first version (AKS-118).
- 2026-11-06: version 2 from the owner design review (AKS-118): Sanzo Wada palette with a softened dark theme; chart and colour-blind safe chart tokens; bundled fonts; Phosphor icons; block shapes per category; distinct resource boxes and lines; review marks for outside changes; after-run overlay; motion setting; charts with ECharts; confirmation dialog; disabled-Run pointers; plain words.
