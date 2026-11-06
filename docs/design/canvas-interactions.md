# Canvas interactions

The interaction rules for the Canvas screen: adding, connecting, selecting, moving, deleting, undo and redo, zoom and pan, saving, validation and error display, running, renaming and external edits. They implement every rule in spec 3 "Canvas behaviour" and serve spec 3 "Design before building" (third item). Styles are in `design-system.md`; keyboard and screen-reader details are collected in `accessibility.md`; the layout is in `wireframes/01-canvas.svg`.

Every product detail traces to a spec. Where the specs were silent, the simplest reading was taken; those choices are marked **(design choice)** and listed in `docs/DECISIONS.md` (2026-11-06) for the owner to confirm.

## Spec 3 rules and where they are met

| Spec 3 "Canvas behaviour" rule | Met in |
| --- | --- |
| **Single source.** The canvas shows the model file and nothing else. Every canvas action is one or more model edits. | "The model and the canvas"; the edit column of every table below |
| **Add.** Dragging a block from the palette adds a component with a generated id, such as `server_2`, and default settings. | "Adding a block" |
| **Connect.** Dragging from an output port to an input port sends `connect`. Dragging from an output port that is already connected replaces its connection. | "Connecting" |
| **Delete.** Removes the selection and its connections. | "Deleting" |
| **Undo and redo.** At least 100 steps, covering every model edit. | "Undo and redo" |
| **Save.** Automatic after every edit. There is no save button. | "Saving" |
| **Validate.** Runs half a second after the last edit. Issues appear as a marker on the block and in a list; selecting a list entry selects the block. | "Validation and error display" |
| **Run.** Disabled while errors exist, with the reason shown. | "Running" |
| **Rename.** Changing a component's id updates its connections and any references to its metrics. | "Renaming" |
| **External edits.** The canvas sends `base_revision` on every write and, on a `model` event whose revision it did not produce, reloads the model and shows a one-line notice naming the client. | "External edits" |

## The model and the canvas

- **What is drawn.** One block per entry in `components`, one line per entry in `connections`, and one dashed reference line per `pool` or `target` setting (spec 1, spec 2 "Block reference"). Nothing else is stored or shown: no free text, no groups, no shapes. A block's position is its component's `ui` object (spec 1: "The `ui` object holds canvas position and is never read by an engine"), written as `{"x": <number>, "y": <number>}` in canvas pixels at 100% zoom **(design choice: the keys inside `ui`)**.
- **How it changes.** Every action below sends one request to `POST /v1/projects/{pid}/model/edits` with a batch of edits and `base_revision`, except undo and redo, which use `PUT /v1/projects/{pid}/model` (see "Undo and redo"). A batch is one user action: one save, one undo step.
- **The response is the truth.** After every write the canvas redraws from the model in the response, not from its own guess. If the response is 400 (E180, the edit could not be applied), nothing changed: the canvas keeps the model it had and shows the issue's message as a one-line notice.
- **Where the model comes from.** On opening a project the canvas reads `GET /v1/projects/{pid}/model` and subscribes to `GET /v1/projects/{pid}/events`.
- **Optimization models.** A model with `"domain": "optimization"` has no components (spec 1). Its Canvas screen shows a form instead of the graph: a table of variables (id, type, lower, upper), the objective (sense and one coefficient per variable), and a table of constraints (id, one coefficient per variable, operator, right-hand side). Each change is a `set_path` edit on `/variables`, `/objective` or `/constraints`. Undo, redo, saving, validation and Run work as on the graph **(design choice; spec 3 "Screens" item 2 updated)**. Spec 3 listed `set_path` for `meta`, `run`, `objectives`, `constraints` and `search` only, so an optimization model's `variables` and `objective` could not be edited at all; `variables` and `objective` were added to `set_path` and `remove_path` (2026-11-06, logged in `docs/DECISIONS.md`).

## Adding a block

