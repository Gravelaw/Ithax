# Spec 3 research: node-editor patterns (M9)

## Question

How do general workflow tools handle large graphs, grouping and errors? (Spec 3, "Research before building", M9 · Node-editor patterns.) The canvas must stay responsive with 200 components (spec 3 "Performance targets").

## Finding

Tools read: Node-RED (a flow editor for event-driven programs), KNIME Analytics Platform (data workflows), and React Flow, the library spec 3 names for the canvas.

### Large graphs

- **Render only what is visible.** React Flow has an `onlyRenderVisibleElements` option that renders only the nodes and edges in view. Its performance guide adds: wrap custom node and edge components in `React.memo`, keep callbacks stable with `useCallback`, do not read the whole `nodes` array inside components (they then re-render on every drag, pan and zoom), keep derived state such as the selected ids in its own store field, collapse large node trees with the `hidden` flag, and drop costly CSS (animations, shadows, gradients) on large graphs.
- **Overview map.** React Flow's `MiniMap` draws every node as an SVG shape and the current viewport as a mask; it can be made pannable and zoomable, and needs an accessible name (`ariaLabel`, default "Mini Map").
- **Zoom range.** React Flow defaults to 0.5 to 2; both limits are props (`minZoom`, `maxZoom`).
- **Find.** Node-RED's search (Ctrl/⌘-F) indexes every property of every node; choosing a result reveals the node. Filters include `is:invalid`, nodes with configuration errors.
- **Selecting along the flow.** Node-RED selects all connected, upstream or downstream nodes (Shift-click on the middle, left or right of a node; `Alt-s c/u/d`).

### Grouping

- **Visual groups.** Node-RED groups are a border and fill drawn around nodes, with an optional label; they move and copy as one object (Ctrl/⌘-Shift-G to group, Ctrl/⌘-Shift-U to ungroup). Nothing about the flow's behaviour changes.
- **Sub-flows.** Node-RED subflows collapse a selection into a single node that is added to the palette and reused; this is only allowed when every wire into the selection reaches one node, because a subflow has at most one input.
- **React Flow** supports both: a child node with `parentId` is positioned relative to its parent and can be held inside it with `extent: 'parent'`; a `group` node type has no handles.

### Errors

- **On the node.** Node-RED draws a red triangle on a node with configuration errors; hovering shows the details. KNIME draws a traffic light under each node; a new node shows red, "not configured", and the light turns yellow, "configured", once its settings are complete.
- **In a list.** Node-RED's `is:invalid` search lists the faulty nodes.
- **Hover-only details are a problem for keyboard users** (WCAG 2.2 success criterion 1.4.13, content on hover or focus), so details must also be reachable from a list or by focus.

### Keyboard and pointer alternatives

- **React Flow** makes nodes and edges focusable by default: Tab moves through them, Enter or Space selects, Escape clears the selection, arrow keys move the selected node (Shift for larger steps), and an `aria-live` region announces moves. `ariaLabelConfig` localises the built-in texts.
- **Node-RED** wires without dragging: hold Ctrl/⌘ and click a port, then click the destination. Its Quick-Add dialog (Ctrl/⌘-click on the workspace) adds a node where the pointer is, with a filter box.
- **Node-RED** deletes a node and keeps the flow joined with Ctrl/⌘-Delete, and inserts a dropped node into a wire it is dropped on.

## Sources

Read on 2026-11-06.

- Node-RED, "Groups": https://nodered.org/docs/user-guide/editor/workspace/groups
- Node-RED, "Subflows": https://nodered.org/docs/user-guide/editor/workspace/subflows
- Node-RED, "Nodes": https://nodered.org/docs/user-guide/editor/workspace/nodes
- Node-RED, "Wires": https://nodered.org/docs/user-guide/editor/workspace/wires
- Node-RED, "Selection": https://nodered.org/docs/user-guide/editor/workspace/selection
- Node-RED, "Searching flows": https://nodered.org/docs/user-guide/editor/workspace/search
- KNIME Analytics Platform User Guide (nodes, status traffic light): https://docs.knime.com/latest/analytics_platform_user_guide/index.html
- React Flow, "Performance": https://reactflow.dev/learn/advanced-use/performance
- React Flow, "The ReactFlow component" (API reference, viewport props): https://reactflow.dev/api-reference/react-flow
- React Flow, "The MiniMap component": https://reactflow.dev/api-reference/components/minimap
- React Flow, "Sub Flows": https://reactflow.dev/learn/layouting/sub-flows
- React Flow, "Accessibility": https://reactflow.dev/learn/advanced-use/accessibility
- WCAG 2.2: https://www.w3.org/TR/WCAG22/

## Decision

Recorded in `docs/design/canvas-interactions.md`:

1. **Large graphs:** `onlyRenderVisibleElements` on; memoised block components; selection kept in its own store field; no shadows or animations on blocks or connections; a minimap; zoom from 0.2 to 2 so that 200 blocks fit on one screen at the smallest zoom; "Fit view"; and "Find block" (Ctrl+F) over ids, labels and types. Whether these meet the 100 ms target is measured at M9 (spec 3 "Performance targets").
2. **Grouping: none in Phase 1.** The model format has no group or sub-model concept (spec 1), and the canvas shows the model file and nothing else (spec 3 "Single source"). A visual-only group could live under `ui`, but no template needs it: the template with the most block types, the warehouse, uses seven (spec 4 "Template library"). This is the simplest reading. It is logged in `docs/DECISIONS.md` for the owner to revisit after the M10 templates.
3. **Errors:** a marker on the block with a shape and a count, never colour alone (WCAG 1.4.1); the full text in the problems list and in the side panel when the block is selected. Hover tooltips repeat the text but are never the only place it appears.
4. **Pointer and keyboard alternatives:** click a port and then click a target, as an alternative to dragging (WCAG 2.5.7); a "Connect" dialog for keyboard users; React Flow's built-in keyboard support kept on (`nodesFocusable`, `edgesFocusable`).
5. **Not adopted:** dropping a block onto a connection to insert it, and delete-and-reconnect. Both are a batch of several edits that a beginner may not expect. They can be added later without changing the model format.

## Tested

Not tested: no interface code exists. The 200-component responsiveness target is measured at M9 by the end-to-end test that spec 3 describes.
