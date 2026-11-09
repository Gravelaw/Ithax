# Accessibility

A check of the design against the Web Content Accessibility Guidelines (WCAG) 2.2, Level AA, covering keyboard use, contrast, text size and focus order. This serves spec 3 "Design before building" (fifth item). The interface is web content inside a desktop webview (spec 3 "Architecture"), so WCAG applies directly.

The target is **WCAG 2.2 Level AA** for every screen. It is a design target, not a test result: the M9 interface is checked against this list when it exists.

## Success criteria applied

Numbers and titles are from the WCAG 2.2 Recommendation (https://www.w3.org/TR/WCAG22/, read 2026-11-06).

| Criterion | Level | How the design meets it | Where |
| --- | --- | --- | --- |
| 1.3.1 Info and Relationships | A | Panels are landmarks with names ("Palette", "Canvas", "Block settings", "Problems"); form fields have labels; tables have header cells | All screens |
| 1.4.1 Use of Color | A | Errors and warnings differ by badge shape and word, not only colour; block categories differ by shape (capsule, rounded box, tag) as well as icon and type word; the three resource reference lines differ by pattern, icon and word; review marks carry "Added", "Changed", "Removed"; chart series carry marker shapes and direct labels, and a colour-blind safe chart palette is a setting | `design-system.md` |
| 1.4.3 Contrast (Minimum) | AA | Every text pair is at least 4.5:1 in both themes; lowest 4.60:1 | "Contrast" below |
| 1.4.4 Resize Text | AA | Text-size setting from 100% to 200%; all sizes in `rem` | "Text size" below |
| 1.4.10 Reflow | AA | Panels collapse below 1024 px; the side panel becomes an overlay. The canvas is a diagram, which falls under the criterion's exception for content that needs a two-dimensional layout; its text alternative (the blocks table, "Screen readers" below) reflows | `design-system.md` "Spacing and layout" |
| 1.4.11 Non-text Contrast | AA | Outlines, ports, connections, reference lines, focus rings, markers, category colours and chart series are at least 3:1 against what is next to them; lowest 3.44:1 | "Contrast" below |
| 1.4.12 Text Spacing | AA | No fixed-height text boxes; text wraps | All screens |
| 1.4.13 Content on Hover or Focus | AA | Tooltips appear on hover and on keyboard focus, stay while the pointer is over them, close with Escape, and never hold the only copy of information (issue text is also in the problems list and side panel) | `canvas-interactions.md` |
| 2.1.1 Keyboard | A | Every canvas action has a keyboard path ("Keyboard map" below); the pointer-only paths have keyboard equivalents | "Keyboard map" |
| 2.1.2 No Keyboard Trap | A | Tab and Shift+Tab always leave the canvas; Escape closes dialogs and leaves "placing" and "connecting" states | "Focus order" |
| 2.1.4 Character Key Shortcuts | A | Single-key shortcuts (C, F2, Delete, arrows) act only while the canvas has focus, which the criterion allows | "Keyboard map" |
| 2.2.2 Pause, Stop, Hide | A | The Run monitor's live numbers would update at most once per second, with a "Pause updates" button; no Phase 1 engine reports numbers while it runs, so the monitor shows only its progress bar and the service's message and has no "Pause updates" (AKS-138, logged fallback); items moving along connections after a run have a "Pause flow" button, and the Motion setting can turn all motion off; nothing blinks | `wireframes/05-run-monitor.svg`, `design-system.md` "Motion" |
| 2.4.3 Focus Order | A | A fixed order, described in "Focus order" | "Focus order" |
| 2.4.7 Focus Visible | AA | A 2 px `focus` ring with 2 px offset on every focusable element, including blocks, ports and connections | `design-system.md` |
| 2.4.11 Focus Not Obscured (Minimum) | AA | Focusing a block off-screen pans the canvas to show it (React Flow `autoPanOnNodeFocus`, on by default); notices and the problems list never cover the focused block | `canvas-interactions.md` |
| 2.5.7 Dragging Movements | AA | Every drag has a single-pointer alternative: click-then-click to add and to connect, the side panel's pickers to connect, arrow keys or position fields to move, zoom buttons and minimap clicks to navigate | "Pointer alternatives" |
| 2.5.8 Target Size (Minimum) | AA | Pointer targets are at least 24 × 24 px; ports have a 24 × 24 px hit area around a 12 px circle | `design-system.md` "Port styles" |
| 3.3.1 Error Identification | A | Each issue names the component and is described in text (spec 1 issue object `message`) | `canvas-interactions.md` "Validation and error display" |
| 3.3.3 Error Suggestion | AA | The issue's `hint` is shown with the message | Same |
| 4.1.2 Name, Role, Value | A | Blocks, ports and connections have accessible names ("Block till, server, 1 error"; "Output port out of till, connected to exit.in"); toggles and pickers expose their state | "Screen readers" |
| 4.1.3 Status Messages | AA | Save state, validation counts, notices and run progress are announced in polite live regions without taking focus | `canvas-interactions.md` |

Level AAA criterion 2.3.3 (animation from interactions) is followed: Settings, Appearance, "Motion" (Full, Reduced, Off) defaults to the operating system's reduce-motion preference, and Off removes every animation (`design-system.md` "Motion").

## Keyboard map

Canvas shortcuts work only while the canvas has focus (WCAG 2.1.4). Every action listed in `canvas-interactions.md` appears here, so the canvas can be used without a pointer.

| Action | Keys | Spec 3 rule served |
| --- | --- | --- |
| Move focus to the next or previous block or connection | Tab, Shift+Tab | |
| Select the focused item | Enter or Space | |
| Add or remove the focused item from the selection | Ctrl+Space | |
| Select all | Ctrl+A | |
| Clear selection | Escape | |
| Find a block by id, label or type | Ctrl+F, type, Enter | |
| Add a block | Focus the palette (F6 to reach it), arrow to a block type, Enter | Add |
| Connect | Select a block, press C, choose output port, choose input port, Enter | Connect |
| Connect (alternative) | In the side panel, the output port's picker | Connect |
| Disconnect | Select the connection, Delete; or the picker's "Not connected" | Connect |
| Move the selection | Arrow keys (8 px), Shift+arrow (40 px) | |
| Delete the selection | Delete or Backspace; in the confirmation dialog, focus starts on Cancel, Tab to Delete and Enter, Escape cancels | Delete |
| Review an outside change | F6 to the side panel's "Changes to review" list, arrow to a change, Accept or Reject buttons | External edits |
| Try a change | Tab to "Try a change" beside a field, Enter, type the value and a name, Enter | |
| Rename | F2, type, Enter (Escape cancels) | Rename |
| Edit settings | F6 to the side panel, Tab through fields | |
| Undo, redo | Ctrl+Z; Ctrl+Shift+Z or Ctrl+Y | Undo and redo |
| Zoom in, out, fit, 100% | Ctrl+=, Ctrl+−, Ctrl+0, Ctrl+1 | |
| Pan (nothing selected) | Arrow keys | |
| Open the context menu | Shift+F10 or the Menu key | |
| Go to the problems list | F6 to it, or activate the "N errors" link beside Run | Validate, Run |
| Select a block from the problems list | Arrow to the entry, Enter | Validate |
| Run | Ctrl+Enter, or Tab to the Run button | Run |
| Learn mode: next and previous step | Focus the step card; Next and Back buttons | |
| Switch screens | F6 to the navigation rail, arrow keys, Enter | |

There is no keyboard path for drawing a box selection; Ctrl+Space and Ctrl+A cover multiple selection.

## Pointer alternatives

WCAG 2.5.7 asks that anything done by dragging can also be done with single pointer actions.

| Dragging action | Single-pointer alternative |
| --- | --- |
| Drag a block from the palette | Click the block type, then click the canvas |
| Drag from an output port to an input port | Click the output port, then click the input port; or the side panel's picker |
| Drag a block to move it | The side panel's "Position" fields (x, y); or the context menu's "Move to…" which then takes one click on the canvas |
| Drag the canvas to pan | Click in the minimap; zoom buttons and "Fit" |
| Shift+drag to box-select | Ctrl+click each block |
| Resize the problems list | "Collapse" and "Expand" buttons |

## Focus order

Within the window, F6 and Shift+F6 cycle through the regions; Tab moves within a region. The order is the reading order of the layout (`design-system.md`, "Spacing and layout"):

1. Navigation rail (arrow keys between screens; Enter opens one)
2. Top bar: project name, save state, Undo, Redo, experiment picker, Run, the reason link
3. Palette (Canvas screen): filter box, then block types by group
4. Canvas: blocks in model order (the order of `components`), then connections in model order. Model order, not position, so the order is stable while blocks move
5. Side panel: the selection's issues, then its fields from top to bottom
6. Problems list
7. Notices, when present (also announced, so the user need not go there)

Rules:

- **Opening a dialog** (first-start notice, Connect, Find block, Stop run) moves focus to its first control; closing returns focus to where it was. The delete confirmation and "Restore all defaults" dialogs put focus on Cancel, so Enter pressed by accident changes nothing.
- **After adding a block**, focus moves to the new block; after deleting, to the next block in model order, or the canvas if none.
- **After selecting a problem entry**, focus stays in the list so the user can go through the problems; the side panel and the canvas follow the selection.
- **After an external reload**, focus stays on the same block id if it still exists.

## Contrast

All colour pairs, with their computed ratios in both themes, are in `design-system.md` "Contrast", generated by `scripts/contrast.py` from `docs/design/tokens.json`; `tests/test_design.py` fails if any pair falls below its threshold or the table goes stale.

Summary of the computation after the owner design review of 2026-11-06 (Sanzo Wada palette, softened dark theme, chart tokens; 37 pairs per theme, 74 in all):

| Theme | Text pairs (need 4.5:1) | Lowest text pair | Non-text pairs (need 3:1) | Lowest non-text pair |
| --- | --- | --- | --- | --- |
| Light | 15 of 15 pass | 4.60:1, `text-muted` on `surface-alt` | 22 of 22 pass | 3.44:1, `cat-resource` on `canvas` |
| Dark | 15 of 15 pass | 4.86:1, `learn` on `surface` | 22 of 22 pass | 4.02:1, `border-strong` on `surface` |

Contrast while dimmed: no block or text is ever dimmed by opacity. Learn mode highlights one block with a ring instead of fading the others.

## Text size

- **Smallest text is 12 px** (block type line, port labels, results footer) at 100%. Body text is 14 px.
- **Text-size setting:** 100%, 125%, 150%, 175%, 200% (Settings, "Appearance"). It scales the root font size; blocks grow with their text, so nothing is clipped. At 200% the canvas fits fewer blocks per screen; zoom compensates.
- **The canvas zoom is separate from text size.** Zoom changes the drawing; text size changes the interface. Both apply to block text.
- **Results PDF** uses 10 pt minimum for the footer and 11 pt for body text.

## Screen readers

- **Blocks** are focusable elements with role `group` and a name built from the model: "till, server, capacity 1, 1 error". Their ports are buttons inside: "Output port out of till, connected to exit.in".
- **Connections** are focusable: "Connection from arrivals.out to till.in".
- **React Flow's accessibility layer** is kept on (`nodesFocusable`, `edgesFocusable`) and its messages are worded through `ariaLabelConfig` (`docs/research/spec-3-node-editor-patterns.md`).
- **A text alternative to the whole canvas** is the side panel with nothing selected, which lists every block with its connections as a table; each row's "Select" button selects the block. A screen-reader user can build and check a model from the palette, the Connect dialog, the side panel and this table without seeing the drawing.
- **Charts** on every screen each have a data table beside them with the same numbers.
- **Review marks** are announced: "Till, server, changed by an assistant: capacity 1 to 2. Accept or reject."

## Colour blindness

Settings, Appearance, "Colour-blind safe charts" (owner review) switches chart series to `chart-cb-1` to `chart-cb-4`, hues from Okabe and Ito chosen to stay distinct for red-green and blue-yellow colour blindness, each still at least 3:1 against `surface`. Elsewhere nothing relies on colour alone (criterion 1.4.1 above), so the canvas needs no separate mode.

## Not yet checked

- The design has not been tested with a screen reader or by a keyboard-only user; that happens on the M9 interface.
- Whether WebKitGTK (Linux) and WebView2 (Windows) expose React Flow's ARIA roles equally to the platform screen readers is unknown until the interface exists (`docs/research/spec-3-framework-check.md`).