| Action | Pointer | Keyboard | Edit sent |
| --- | --- | --- | --- |
| Add by dragging | Drag a block type from the palette and drop it on the canvas | | `add_component` with the generated id, the type, default `params` and `ui` at the drop point |
| Add without dragging | Click a block type in the palette (it shows as "placing"), then click the canvas where it should go; Escape cancels | | Same |
| Add with the keyboard | | Focus a block type in the palette and press Enter | Same, with `ui` at the centre of the visible canvas, moved down by 24 px until it overlaps no block |

- **Generated id.** `<type>_<n>`, with `n` the smallest positive integer that makes the id unique among components: the first server is `server_1`, the next `server_2` (spec 3 example). This matches JaamSim's numbering (`spec-3-interface-study.md`). The id fits spec 1's identifier pattern because block type names do.
- **Default settings.** The defaults that `GET /v1/schema/components/{type}` declares. A required setting with no default is left out, so the new block shows an E122 error until it is filled in. This is correct behaviour, not a fault: the error tells the user what to fill in. The side panel opens on the new block with that field focused.
- **After adding,** the new block is selected and has keyboard focus.
- **Palette contents** come from `GET /v1/schema`: only block types the installed adapters provide are listed, in the three groups of `design-system.md` (flow, work, resource). A filter box at the top of the palette narrows the list by name.

## Connecting

| Action | Pointer | Keyboard | Edit sent |
| --- | --- | --- | --- |
| Connect by dragging | Press on an output port, drag to an input port, release | | `connect` with `from` `<id>.<port>` and `to` `<id>.<port>` |
| Connect without dragging | Click an output port, then click an input port; Escape or a click on empty canvas cancels | | Same |
| Connect with the keyboard | | Select a block and press C: the "Connect" dialog lists the block's output ports and, for the chosen port, every input port in the model by block id; Enter connects | Same |
| Connect from the side panel | In the side panel's "Connections" section, each output port has a picker listing every input port | Same picker, by keyboard | Same |
| Replace a connection | Any of the above from an output port that is already connected | Same | `connect`; the service replaces the old connection (spec 3 "Model edits") |
| Disconnect | Select a connection and press Delete, or set the port's picker to "Not connected" | Same | `disconnect` with `from` |

