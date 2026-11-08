/**
 * The Canvas screen for a `process` model (spec 3 "Screens" 2 and "Canvas behaviour";
 * `docs/design/canvas-interactions.md`; `docs/design/wireframes/01-canvas.svg`).
 *
 * The canvas draws the model the service last returned and nothing else: one block per
 * component, one line per connection, one reference line per `pool` or `target`. Every
 * action is one batch of model edits (`CanvasSession`), one undo step: add (drag from the
 * palette, click then click, or Enter), connect (drag or click port to port, the side
 * panel's pickers, or C), move (drag, arrow keys: one step per burst, or the Position
 * fields), delete (with the confirmation), rename, label and settings in the side panel.
 * Undo and redo write whole models. Validation follows each write by half a second; its
 * issues mark the blocks and fill the problems list. Run waits for a saved, checked model
 * without errors.
 */
import {
  ArrowUUpLeftIcon,
  ArrowUUpRightIcon,
  CheckCircleIcon,
  CornersOutIcon,
  MagnifyingGlassMinusIcon,
  MagnifyingGlassPlusIcon,
  PlayIcon,
  WarningCircleIcon,
  XIcon,
} from "@phosphor-icons/react";
import {
  applyEdgeChanges,
  applyNodeChanges,
  Background,
  BackgroundVariant,
  type Edge,
  type EdgeChange,
  type Connection as FlowConnection,
  MarkerType,
  MiniMap,
  type Node,
  type NodeChange,
  Panel,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  useViewport,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import "./canvas.css";
import {
  type DragEvent,
  type KeyboardEvent as ReactKeyboardEvent,
  type MouseEvent as ReactMouseEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";
import type { ApiClient, ApiResult } from "../api/client";
import type { ComponentType, Edit, Issue, Model, Project, SchemaBody } from "../api/types";
import type { Route } from "../app/router";
import { LOST_CONTACT, ServiceProblem } from "../components/ServiceProblem";
import { useSettings } from "../settings/SettingsContext";
import { type BlockData, BlockNode, type BlockNodeType, blockName } from "./BlockNode";
import { BusyContext } from "./busy";
import { ConnectDialog, DeleteDialog, type DeletePlan } from "./Dialogs";
import {
  BLOCK_HEIGHT,
  BLOCK_WIDTH,
  categoryOf,
  components,
  connections,
  freePlace,
  issueComponent,
  issueCounts,
  nextId,
  type Point,
  portsOf,
  positionOf,
  references,
  snap,
  splitEnd,
} from "./model";
import { BLOCK_MIME, Palette } from "./Palette";
import { ProblemsList } from "./ProblemsList";
import { type EditPlan, editsWrite, modelWrite } from "./plans";
import { ReferenceEdge } from "./ReferenceEdge";
import { type PanelActions, type Selection, SidePanel } from "./SidePanel";
import type { SessionState } from "./session";
import { undoSteps, useSession } from "./useSession";

export const MIN_ZOOM = 0.2;
export const MAX_ZOOM = 2;
export const NOTICE_MS = 8000;
/** Said when a change is tried while a write awaits its answer: it is not made. */
export const WAIT = "Wait until the last change is saved, then make it again.";

const nodeTypes = { block: BlockNode };
const edgeTypes = { reference: ReferenceEdge };

type CanvasProps = {
  client: ApiClient;
  project: Project | null;
  /** The top bar's slot for the save state, undo, redo and Run. */
  toolbar: HTMLElement | null;
  onGo: (route: Route) => void;
};

export function CanvasScreen(props: CanvasProps) {
  if (props.project === null) {
    return (
      <p className="canvas-message" role="status">
        Opening the project…
      </p>
    );
  }
  return (
    <ReactFlowProvider key={props.project.id}>
      <ProjectCanvas {...props} project={props.project} />
    </ReactFlowProvider>
  );
}

function useSchema(client: ApiClient): ApiResult<SchemaBody> | null {
  const [schema, setSchema] = useState<ApiResult<SchemaBody> | null>(null);
  useEffect(() => {
    let live = true;
    void client.getSchema().then((result) => {
      if (live) setSchema(result);
    });
    return () => {
      live = false;
    };
  }, [client]);
  return schema;
}

function ProjectCanvas({ client, project, toolbar, onGo }: CanvasProps & { project: Project }) {
  const { settings } = useSettings();
  const [state, session] = useSession(client, project.id, undoSteps(settings));
  const schema = useSchema(client);

  if (state.status === "unavailable") {
    return (
      <div className="canvas-message">
        <ServiceProblem result={state.loadProblem} />
      </div>
    );
  }
  if (schema !== null && schema.kind !== "ok") {
    return (
      <div className="canvas-message">
        <ServiceProblem result={schema} />
      </div>
    );
  }
  if (state.model === null || schema === null || session === null) {
    return (
      <p className="canvas-message" role="status">
        Loading the model…
      </p>
    );
  }
  if (state.model.domain === "optimization") {
    return (
      <section className="canvas-message" aria-labelledby="screen-heading">
        <h1 id="screen-heading" className="title">
          Canvas
        </h1>
        <p className="muted">
          This project is a plan (decisions and limits). Its Table and Diagram views arrive in a
          later build.
        </p>
      </section>
    );
  }
  return (
    <ProcessCanvas
      client={client}
      project={project}
      toolbar={toolbar}
      onGo={onGo}
      state={state}
      model={state.model}
      session={session}
      types={schema.data["x-component-types"] ?? {}}
    />
  );
}

function isTyping(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return (
    target.isContentEditable ||
    ["INPUT", "SELECT", "TEXTAREA"].includes(target.tagName) ||
    target.closest('[role="dialog"]') !== null
  );
}

function buildNodes(
  model: Model,
  types: Record<string, ComponentType>,
  issues: Issue[],
  previous: BlockNodeType[],
  wanted: string[] | null,
  readOnly: boolean,
  renamed: Readonly<Record<string, string>>,
): BlockNodeType[] {
  // A renamed block keeps its selection and size under its new id.
  const before = new Map(previous.map((node) => [renamed[node.id] ?? node.id, node]));
  const all = components(model);
  const linked = connections(model);
  return all.map((component, index) => {
    const ports = portsOf(component, types[component.type]);
    const own = issues.filter((issue) => issueComponent(issue, model) === component.id);
    const errors = own.filter((issue) => issue.severity === "error").length;
    const connected: Record<string, string[]> = {};
    for (const connection of linked) {
      const from = splitEnd(connection.from);
      const to = splitEnd(connection.to);
      if (from?.[0] === component.id)
        connected[from[1]] = [...(connected[from[1]] ?? []), connection.to];
      if (to?.[0] === component.id)
        connected[to[1]] = [...(connected[to[1]] ?? []), connection.from];
    }
    const data: BlockData = {
      component,
      category: categoryOf(component.type),
      inputs: ports.inputs,
      outputs: ports.outputs,
      connected,
      errors,
      warnings: own.length - errors,
      messages: own.map((issue) => `${issue.code} ${issue.message}`).join("\n"),
    };
    const old = before.get(component.id);
    const node: BlockNodeType = {
      id: component.id,
      type: "block",
      position: old?.dragging ? old.position : positionOf(component, index),
      data,
      ariaLabel: blockName(data),
      selected: wanted !== null ? wanted.includes(component.id) : (old?.selected ?? false),
      draggable: !readOnly,
      deletable: false,
    };
    if (old?.measured) node.measured = old.measured;
    if (old?.dragging) node.dragging = true;
    return node;
  });
}

function buildEdges(
  model: Model,
  types: Record<string, ComponentType>,
  previous: Edge[],
  clear: boolean,
): Edge[] {
  const selected = new Set(previous.filter((edge) => edge.selected).map((edge) => edge.id));
  const all = components(model);
  const byId = new Map(all.map((component) => [component.id, component]));
  const edges: Edge[] = [];
  connections(model).forEach((connection, index) => {
    const from = splitEnd(connection.from);
    const to = splitEnd(connection.to);
    if (!from || !to) return;
    const source = byId.get(from[0]);
    const target = byId.get(to[0]);
    if (!source || !target) return;
    if (!portsOf(source, types[source.type]).outputs.includes(from[1])) return;
    if (!portsOf(target, types[target.type]).inputs.includes(to[1])) return;
    const id = `c${index}:${connection.from}>${connection.to}`;
    edges.push({
      id,
      source: from[0],
      sourceHandle: from[1],
      target: to[0],
      targetHandle: to[1],
      type: "smoothstep",
      markerEnd: { type: MarkerType.ArrowClosed },
      ariaLabel: `Connection from ${connection.from} to ${connection.to}`,
      selected: !clear && selected.has(id),
      deletable: false,
      data: { index },
    });
  });
  for (const reference of references(model)) {
    edges.push({
      id: `r:${reference.kind}:${reference.from}>${reference.to}`,
      source: reference.from,
      sourceHandle: "ref-out",
      target: reference.to,
      targetHandle: "ref-in",
      type: "reference",
      data: { kind: reference.kind },
      selectable: false,
      focusable: false,
      deletable: false,
    });
  }
  return edges;
}

/** Why Run is not available, and which pointer it shows (owner review choice 9). */
export function runBlocked(
  state: SessionState,
): { reason: string; pointer: "errors" | "busy" } | null {
  if (state.failing) {
    return { reason: "Not saved: the service is not answering. Retrying.", pointer: "busy" };
  }
  if (state.saving) return { reason: "Saving…", pointer: "busy" };
  if (state.checking) return { reason: "Checking…", pointer: "busy" };
  const { errors } = issueCounts(state.issues);
  if (errors > 0) {
    return {
      reason: `${errors} error${errors === 1 ? "" : "s"}. Fix ${errors === 1 ? "it" : "them"} to run.`,
      pointer: "errors",
    };
  }
  return null;
}

function SaveState({ state }: { state: SessionState }) {
  if (state.failing) {
    return (
      <span className="save-state save-failing" role="status">
        <WarningCircleIcon aria-hidden="true" size={16} weight="fill" />
        Not saved: the service is not answering. Retrying.
      </span>
    );
  }
  if (state.saving) {
    return (
      <span className="save-state" role="status">
        Saving…
      </span>
    );
  }
  return (
    <span className="save-state save-saved" role="status" title={`Revision ${state.revision}`}>
      <CheckCircleIcon aria-hidden="true" size={16} weight="fill" />
      Saved
    </span>
  );
}

function ZoomControls() {
  const flow = useReactFlow();
  const { zoom } = useViewport();
  return (
    <Panel position="bottom-left" className="zoom-controls">
      <button
        type="button"
        className="icon-button"
        aria-label="Zoom in"
        title="Zoom in (Ctrl+=)"
        onClick={() => void flow.zoomIn()}
      >
        <MagnifyingGlassPlusIcon aria-hidden="true" size={18} />
      </button>
      <button
        type="button"
        className="icon-button"
        aria-label="Zoom out"
        title="Zoom out (Ctrl+−)"
        onClick={() => void flow.zoomOut()}
      >
        <MagnifyingGlassMinusIcon aria-hidden="true" size={18} />
      </button>
      <button
        type="button"
        className="icon-button"
        aria-label="Fit the model in view"
        title="Fit (Ctrl+0)"
        onClick={() => void flow.fitView()}
      >
        <CornersOutIcon aria-hidden="true" size={18} />
      </button>
      <button
        type="button"
        className="zoom-level"
        aria-label={`Zoom ${Math.round(zoom * 100)}%. Set to 100%`}
        title="Zoom to 100% (Ctrl+1)"
        onClick={() => void flow.zoomTo(1)}
      >
        {Math.round(zoom * 100)}%
      </button>
    </Panel>
  );
}

interface ProcessProps {
  client: ApiClient;
  project: Project;
  toolbar: HTMLElement | null;
  onGo: (route: Route) => void;
  state: SessionState;
  model: Model;
  session: NonNullable<ReturnType<typeof useSession>[1]>;
  types: Record<string, ComponentType>;
}

function ProcessCanvas({
  client,
  project,
  toolbar,
  onGo,
  state,
  model,
  session,
  types,
}: ProcessProps) {
  const { settings, save } = useSettings();
  const flow = useReactFlow();
  const readOnly = state.failing;
  // While a write (or a reload) awaits its answer no change is taken: every action is
  // computed from the model shown, which then holds every accepted write.
  const busy = state.busy;
  const locked = readOnly || busy;
  const [nodes, setNodes] = useState<BlockNodeType[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [placing, setPlacing] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<(DeletePlan & { edges: number[] }) | null>(null);
  const [connecting, setConnecting] = useState<string | null>(null);
  const [experiment, setExperiment] = useState<string>("");
  const wanted = useRef<string[] | null>(null);
  const [focusAfter, setFocusAfter] = useState<string | null>(null);
  const shownLocally = useRef<ApiResult<unknown> | null>(null);
  const problems = useRef<HTMLElement>(null);
  const area = useRef<HTMLElement>(null);
  const drawn = useRef(new Set<string>());
  drawn.current = new Set(nodes.map((node) => node.id));

  // The drawing follows the model, the issues and the selection.
  useEffect(() => {
    const want = wanted.current;
    setNodes((previous) =>
      buildNodes(model, types, state.issues, previous, want, readOnly, state.renamed),
    );
    setEdges((previous) => buildEdges(model, types, previous, want !== null));
    if (want?.every((id) => components(model).some((item) => item.id === id))) {
      wanted.current = null;
    }
  }, [model, types, state.issues, readOnly, state.renamed]);

  // A block just added or renamed takes the keyboard focus once it is drawn.
  // React Flow shows a node only once it is measured, so focusing is tried for a few frames.
  useEffect(() => {
    const id = focusAfter;
    if (id === null || !nodes.some((node) => node.id === id)) return;
    let tries = 0;
    let frame = 0;
    const focus = () => {
      const element = area.current?.querySelector<HTMLElement>(
        `.react-flow__node[data-id="${CSS.escape(id)}"]`,
      );
      element?.focus({ preventScroll: true });
      if (element && document.activeElement === element) setFocusAfter(null);
      else if (tries++ < 30) frame = requestAnimationFrame(focus);
      else setFocusAfter(null);
    };
    focus();
    return () => cancelAnimationFrame(frame);
  }, [nodes, focusAfter]);

  // On opening, the view fits the whole model once its blocks are measured.
  const fitted = useRef(components(model).length === 0);
  useEffect(() => {
    if (fitted.current || nodes.length === 0 || nodes.some((node) => !node.measured)) return;
    fitted.current = true;
    const frame = requestAnimationFrame(() => void flow.fitView({ maxZoom: 1, padding: 0.15 }));
    return () => cancelAnimationFrame(frame);
  }, [nodes, flow]);

  // Notices go after 8 seconds (or at the next one).
  useEffect(() => {
    if (notice === null) return;
    const timer = setTimeout(() => setNotice(null), NOTICE_MS);
    return () => clearTimeout(timer);
  }, [notice]);

  const experiments = Array.isArray(model.experiments) ? model.experiments : [];
  const chosenExperiment =
    experiments.find((item) => item.id === experiment)?.id ??
    experiments.find((item) => item.id === "base")?.id ??
    experiments[0]?.id ??
    "";

  const selection: Selection = useMemo(
    () => ({
      // Until the drawing catches up, a block renamed by the last write is found by its new id.
      blocks: nodes
        .filter((node) => node.selected)
        .map((node) => state.renamed[node.id] ?? node.id),
      connections: edges
        .filter((edge) => edge.selected && edge.type !== "reference")
        .map((edge) => (edge.data as { index: number }).index),
    }),
    [nodes, edges, state.renamed],
  );

  const selectBlocks = useCallback((ids: string[]) => {
    // Ids not drawn yet (a block just added or renamed) are selected when they are.
    wanted.current = ids.every((id) => drawn.current.has(id)) ? null : ids;
    setNodes((previous) => previous.map((node) => ({ ...node, selected: ids.includes(node.id) })));
    setEdges((previous) => previous.map((edge) => ({ ...edge, selected: false })));
  }, []);

  /** Sends one action, built from the model shown; refused while a write awaits its answer. */
  /** Whether a change can be made now; while a write awaits its answer, says to wait. */
  const free = useCallback(() => {
    if (session.getState().busy) setNotice(WAIT);
    return session.canWrite();
  }, [session]);

  const send = useCallback(
    (label: string, edits: EditPlan) =>
      (free()
        ? session.write(editsWrite(label, edits))
        : Promise.resolve(null)) as Promise<ApiResult<unknown> | null>,
    [session, free],
  );

  const add = useCallback(
    (type: string, at: Point) => {
      setPlacing(null);
      if (!free()) return;
      let made = "";
      void session
        .write((current) => {
          made = nextId(current, type);
          return {
            kind: "edits",
            label: `add ${made}`,
            edits: [
              { edit: "add_component", id: made, type, params: {}, ui: { x: at.x, y: at.y } },
            ],
          };
        })
        .then((result) => {
          if (result?.kind === "ok") {
            selectBlocks([made]);
            setFocusAfter(made);
          }
        });
    },
    [session, selectBlocks, free],
  );

  const addAtCentre = useCallback(
    (type: string) => {
      const box = area.current?.getBoundingClientRect();
      const centre = box
        ? flow.screenToFlowPosition({ x: box.left + box.width / 2, y: box.top + box.height / 2 })
        : { x: 0, y: 0 };
      add(type, freePlace(model, centre));
    },
    [add, flow, model],
  );

  /** Adds a block centred on the pointer; without a usable pointer, as the keyboard does. */
  const addAtPointer = (type: string, clientX: number, clientY: number) => {
    const at = flow.screenToFlowPosition({ x: clientX, y: clientY });
    if (!Number.isFinite(at.x) || !Number.isFinite(at.y)) {
      addAtCentre(type);
      return;
    }
    add(type, { x: snap(at.x - BLOCK_WIDTH / 2), y: snap(at.y - BLOCK_HEIGHT / 2) });
  };

  const deletePlan = useCallback((): (DeletePlan & { edges: number[] }) | null => {
    const blocks = selection.blocks;
    const removed = new Set(blocks);
    const all = connections(model);
    const own = all.filter(
      (item) =>
        removed.has(splitEnd(item.from)?.[0] ?? "") || removed.has(splitEnd(item.to)?.[0] ?? ""),
    ).length;
    const others = selection.connections.filter((index) => {
      const item = all[index];
      return (
        item !== undefined &&
        !removed.has(splitEnd(item.from)?.[0] ?? "") &&
        !removed.has(splitEnd(item.to)?.[0] ?? "")
      );
    });
    if (blocks.length === 0 && others.length === 0) return null;
    return { blocks, connections: own + others.length, edges: others };
  }, [selection, model]);

  const doDelete = useCallback(
    (plan: DeletePlan & { edges: number[] }) => {
      const all = connections(model);
      const edits: Edit[] = [
        ...plan.blocks.map((id): Edit => ({ edit: "remove_component", id })),
        ...plan.edges
          .map((index) => all[index])
          .filter((item) => item !== undefined)
          .map((item): Edit => ({ edit: "disconnect", from: item.from })),
      ];
      const label =
        plan.blocks.length > 0
          ? `delete ${plan.blocks.join(", ")}`
          : `disconnect ${plan.edges.map((index) => all[index]?.from).join(", ")}`;
      const order = components(model).map((item) => item.id);
      const next = order.find(
        (id, index) =>
          !plan.blocks.includes(id) && index > order.indexOf(plan.blocks[0] ?? order[0] ?? ""),
      );
      void send(label, edits).then((result) => {
        if (result?.kind !== "ok") return;
        if (plan.blocks.length > 0) {
          setNotice(
            `Deleted ${plan.blocks.join(", ")} and ${plan.connections} connection${
              plan.connections === 1 ? "" : "s"
            }. Undo (Ctrl+Z).`,
          );
        }
        selectBlocks([]);
        if (next !== undefined) setFocusAfter(next);
        else area.current?.focus();
      });
    },
    [model, send, selectBlocks],
  );

  const requestDelete = useCallback(() => {
    if (readOnly || !free()) return;
    const plan = deletePlan();
    if (plan === null) return;
    if (plan.blocks.length > 0 && settings.interface.ask_before_deleting) setDeleting(plan);
    else doDelete(plan);
  }, [readOnly, free, deletePlan, settings.interface.ask_before_deleting, doDelete]);

  const confirmDelete = (dontAskAgain: boolean) => {
    const plan = deleting;
    setDeleting(null);
    if (plan === null) return;
    if (dontAskAgain) {
      void save({ interface: { ...settings.interface, ask_before_deleting: false } });
    }
    doDelete(plan);
  };

  /**
   * Arrow keys: each press is a move from where the model has the block, sent at once;
   * presses close together are one undo step (the session). A press while a write awaits
   * its answer is not taken.
   */
  const moveSelection = (dx: number, dy: number) => {
    const all = components(model);
    const positions = new Map<string, Point>();
    for (const node of nodes) {
      const index = all.findIndex((item) => item.id === node.id);
      const component = all[index];
      if (!node.selected || component === undefined) continue;
      const from = positionOf(component, index);
      positions.set(node.id, { x: from.x + dx, y: from.y + dy });
    }
    void session.move(positions, true);
  };

  const onNodesChange = useCallback((changes: NodeChange<BlockNodeType>[]) => {
    setNodes((previous) => applyNodeChanges(changes, previous));
  }, []);

  const onEdgesChange = useCallback((changes: EdgeChange[]) => {
    setEdges((previous) => applyEdgeChanges(changes, previous));
  }, []);

  const onNodeDragStop = useCallback(
    (_event: unknown, _node: Node, dragged: Node[]) => {
      const positions = new Map<string, Point>();
      for (const node of dragged) {
        const component = components(model).find((item) => item.id === node.id);
        const at = { x: snap(node.position.x), y: snap(node.position.y) };
        const was = component ? positionOf(component, components(model).indexOf(component)) : null;
        if (component && (was?.x !== at.x || was?.y !== at.y || component.ui === undefined)) {
          positions.set(component.id, at);
        }
      }
      if (positions.size > 0) void session.move(positions);
    },
    [model, session],
  );

  /** `connect`; when it replaces a connection, a notice says so (canvas-interactions.md). */
  const connectEnds = useCallback(
    (from: string, to: string) => {
      const was = connections(model).find((item) => item.from === from)?.to;
      void send(`connect ${from} to ${to}`, [{ edit: "connect", from, to }]).then((result) => {
        if (result?.kind === "ok" && was !== undefined && was !== to) {
          setNotice(`${from} now goes to ${to} (was ${was}).`);
        }
      });
    },
    [model, send],
  );

  const onConnect = useCallback(
    (connection: FlowConnection) => {
      if (!connection.sourceHandle || !connection.targetHandle) return;
      connectEnds(
        `${connection.source}.${connection.sourceHandle}`,
        `${connection.target}.${connection.targetHandle}`,
      );
    },
    [connectEnds],
  );

  const isValidConnection = useCallback(
    (connection: Edge | FlowConnection) =>
      connection.sourceHandle !== "ref-out" &&
      connection.targetHandle !== "ref-in" &&
      Boolean(connection.sourceHandle) &&
      Boolean(connection.targetHandle),
    [],
  );

  const onDragOver = (event: DragEvent) => {
    if (locked || !event.dataTransfer.types.includes(BLOCK_MIME)) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
  };

  const onDrop = (event: DragEvent) => {
    const type = event.dataTransfer.getData(BLOCK_MIME);
    if (locked || type === "") return;
    event.preventDefault();
    addAtPointer(type, event.clientX, event.clientY);
  };

  const onPaneClick = (event: ReactMouseEvent) => {
    if (placing === null || locked) return;
    addAtPointer(placing, event.clientX, event.clientY);
  };

  const onCanvasKey = (event: ReactKeyboardEvent) => {
    if (isTyping(event.target)) return;
    const control = event.ctrlKey || event.metaKey;
    const key = event.key;
    if (key === "Delete" || key === "Backspace") {
      event.preventDefault();
      requestDelete();
    } else if (key.startsWith("Arrow") && !control) {
      event.preventDefault();
      event.stopPropagation();
      const step = event.shiftKey ? 40 : 8;
      const dx = key === "ArrowLeft" ? -1 : key === "ArrowRight" ? 1 : 0;
      const dy = key === "ArrowUp" ? -1 : key === "ArrowDown" ? 1 : 0;
      if (selection.blocks.length > 0 && !locked) moveSelection(dx * step, dy * step);
      else {
        const view = flow.getViewport();
        void flow.setViewport({ ...view, x: view.x - dx * 40, y: view.y - dy * 40 });
      }
    } else if ((key === "c" || key === "C") && !control && !event.altKey) {
      if (selection.blocks.length === 1 && !locked) {
        event.preventDefault();
        setConnecting(selection.blocks[0] ?? null);
      }
    } else if (key === "F2") {
      if (selection.blocks.length === 1) {
        event.preventDefault();
        document.getElementById("block-id")?.focus();
      }
    } else if (control && (key === "a" || key === "A")) {
      event.preventDefault();
      selectBlocks(components(model).map((item) => item.id));
    } else if (key === "Escape") {
      if (placing !== null) setPlacing(null);
      else selectBlocks([]);
    } else if (control && (key === "=" || key === "+")) {
      event.preventDefault();
      void flow.zoomIn();
    } else if (control && key === "-") {
      event.preventDefault();
      void flow.zoomOut();
    } else if (control && key === "0") {
      event.preventDefault();
      void flow.fitView();
    } else if (control && key === "1") {
      event.preventDefault();
      void flow.zoomTo(1);
    }
  };

  const blocked = runBlocked(state);
  const run = useCallback(() => {
    if (runBlocked(session.getState()) !== null) return;
    onGo({ screen: "monitor", projectId: project.id });
  }, [session, onGo, project.id]);

  const undo = useCallback(() => {
    if (!locked) void session.undo();
  }, [session, locked]);
  const redo = useCallback(() => {
    if (!locked) void session.redo();
  }, [session, locked]);

  // Undo, redo and Run work from anywhere on the screen, except while typing in a field.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape" && placing !== null) {
        setPlacing(null);
        return;
      }
      if (!(event.ctrlKey || event.metaKey) || isTyping(event.target)) return;
      if (document.querySelector('[role="dialog"]') !== null) return;
      const key = event.key.toLowerCase();
      if (key === "z" && !event.shiftKey) {
        event.preventDefault();
        undo();
      } else if ((key === "z" && event.shiftKey) || key === "y") {
        event.preventDefault();
        redo();
      } else if (key === "enter") {
        event.preventDefault();
        run();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [undo, redo, run, placing]);

  const chooseProblem = (issue: Issue, component: string | null) => {
    if (component !== null && components(model).some((item) => item.id === component)) {
      selectBlocks([component]);
      const node = flow.getNode(component);
      if (node) {
        const width = node.measured?.width ?? BLOCK_WIDTH;
        const height = node.measured?.height ?? BLOCK_HEIGHT;
        void flow.setCenter(node.position.x + width / 2, node.position.y + height / 2, {
          zoom: flow.getZoom(),
        });
      }
    } else if (issue.path.startsWith("/experiments")) {
      onGo({ screen: "experiment", projectId: project.id });
    } else {
      selectBlocks([]);
    }
  };

  const actions: PanelActions = {
    send: async (label, edits) => {
      const result = await send(label, edits);
      if (result !== null && result.kind !== "ok") shownLocally.current = result;
      return result;
    },
    edit: (label, edits) => {
      void send(label, edits);
    },
    replace: (label, build) => {
      if (free()) void session.write(modelWrite(label, build));
    },
    select: selectBlocks,
    remove: requestDelete,
    connect: connectEnds,
  };

  const connectingBlock =
    connecting === null ? undefined : components(model).find((item) => item.id === connecting);
  const inputEnds = components(model).flatMap((component) =>
    portsOf(component, types[component.type]).inputs.map((port) => `${component.id}.${port}`),
  );

  const tools = (
    <div className="canvas-tools">
      <SaveState state={state} />
      <button
        type="button"
        className="secondary tool"
        aria-label={state.undoLabel ? `Undo: ${state.undoLabel}` : "Undo"}
        title={state.undoLabel ? `Undo: ${state.undoLabel} (Ctrl+Z)` : "Nothing to undo"}
        disabled={state.undoLabel === null || readOnly}
        aria-disabled={busy || undefined}
        onClick={undo}
      >
        <ArrowUUpLeftIcon aria-hidden="true" size={16} />
        Undo
      </button>
      <button
        type="button"
        className="secondary tool"
        aria-label={state.redoLabel ? `Redo: ${state.redoLabel}` : "Redo"}
        title={state.redoLabel ? `Redo: ${state.redoLabel} (Ctrl+Shift+Z)` : "Nothing to redo"}
        disabled={state.redoLabel === null || readOnly}
        aria-disabled={busy || undefined}
        onClick={redo}
      >
        <ArrowUUpRightIcon aria-hidden="true" size={16} />
        Redo
      </button>
      <label className="experiment-picker">
        <span className="muted small">Experiment</span>
        <select
          className="mono"
          value={chosenExperiment}
          onChange={(event) => setExperiment(event.target.value)}
        >
          {experiments.map((item) => (
            <option key={item.id} value={item.id}>
              {item.id}
            </option>
          ))}
        </select>
      </label>
      <span className="run-wrap">
        <button
          type="button"
          className="primary run"
          aria-disabled={blocked !== null}
          aria-describedby={blocked ? "run-reason" : undefined}
          data-blocked={blocked?.pointer}
          title={blocked?.reason}
          onClick={run}
        >
          <PlayIcon aria-hidden="true" size={16} weight="fill" />
          Run
        </button>
        {blocked?.pointer === "errors" ? (
          <button
            type="button"
            id="run-reason"
            className="link run-reason run-reason-error"
            onClick={() => problems.current?.focus()}
          >
            {blocked.reason}
          </button>
        ) : blocked ? (
          <span id="run-reason" className="run-reason">
            {blocked.reason}
          </span>
        ) : null}
      </span>
    </div>
  );

  const refusal = state.refusal !== shownLocally.current ? state.refusal : null;

  return (
    <BusyContext.Provider value={busy}>
      <div className={`canvas-screen${placing !== null ? " placing" : ""}`} aria-busy={busy}>
        {toolbar ? createPortal(tools, toolbar) : tools}
        <h1 className="visually-hidden">Canvas</h1>
        <Palette
          types={types}
          placing={placing}
          readOnly={readOnly}
          onPlace={setPlacing}
          onAdd={addAtCentre}
        />
        <div className="canvas-centre">
          <div className="canvas-notices" aria-live="polite">
            {state.failing ? (
              <p className="notice notice-error">
                Not saved: the service is not answering. Retrying.
              </p>
            ) : null}
            {state.eventsClosed !== null ? (
              <p className="notice notice-error">{LOST_CONTACT}</p>
            ) : null}
            <ServiceProblem result={refusal} />
            {notice !== null ? (
              <p className="notice">
                <span>{notice}</span>
                <button
                  type="button"
                  className="icon-button"
                  aria-label="Dismiss"
                  onClick={() => setNotice(null)}
                >
                  <XIcon aria-hidden="true" size={14} />
                </button>
              </p>
            ) : null}
          </div>
          <section
            ref={area}
            className="canvas-flow"
            data-region="canvas"
            aria-label="Canvas"
            tabIndex={-1}
            onKeyDownCapture={onCanvasKey}
            onDragOver={onDragOver}
            onDrop={onDrop}
          >
            <ReactFlow
              nodes={nodes}
              edges={edges}
              nodeTypes={nodeTypes}
              edgeTypes={edgeTypes}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onNodeDragStop={onNodeDragStop}
              onConnect={onConnect}
              isValidConnection={isValidConnection}
              onPaneClick={onPaneClick}
              minZoom={MIN_ZOOM}
              maxZoom={MAX_ZOOM}
              snapToGrid
              snapGrid={[8, 8]}
              deleteKeyCode={null}
              fitView
              fitViewOptions={{ maxZoom: 1 }}
              onlyRenderVisibleElements
              nodesDraggable={!locked}
              nodesConnectable={!locked}
              elementsSelectable
              connectOnClick
            >
              <Background variant={BackgroundVariant.Dots} gap={16} />
              <ZoomControls />
              <MiniMap pannable zoomable ariaLabel="Overview of the model" />
            </ReactFlow>
          </section>
          <ProblemsList
            ref={problems}
            model={model}
            issues={state.issues}
            checking={state.checking}
            onChoose={chooseProblem}
          />
        </div>
        <SidePanel
          client={client}
          model={model}
          selection={selection}
          types={types}
          issues={state.issues}
          readOnly={readOnly}
          actions={actions}
          renamed={state.renamed}
        />
        {deleting !== null ? (
          <DeleteDialog
            plan={deleting}
            onCancel={() => setDeleting(null)}
            onDelete={confirmDelete}
          />
        ) : null}
        {connectingBlock !== undefined ? (
          <ConnectDialog
            block={connectingBlock.id}
            outputs={portsOf(connectingBlock, types[connectingBlock.type]).outputs}
            inputs={inputEnds}
            current={(port) =>
              connections(model).find((item) => item.from === `${connectingBlock.id}.${port}`)?.to
            }
            onCancel={() => setConnecting(null)}
            onConnect={(from, to) => {
              setConnecting(null);
              connectEnds(from, to);
            }}
          />
        ) : null}
      </div>
    </BusyContext.Provider>
  );
}