- **Valid targets.** While connecting, the input ports of every other block get an `accent` ring. Dropping on anything else (empty canvas, an output port, a block's body) cancels and sends nothing. A connection from a block to its own input is allowed if the model allows it; the canvas does not judge the model, validation does.
- **Replacing is visible.** An already-connected output port shows its current target in its tooltip and in the side panel. When a connection replaces another, a one-line notice says so: "`arrivals.out` now goes to `queue_1.in` (was `till.in`)." It disappears after 8 seconds or on the next action, and Undo restores the old connection.
- **Routes of a branch.** Each route is its own output port, named after the route (spec 1). Adding a route in the side panel (`set_setting` on `/routes`) adds the port.
- **Reference lines** (a server's `pool`, a schedule's or failure's `target`) are not connections. They are set in the side panel with a picker of matching blocks (`set_setting`), and drawn as dashed lines **(design choice; spec 3 "Canvas behaviour" updated with a "References" rule)**.

## Selecting

| Action | Pointer | Keyboard |
| --- | --- | --- |
| Select one block or connection | Click it | Tab to it; Enter or Space selects |
| Add or remove from the selection | Ctrl+click | Ctrl+Space on the focused item |
| Select several by area | Shift+drag on empty canvas draws a box; blocks inside are selected | |
| Select all | | Ctrl+A |
| Clear selection | Click empty canvas | Escape |
| Find and select a block | | Ctrl+F opens "Find block": type part of an id, label or type; Enter selects the block and centres the view on it |

- **Side panel follows the selection.** One block: its issues, id, label, position (x, y), settings form and connections. One connection: its `from` and `to`, with a "Disconnect" button. Several items: their count and a "Delete" button. Nothing: the model's parameters, with "Add parameter" (`set_parameter`), and below them a table of every block with its type, connections and issue count, each row with a "Select" button. The table is the text alternative to the drawing (`accessibility.md`, "Screen readers").
- **Selection is not a model edit** and is not saved. It is not undone by Undo.

## Moving

| Action | Pointer | Keyboard | Edit sent |
| --- | --- | --- | --- |
| Move blocks | Drag a selected block; all selected blocks move together | Arrow keys move the selection by 8 px; Shift+arrow by 40 px | One `set_ui` per moved block, in one batch, when the drag ends, or 500 ms after the last arrow key |
| Move without dragging | Context menu "Move to…", then one click on the canvas; or type x and y in the side panel's "Position" fields | The "Position" fields | `set_ui` |
| Snap | Blocks snap to an 8 px grid | Same | |

- **One step per move.** A drag, or a run of arrow presses without a 500 ms pause, is one batch and one undo step **(design choice)**.

## Deleting

| Action | Pointer | Keyboard | Edit sent |
| --- | --- | --- | --- |
| Delete the selection | Right-click > Delete, or the side panel's Delete button | Delete or Backspace | One batch: `remove_component` for each selected block (its connections go with it, spec 3 "Model edits"), and `disconnect` for each selected connection whose block is not also being removed |

- **No confirmation dialog.** Undo restores everything the delete removed, and the one-line notice says what went: "Deleted `till` and 2 connections. Undo (Ctrl+Z)."
- **References are not repaired.** Deleting a `resource_pool` that a server names in `pool` leaves the reference, and validation shows E124 on the server. The canvas does not change other blocks' settings behind the user's back.

## Undo and redo

- **Depth.** At least 100 steps (spec 3); the interface keeps 200 **(design choice)**. Each step is one batch: one add, connect, delete, move, rename, settings change, parameter or experiment change, from any screen of the project. Undo covers every model write the interface makes, so it covers every model edit (spec 3).
- **Keys.** Undo: Ctrl+Z. Redo: Ctrl+Shift+Z or Ctrl+Y. Buttons in the top bar do the same, with the name of the step in their tooltip and accessible name: "Undo: delete `till`".
- **How it works (design choice; spec 3 "Canvas behaviour" updated).** Before each write the interface keeps the model as it was, with its revision. Undo sends that earlier model with `PUT /v1/projects/{pid}/model` and `base_revision` set to the current revision; redo sends the later one the same way. A whole-model write was chosen over inverse edits because some edits have no inverse in the edit list: `set_setting` that creates a new optional key (for example `queue_capacity`) cannot be taken back with an edit, since there is no edit that removes a component setting. A whole-model write restores exactly what was there, including `ui`. The cost is memory: 200 copies of a 200-component model, a few megabytes, held only while the project is open.
- **A new action clears the redo steps,** as in every editor.
- **Undo is a write like any other.** It increments the revision, saves automatically, triggers validation, and shows on other clients as a `model` event from `ui`.
- **The history is per open project and per window.** It is not saved; it is cleared on closing the project.
- **External edits clear the history** (see "External edits"), because an earlier model would silently undo the other client's change.

## Zoom and pan

| Action | Pointer | Keyboard |
| --- | --- | --- |
| Zoom in or out | Mouse wheel or touchpad pinch, centred on the pointer; or the + and − buttons | Ctrl+= and Ctrl+− |
| Zoom to fit | "Fit" button | Ctrl+0 |
| Zoom to 100% | Click the zoom percentage | Ctrl+1 |
| Pan | Drag on empty canvas; or Space+drag anywhere; or drag in the minimap | Arrow keys when nothing is selected (40 px per press) |
| Overview | Minimap at the bottom right: click or drag to move the view | |

- **Range:** 20% to 200% **(design choice; React Flow's default is 50% to 200%, too narrow to fit 200 blocks on one screen; `spec-3-node-editor-patterns.md`)**.
- **On opening** a project the view fits the whole model. Zoom and pan are not saved in the model and are not undoable.
- **Below 50%** blocks show only their stripe, icon and badges (`design-system.md`), so markers stay visible.

## Saving

- **Automatic after every edit; no save button** (spec 3). There is no unsaved state: a change exists only once the service has written it.
- **Save state in the top bar,** as text with an icon: "Saved" (with the revision in the tooltip), "Saving…" while a write is in flight, "Not saved: the service is not answering. Retrying." if a write fails for a network reason. While not saved, the canvas is read-only and the pending batch is retried every 2 seconds **(design choice)**; nothing else is queued, so the user cannot pile up changes the service never saw.
- **Writes are sent one at a time,** in order. A new action waits until the previous write has answered.

## Validation and error display

- **When.** 500 ms after the last edit (spec 3), the canvas calls `POST /v1/projects/{pid}/validate`. Each new edit restarts the 500 ms timer. A validation that was sent before a later edit is ignored when it returns; the later one replaces it. Validation also runs on opening the project.
- **Markers on blocks.** An issue whose `component` names a block puts a badge on that block: a round "!" badge in `error` for errors, a triangular "!" badge in `warning` for warnings, each with a count (`design-system.md`). Errors also outline the block in `error`. Shapes differ as well as colours (WCAG 2.2 success criterion 1.4.1).
- **The problems list** sits under the canvas: one row per issue, errors first, then warnings, each in model order. A row shows the severity icon and word, the code, the component id, the `message` and the `hint` (spec 1 issue object). The header shows the counts: "2 errors, 1 warning".
- **Selecting a list entry selects the block** (spec 3) and centres the view on it, and the side panel opens with the field named by the issue's `path` focused when the path points inside `params`. Entries without a component (for example E170 on an experiment, or E150 on a parameter) open the screen that edits that part: the Experiment screen for `/experiments/...`, the side panel's parameter list for `/parameters/...`.
- **From a block to its issues.** The selected block's issues are also listed at the top of its side panel, so they can be read without the list. Hovering a badge shows the messages as a tooltip, which also appears on keyboard focus (success criterion 1.4.13).
- **Field errors.** When an issue's `path` points at a setting, that field in the side panel shows the message under it in `error`, with an icon (success criterion 3.3.1), and the hint as the suggestion (success criterion 3.3.3).
- **Announcements.** When the counts change, a polite live region announces them: "2 errors, 1 warning." (success criterion 4.1.3).
- **W201 (unstable server) is shown before any run,** as a warning on the server. Findings repeat it after the run (spec 4 `unstable`).

## Running

- **The Run button** is in the top bar, beside the experiment picker (the model's experiments by id; default `base` or the first). Ctrl+Enter does the same from anywhere in the project. It sends `POST /v1/projects/{pid}/runs` with `experiment_id`, then opens the Run monitor. For an optimization model there is no experiment picker and no `experiment_id` (spec 3).
- **Disabled while errors exist, with the reason shown** (spec 3). Beside the disabled button a visible text says why: "2 errors. Fix them to run." The text is a link that focuses the problems list. The reason is never only in a tooltip, because a disabled button cannot take keyboard focus.
- **Also disabled,** with its reason, while a write is unsaved ("Saving…") or while validation is pending ("Checking…"), so a run never starts on a model the user has not seen validated.
- **Warnings do not disable Run** (spec 1: "Errors block a run. Warnings do not").
- **If the service refuses the run** with 422 (errors appeared since the last validation) or E172 (target unavailable), the issues go into the problems list and a one-line notice says the run did not start.

## Renaming

- **Where.** The side panel's "Id" field, or F2 on a selected block, which edits the id in place on the block. Enter accepts; Escape cancels; leaving the field accepts.
- **Edit sent.** `rename_component` with `id` and `new_id`. The service rewrites connections, `schedule` and `failure` targets, `pool` references, objectives and constraints (spec 3 "Model edits"), so references to the component's metrics (`till.wait.mean` becomes `counter.wait.mean`) follow. That is how the spec 3 rule "updates its connections and any references to its metrics" is met: by the service, in one edit, so the assistant and the interface behave the same.
- **A duplicate id** is rejected by the service (E180, 400): the field shows the message under it and keeps the typed text; nothing changes.
- **An id that does not match the identifier pattern** is applied, and validation shows E111 on the block, as for any other edit (spec 3: a batch that applies is saved even if validation then reports errors). The field's hint states the pattern before the user types.
- **Label.** The optional `label` (spec 1) is edited in its own field under the id. It is free text, shown as the block title (`design-system.md`); ids stay what findings and metrics use. Edit sent: `set_label` with `id` and `label`; an empty field sends `label` `null`, which removes it.

> **Spec gap found and closed.** Spec 1 gives each component an optional `label` outside `params`, but spec 3's edit list had no edit that sets it: `add_component` takes `id`, `type`, `params` and `ui`; `set_setting` works inside `params`; `set_path` is limited to named top-level keys; `set_ui` only sets `ui`. Spec 3 "Model edits" now has a `set_label` edit (2026-11-06, logged in `docs/DECISIONS.md`).

## External edits

- **Every write carries `base_revision`** (spec 3), the revision of the model the canvas is showing.
- **Knowing its own writes.** The canvas records the revision returned by each of its writes. A `model` event on `GET /v1/projects/{pid}/events` whose revision is one of them is ignored. An event that arrives while one of the canvas's own writes is still waiting for its answer is held until that answer arrives, so the canvas does not mistake its own write for someone else's.
- **On a `model` event it did not produce,** the canvas reloads the model (`GET .../model`), keeps the selection where the selected ids still exist, clears the undo and redo history (see "Undo and redo"), and shows a one-line notice naming the client from the event's `client` field (spec 3 "Client header"): "The model was changed by an assistant (mcp). The canvas has been reloaded; undo history was cleared." For `script`: "by a script"; for `ui`: "in another window"; with no client: "by another program".
- **On 409 E181** (the canvas's own write raced another client's), nothing was applied. The canvas reloads as above, and the notice says: "Your last change was not saved because the model had just been changed by an assistant (mcp). Please make it again." The change is not replayed automatically, because it may no longer make sense.
- **Notices are one line,** stay until dismissed or replaced, and are announced in a polite live region.

## Context menu

Right-click on a block, a connection or the canvas opens a menu with the same commands as the keys above, each showing its shortcut: Rename (F2), Connect (C), Move to…, Delete (Del), Select all (Ctrl+A), Find block (Ctrl+F), Fit view (Ctrl+0), Undo, Redo. Shift+F10 or the Menu key opens it for the focused item. The menu adds no command that is not available elsewhere.

## Learn mode on the canvas

Learn mode uses this same canvas and model file (spec 4 "Learn and Build modes").

- **Step card.** A card above the side panel shows the lesson step: "Step 2 of 5", the step text (up to 80 words, spec 4 "Template package"), and Back and Next buttons.
- **Highlight.** Each step names one component (spec 4). That block gets the `learn` ring and a "Step 2 of 5" tag, is selected, and the view centres on it. Other blocks are not dimmed, so their text keeps full contrast.
- **The canvas stays editable** during a lesson; edits are ordinary edits. If the user deletes or renames the highlighted block, the step card says "This step's block is no longer in the model" and Next still works.
- **The exercise step** names the change to make and offers the predictions as a single-choice list; after the user picks one, the step card enables "Run". When the run is done, the Results screen opens with the step's explanation shown above the findings (spec 4).

## Out of scope for Phase 1

Grouping, sub-models, copy and paste, comments on the canvas, alignment tools, inserting a block into an existing connection, and delete-and-reconnect. None is required by spec 3, and none has a place in the model file. See `docs/research/spec-3-node-editor-patterns.md`.
