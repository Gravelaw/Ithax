/**
 * The Canvas screen of an `optimization` model, a plan (spec 3 "Screens" 2 and "Canvas
 * behaviour", Optimization models; `docs/design/canvas-interactions.md` "The model and the
 * canvas"; owner review choice 4; `docs/design/wireframes/09-optimization.svg`).
 *
 * Two views of the same model, with a switch: the Table view, where the decisions
 * (variables), the goal (objective) and the limits (constraints) are added, edited and
 * removed, each change one batch of `set_path` and `remove_path` edits (`plan.ts`) and one
 * undo step; and the Diagram view, which draws each decision as a card linked to the goal
 * and the limits that use it. Saving, undo and redo, validation, Run, the review of an
 * outside change and the one-write rule are the Canvas's own (`CanvasSession`): while a
 * write awaits its answer no change is taken, and a field's commit is refused with a notice.
 */
import {
  ArrowUUpLeftIcon,
  ArrowUUpRightIcon,
  GaugeIcon,
  GraphIcon,
  PlayIcon,
  PlusIcon,
  SlidersHorizontalIcon,
  TableIcon,
  TargetIcon,
  TrashIcon,
  XIcon,
} from "@phosphor-icons/react";
import { type ReactNode, useCallback, useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import type { Edit, Issue, LinearConstraint, Model, Project, Variable } from "../api/types";
import type { Route } from "../app/router";
import { LOST_CONTACT, ServiceProblem } from "../components/ServiceProblem";
import { useMounted } from "../components/useMounted";
import { BusyContext, lock, RevisionContext, useBusy } from "./busy";
import { pointer, shown } from "./model";
import { own } from "./own";
import { ProblemsList } from "./ProblemsList";
import {
  addDecision,
  addLimit,
  CARD_HEIGHT,
  CARD_WIDTH,
  coefficientEdits,
  constraintsOf,
  diagramLayout,
  fieldEdits,
  goalSentence,
  isIndexed,
  limitText,
  linearOf,
  type Row,
  removeDecision,
  removeLimit,
  renameDecision,
  repeatsText,
  setsOf,
  tableOf,
  textEdits,
  variablesOf,
} from "./plan";
import { editsWrite } from "./plans";
import {
  MarkButtons,
  MarkChip,
  OutsideNotice,
  type ReviewActions,
  ReviewContext,
  ReviewCount,
  ReviewList,
} from "./ReviewParts";
import { type Change, changeKind } from "./review";
import { CommitInput, FieldIssues } from "./SettingFields";
import { type CanvasSession, clientsOf, marksOf, type SessionState } from "./session";
import { NOTICE_MS, runBlocked, SaveState, WAIT } from "./Toolbar";

type View = "table" | "diagram";

/** Builds one change's edits from the model shown; `null` or `[]` sends nothing. */
type Build = (model: Model) => Edit[] | null;

interface PlanContext {
  model: Model;
  /** Whether the model uses sets and tables (spec 1 format 0.2; AKS-123). */
  indexed: boolean;
  issues: Issue[];
  readOnly: boolean;
  marks: readonly Change[];
  edit(label: string, change: Build): void;
}

const KINDS: readonly [string, string][] = [
  ["continuous", "Continuous (any amount)"],
  ["integer", "Integer (whole numbers)"],
  ["binary", "Binary (yes or no)"],
];
const SENSES: readonly [string, string][] = [
  ["maximize", "Maximize"],
  ["minimize", "Minimize"],
];
const OPS: readonly [string, string][] = [
  ["<=", "at most (≤)"],
  [">=", "at least (≥)"],
  ["==", "exactly (=)"],
];

function text(value: unknown): string {
  return value === undefined ? "" : shown(value);
}

/** The issues whose `path` is `path`. */
function at(issues: Issue[], path: string): Issue[] {
  return issues.filter((issue) => issue.path === path);
}

/** The issues inside `path` that no field in `fields` shows. */
function besides(issues: Issue[], path: string, fields: readonly string[]): Issue[] {
  return issues.filter(
    (issue) =>
      (issue.path === path || issue.path.startsWith(`${path}/`)) && !fields.includes(issue.path),
  );
}

/** A choice from a fixed list; a value the model holds that is not in it is shown too. */
function Choice({
  label,
  value,
  choices,
  onChoose,
  readOnly,
  path,
}: {
  label: string;
  value: unknown;
  choices: readonly [string, string][];
  onChoose: (value: string) => void;
  readOnly: boolean;
  path: string;
}) {
  const busy = useBusy();
  const current = text(value);
  const known = choices.some(([choice]) => choice === current);
  return (
    <select
      aria-label={label}
      data-path={path}
      value={current}
      {...lock(readOnly, busy)}
      onChange={(event) => onChoose(event.target.value)}
    >
      {known ? null : <option value={current}>{current === "" ? "(none)" : current}</option>}
      {choices.map(([choice, words]) => (
        <option key={choice} value={choice}>
          {words}
        </option>
      ))}
    </select>
  );
}

/** A text box for the value at `path`: committed on Enter or on leaving it. */
function Cell({
  ctx,
  path,
  label,
  value,
  onCommit,
  mono = true,
}: {
  ctx: PlanContext;
  path: string;
  label: string;
  value: unknown;
  onCommit: (text: string) => void;
  mono?: boolean;
}) {
  const issues = at(ctx.issues, path);
  return (
    <span className="plan-cell" data-path={path}>
      <CommitInput
        id={`plan${path.replace(/[^a-zA-Z0-9]/g, "-")}`}
        value={text(value)}
        label={label}
        mono={mono}
        readOnly={ctx.readOnly}
        invalid={issues.some((issue) => issue.severity === "error")}
        onCommit={onCommit}
      />
      <FieldIssues issues={issues} />
    </span>
  );
}

function RemoveButton({
  label,
  onRemove,
  readOnly,
}: {
  label: string;
  onRemove: () => void;
  readOnly: boolean;
}) {
  const busy = useBusy();
  return (
    <button
      type="button"
      className="icon-button"
      aria-label={label}
      title={label}
      {...lock(readOnly, busy)}
      onClick={onRemove}
    >
      <TrashIcon aria-hidden="true" size={16} />
    </button>
  );
}

function AddButton({
  label,
  onAdd,
  readOnly,
}: {
  label: string;
  onAdd: () => void;
  readOnly: boolean;
}) {
  const busy = useBusy();
  return (
    <button type="button" className="secondary" {...lock(readOnly, busy)} onClick={onAdd}>
      <PlusIcon aria-hidden="true" size={16} />
      {label}
    </button>
  );
}

function markOf(marks: readonly Change[], key: string, id: string): Change | undefined {
  return marks.find(
    (item) => item.ref.kind === "list" && item.ref.key === key && item.ref.id === id,
  );
}

/** The mark cell of a row: its chip and Accept and Reject, or nothing. */
function MarkCell({ item, subject }: { item: Change | undefined; subject: string }) {
  if (item === undefined) return <td />;
  return (
    <td className="plan-mark">
      <MarkChip kind={changeKind(item)} />
      <MarkButtons item={item} subject={subject} />
    </td>
  );
}

/** Rows removed by another client, drawn as ghosts until reviewed. */
function GhostRows({
  ctx,
  list,
  noun,
  columns,
}: {
  ctx: PlanContext;
  list: string;
  noun: string;
  columns: number;
}) {
  const removed = ctx.marks.filter(
    (item) => item.ref.kind === "list" && item.ref.key === list && item.after === undefined,
  );
  return (
    <>
      {removed.map((item) => {
        const id = item.ref.kind === "list" ? item.ref.id : "";
        return (
          <tr key={item.key} className="plan-row plan-ghost">
            <td colSpan={columns} className="mono">
              {id}
            </td>
            <MarkCell item={item} subject={`${noun} ${id}`} />
          </tr>
        );
      })}
    </>
  );
}

function Decisions({ ctx }: { ctx: PlanContext }) {
  const decisions = variablesOf(ctx.model);
  return (
    <section className="plan-section" aria-labelledby="decisions-heading">
      <h3 className="heading plan-heading" id="decisions-heading">
        <SlidersHorizontalIcon aria-hidden="true" size={18} />
        Decisions <span className="muted small">what you can choose</span>
      </h3>
      <FieldIssues issues={at(ctx.issues, "/variables")} />
      {decisions.length === 0 ? <p className="muted">No decisions yet.</p> : null}
      <table className="plan-table">
        <thead>
          <tr>
            <th scope="col">Name</th>
            <th scope="col">Kind</th>
            <th scope="col">Lower bound</th>
            <th scope="col">Upper bound</th>
            <th scope="col">
              <span className="visually-hidden">Remove</span>
            </th>
            <th scope="col">
              <span className="visually-hidden">Review</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {decisions.map((row) => (
            <DecisionRow key={`${row.index}:${String(row.item.id)}`} ctx={ctx} row={row} />
          ))}
          <GhostRows ctx={ctx} list="variables" noun="decision" columns={5} />
        </tbody>
      </table>
      <AddButton
        label="Add decision"
        readOnly={ctx.readOnly}
        onAdd={() => ctx.edit("add a decision", addDecision)}
      />
    </section>
  );
}

function DecisionRow({ ctx, row }: { ctx: PlanContext; row: Row<Variable> }) {
  const { index, item } = row;
  const id = text(item.id);
  const base = `/variables/${index}`;
  const fields = ["id", "type", "lower", "upper"].map((key) => `${base}/${key}`);
  const mark = markOf(ctx.marks, "variables", id);
  const kind = mark ? changeKind(mark) : null;
  return (
    <>
      <tr className={`plan-row${kind ? ` mark-${kind}` : ""}`}>
        <td>
          <Cell
            ctx={ctx}
            path={`${base}/id`}
            label={`Name of decision ${index + 1}`}
            value={item.id}
            onCommit={(name) =>
              ctx.edit(`rename ${id} to ${name}`, (model) => renameDecision(model, index, name))
            }
          />
          {repeatsText(item) ? <span className="small muted">{repeatsText(item)}</span> : null}
        </td>
        <td>
          <Choice
            label={`Kind of ${id}`}
            path={`${base}/type`}
            value={item.type}
            choices={KINDS}
            readOnly={ctx.readOnly}
            onChoose={(choice) =>
              ctx.edit(`set the kind of ${id}`, (model) => textEdits(model, `${base}/type`, choice))
            }
          />
          <FieldIssues issues={at(ctx.issues, `${base}/type`)} />
        </td>
        {(["lower", "upper"] as const).map((bound) => (
          <td key={bound}>
            <Cell
              ctx={ctx}
              path={`${base}/${bound}`}
              label={`${bound === "lower" ? "Lower" : "Upper"} bound of ${id}`}
              value={item[bound]}
              onCommit={(value) =>
                ctx.edit(`set the ${bound} bound of ${id}`, (model) =>
                  fieldEdits(model, `${base}/${bound}`, value, true),
                )
              }
            />
          </td>
        ))}
        <td>
          <RemoveButton
            label={`Remove decision ${id}`}
            readOnly={ctx.readOnly}
            onRemove={() => ctx.edit(`remove ${id}`, (model) => removeDecision(model, index))}
          />
        </td>
        <MarkCell item={mark} subject={`decision ${id}`} />
      </tr>
      {besides(ctx.issues, base, fields).length > 0 ? (
        <tr>
          <td colSpan={6}>
            <FieldIssues issues={besides(ctx.issues, base, fields)} />
          </td>
        </tr>
      ) : null}
    </>
  );
}

function Goal({ ctx }: { ctx: PlanContext }) {
  const objective = (ctx.model.objective ?? {}) as { sense?: unknown };
  const linear = linearOf(ctx.model.objective);
  // A decision over sets gets its coefficients from terms, which these views do not edit.
  const decisions = variablesOf(ctx.model).filter(({ item }) => setsOf(item, "over").length === 0);
  const mark = ctx.marks.find((item) => item.ref.kind === "top" && item.ref.key === "objective");
  const shownPaths = [
    "/objective/sense",
    ...decisions.map(({ item }) => `/objective/linear${pointer([text(item.id)])}`),
  ];
  return (
    <section
      className={`plan-section${mark ? ` mark-${changeKind(mark)}` : ""}`}
      aria-labelledby="goal-heading"
    >
      <h3 className="heading plan-heading" id="goal-heading">
        <TargetIcon aria-hidden="true" size={18} />
        Goal <span className="muted small">what counts as best</span>
        {mark ? (
          <span className="plan-mark">
            <MarkChip kind={changeKind(mark)} />
            <MarkButtons item={mark} subject="the goal" />
          </span>
        ) : null}
      </h3>
      <div className="plan-goal">
        <Choice
          label="Maximize or minimize"
          path="/objective/sense"
          value={objective.sense}
          choices={SENSES}
          readOnly={ctx.readOnly}
          onChoose={(choice) =>
            ctx.edit("set the goal", (model) => textEdits(model, "/objective/sense", choice))
          }
        />
        {decisions.map(({ item }) => {
          const name = text(item.id);
          return (
            <div key={name} className="plan-coefficient">
              <span className="field-label mono" aria-hidden="true">
                {name}
              </span>
              <Cell
                ctx={ctx}
                path={`/objective/linear${pointer([name])}`}
                label={`Coefficient of ${name} in the goal`}
                value={own(linear, name)}
                onCommit={(value) =>
                  ctx.edit(`set ${name} in the goal`, (model) =>
                    coefficientEdits(model, "/objective", name, value),
                  )
                }
              />
            </div>
          );
        })}
      </div>
      <p className="muted">{goalSentence(ctx.model)}</p>
      <FieldIssues issues={besides(ctx.issues, "/objective", shownPaths)} />
    </section>
  );
}

function Limits({ ctx }: { ctx: PlanContext }) {
  const limits = constraintsOf(ctx.model);
  const decisions = variablesOf(ctx.model)
    .filter(({ item }) => setsOf(item, "over").length === 0)
    .map(({ item }) => text(item.id));
  const reads = ctx.indexed ? 1 : 0;
  return (
    <section className="plan-section" aria-labelledby="limits-heading">
      <h3 className="heading plan-heading" id="limits-heading">
        <GaugeIcon aria-hidden="true" size={18} />
        Limits <span className="muted small">what holds you back</span>
      </h3>
      <FieldIssues issues={at(ctx.issues, "/constraints")} />
      {limits.length === 0 ? <p className="muted">No limits yet.</p> : null}
      <table className="plan-table">
        <thead>
          <tr>
            <th scope="col">Name</th>
            {decisions.map((name) => (
              <th scope="col" key={name} className="mono">
                {name}
              </th>
            ))}
            {ctx.indexed ? <th scope="col">Reads as</th> : null}
            <th scope="col">Must be</th>
            <th scope="col">Limit</th>
            <th scope="col">
              <span className="visually-hidden">Remove</span>
            </th>
            <th scope="col">
              <span className="visually-hidden">Review</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {limits.map((row) => (
            <LimitRow
              key={`${row.index}:${String(row.item.id)}`}
              ctx={ctx}
              row={row}
              decisions={decisions}
            />
          ))}
          <GhostRows
            ctx={ctx}
            list="constraints"
            noun="limit"
            columns={decisions.length + reads + 4}
          />
        </tbody>
      </table>
      <AddButton
        label="Add limit"
        readOnly={ctx.readOnly}
        onAdd={() => ctx.edit("add a limit", addLimit)}
      />
    </section>
  );
}

function LimitRow({
  ctx,
  row,
  decisions,
}: {
  ctx: PlanContext;
  row: Row<LinearConstraint>;
  decisions: string[];
}) {
  const { index, item } = row;
  const id = text(item.id);
  const base = `/constraints/${index}`;
  const linear = linearOf(item);
  const fields = [
    `${base}/id`,
    `${base}/op`,
    `${base}/rhs`,
    ...decisions.map((name) => `${base}/linear${pointer([name])}`),
  ];
  const mark = markOf(ctx.marks, "constraints", id);
  const kind = mark ? changeKind(mark) : null;
  return (
    <>
      <tr className={`plan-row${kind ? ` mark-${kind}` : ""}`}>
        <td>
          <Cell
            ctx={ctx}
            path={`${base}/id`}
            label={`Name of limit ${index + 1}`}
            value={item.id}
            onCommit={(name) =>
              ctx.edit(`rename ${id} to ${name}`, (model) => textEdits(model, `${base}/id`, name))
            }
          />
        </td>
        {decisions.map((name) => (
          <td key={name}>
            <Cell
              ctx={ctx}
              path={`${base}/linear${pointer([name])}`}
              label={`Coefficient of ${name} in ${id}`}
              value={own(linear, name)}
              onCommit={(value) =>
                ctx.edit(`set ${name} in ${id}`, (model) =>
                  coefficientEdits(model, base, name, value),
                )
              }
            />
          </td>
        ))}
        {ctx.indexed ? <td className="small">{limitText(item, ctx.model)}</td> : null}
        <td>
          <Choice
            label={`How ${id} must hold`}
            path={`${base}/op`}
            value={item.op}
            choices={OPS}
            readOnly={ctx.readOnly}
            onChoose={(choice) =>
              ctx.edit(`set how ${id} must hold`, (model) => textEdits(model, `${base}/op`, choice))
            }
          />
          <FieldIssues issues={at(ctx.issues, `${base}/op`)} />
        </td>
        <td>
          {tableOf(item.rhs) !== null ? (
            <span className="mono" data-path={`${base}/rhs`}>
              {`table ${tableOf(item.rhs)}`}
              <FieldIssues issues={at(ctx.issues, `${base}/rhs`)} />
            </span>
          ) : (
            <Cell
              ctx={ctx}
              path={`${base}/rhs`}
              label={`Limit of ${id}`}
              value={item.rhs}
              onCommit={(value) =>
                ctx.edit(`set the limit of ${id}`, (model) =>
                  fieldEdits(model, `${base}/rhs`, value, false),
                )
              }
            />
          )}
        </td>
        <td>
          <RemoveButton
            label={`Remove limit ${id}`}
            readOnly={ctx.readOnly}
            onRemove={() => ctx.edit(`remove ${id}`, (model) => removeLimit(model, index))}
          />
        </td>
        <MarkCell item={mark} subject={`limit ${id}`} />
      </tr>
      {besides(ctx.issues, base, fields).length > 0 ? (
        <tr>
          <td colSpan={decisions.length + (ctx.indexed ? 6 : 5)}>
            <FieldIssues issues={besides(ctx.issues, base, fields)} />
          </td>
        </tr>
      ) : null}
    </>
  );
}

/** The Diagram view: decision cards linked to the goal and limit cards that use them. */
function Diagram({ model, onOpen }: { model: Model; onOpen: (path: string) => void }) {
  const layout = diagramLayout(model);
  const variables = variablesOf(model);
  const limits = new Map(constraintsOf(model).map((row) => [row.index, row.item]));
  const centre = new Map<string, { x: number; y: number }>();
  for (const card of layout.decisions)
    centre.set(`decision:${card.id}`, { x: card.x + CARD_WIDTH, y: card.y + CARD_HEIGHT / 2 });
  for (const card of layout.targets)
    centre.set(card.key, { x: card.x, y: card.y + CARD_HEIGHT / 2 });
  return (
    <div className="plan-diagram" style={{ width: layout.width, height: layout.height }}>
      <svg className="plan-lines" width={layout.width} height={layout.height} aria-hidden="true">
        {layout.lines.map((line) => {
          const from = centre.get(`decision:${line.from}`);
          const to = centre.get(line.to);
          if (!from || !to) return null;
          const lx = from.x + (to.x - from.x) * 0.72;
          const ly = from.y + (to.y - from.y) * 0.72;
          return (
            <g key={`${line.from}>${line.to}`}>
              <line x1={from.x} y1={from.y} x2={to.x} y2={to.y} className="plan-line" />
              <rect
                x={lx - 16}
                y={ly - 10}
                width={32}
                height={20}
                rx={10}
                className="plan-line-label"
              />
              <text x={lx} y={ly + 4} textAnchor="middle" className="plan-line-text">
                {line.label}
              </text>
            </g>
          );
        })}
      </svg>
      {layout.decisions.map((card) => {
        const variable = variables.find((row) => row.index === card.index)?.item;
        const bounds = [
          variable?.lower !== undefined ? `≥ ${text(variable.lower)}` : null,
          variable?.upper !== undefined ? `≤ ${text(variable.upper)}` : null,
        ].filter(Boolean);
        return (
          <button
            type="button"
            key={card.key}
            className="plan-card"
            style={{ left: card.x, top: card.y, width: CARD_WIDTH, height: CARD_HEIGHT }}
            onClick={() => onOpen(`/variables/${card.index}/id`)}
          >
            <span className="plan-card-title">
              <SlidersHorizontalIcon aria-hidden="true" size={16} />
              <span className="mono">{card.id}</span>
            </span>{" "}
            <span className="small muted">
              decision, {text(variable?.type)}
              {bounds.length > 0 ? ` ${bounds.join(", ")}` : ""}
              {repeatsText(variable) ? `, ${repeatsText(variable)}` : ""}
            </span>
          </button>
        );
      })}
      {layout.targets.map((card) => {
        const limit = limits.get(card.index);
        const goal = card.kind === "goal";
        return (
          <button
            type="button"
            key={card.key}
            className="plan-card"
            style={{ left: card.x, top: card.y, width: CARD_WIDTH, height: CARD_HEIGHT }}
            onClick={() => onOpen(goal ? "/objective/sense" : `/constraints/${card.index}/id`)}
          >
            <span className="plan-card-title">
              {goal ? (
                <TargetIcon aria-hidden="true" size={16} />
              ) : (
                <GaugeIcon aria-hidden="true" size={16} />
              )}
              {goal ? "Goal" : <span className="mono">{text(limit?.id)}</span>}
            </span>{" "}
            <span className="small muted">
              {goal ? goalSentence(model) : limit ? limitText(limit, model) : ""}
            </span>
          </button>
        );
      })}
    </div>
  );
}

export function PlanScreen({
  project,
  toolbar,
  onGo,
  state,
  model,
  session,
}: {
  project: Project;
  toolbar: HTMLElement | null;
  onGo: (route: Route) => void;
  state: SessionState;
  model: Model;
  session: CanvasSession;
}) {
  const readOnly = state.failing;
  const busy = state.busy;
  const locked = readOnly || busy;
  const [view, setView] = useState<View>("table");
  const [notice, setNotice] = useState<string | null>(null);
  const [dismissed, setDismissed] = useState(0);
  const [focusPath, setFocusPath] = useState<string | null>(null);
  const marks = useMemo(
    () => marksOf({ baseline: state.baseline, model }),
    [state.baseline, model],
  );

  useEffect(() => {
    if (notice === null) return;
    const timer = setTimeout(() => setNotice(null), NOTICE_MS);
    return () => clearTimeout(timer);
  }, [notice]);

  // Opens a field (from the Diagram view, the problems list or a new row) once it is drawn:
  // the field its path names, else the nearest one above it.
  useEffect(() => {
    if (focusPath === null || view !== "table") return;
    const frame = requestAnimationFrame(() => {
      const field = (path: string) =>
        document.querySelector<HTMLElement>(
          `[data-path="${CSS.escape(path)}"] input, select[data-path="${CSS.escape(path)}"]`,
        );
      // The field the path names, else the nearest above it, else that row's name.
      let path = focusPath;
      while (path !== "") {
        const found = field(path) ?? field(`${path}/id`);
        if (found) {
          found.focus();
          break;
        }
        path = path.slice(0, path.lastIndexOf("/"));
      }
      setFocusPath(null);
    });
    return () => cancelAnimationFrame(frame);
  }, [focusPath, view]);

  /** Whether a change can be made now; while a write awaits its answer, says to wait. */
  const free = useCallback(() => {
    if (session.getState().busy) setNotice(WAIT);
    return session.canWrite();
  }, [session]);

  const edit = useCallback(
    (label: string, change: Build) => {
      if (!free()) return;
      const before = session.getState().model;
      void session.write(editsWrite(label, change)).then((result) => {
        // A new row's name takes the focus.
        if (result?.kind !== "ok" || before === null) return;
        for (const key of ["variables", "constraints"]) {
          const was = Array.isArray(before[key]) ? before[key].length : 0;
          const now = Array.isArray(result.data.model[key])
            ? (result.data.model[key] as unknown[]).length
            : 0;
          if (now === was + 1) setFocusPath(`/${key}/${now - 1}/id`);
        }
      });
    },
    [free, session],
  );

  const review: ReviewActions = useMemo(
    () => ({
      accept: (key) => {
        if (free()) session.accept(key);
      },
      reject: (key) => {
        if (free()) void session.reject(key);
      },
      acceptAll: () => {
        if (free()) session.acceptAll();
      },
      rejectAll: () => {
        if (free()) void session.rejectAll();
      },
      readOnly,
    }),
    [free, session, readOnly],
  );

  const blocked = runBlocked(state);
  // An optimization model's run takes no experiment (spec 3 `POST .../runs`).
  const mounted = useMounted();
  const run = useCallback(() => {
    if (runBlocked(session.getState()) !== null) return;
    void session.startRun(null).then((result) => {
      if (result?.kind === "ok" && mounted.current) {
        onGo({ screen: "monitor", projectId: project.id, runId: result.data.run_id });
      }
    });
  }, [session, onGo, project.id, mounted]);
  const undo = useCallback(() => {
    if (!locked) void session.undo();
  }, [session, locked]);
  const redo = useCallback(() => {
    if (!locked) void session.redo();
  }, [session, locked]);

  // Undo, redo and Run work from anywhere on the screen, except while typing in a field.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (!(event.ctrlKey || event.metaKey)) return;
      const target = event.target;
      if (target instanceof HTMLElement && ["INPUT", "SELECT", "TEXTAREA"].includes(target.tagName))
        return;
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
  }, [undo, redo, run]);

  const open = (path: string) => {
    setView("table");
    setFocusPath(path);
  };

  const tools = (
    <div className="canvas-tools">
      <SaveState state={state} />
      <ReviewCount
        count={marks.length}
        onOpen={() => {
          requestAnimationFrame(() => document.getElementById("review-heading")?.focus());
        }}
      />
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
        {blocked ? (
          <span
            id="run-reason"
            className={`run-reason${blocked.pointer === "errors" ? " run-reason-error" : ""}`}
          >
            {blocked.reason}
          </span>
        ) : null}
      </span>
    </div>
  );

  const indexed = isIndexed(model);
  const ctx: PlanContext = { model, indexed, issues: state.issues, readOnly, marks, edit };
  const views: ReactNode =
    view === "table" ? (
      <div className="plan-table-view">
        <Decisions ctx={ctx} />
        <Goal ctx={ctx} />
        <Limits ctx={ctx} />
      </div>
    ) : (
      <Diagram model={model} onOpen={open} />
    );

  return (
    <BusyContext.Provider value={busy}>
      <RevisionContext.Provider value={state.revision}>
        <ReviewContext.Provider value={review}>
          <div className="plan-screen" aria-busy={busy}>
            {toolbar ? createPortal(tools, toolbar) : tools}
            <h1 className="visually-hidden">Canvas</h1>
            <div className="plan-centre">
              <div className="canvas-notices" aria-live="polite">
                {state.failing ? (
                  <p className="notice notice-error">
                    Not saved: the service is not answering. Retrying.
                  </p>
                ) : null}
                {state.eventsClosed !== null ? (
                  <p className="notice notice-error">{LOST_CONTACT}</p>
                ) : null}
                {state.outside !== null && state.outside.seq !== dismissed ? (
                  <OutsideNotice
                    outside={state.outside}
                    clients={clientsOf(state)}
                    onDismiss={() => setDismissed(state.outside?.seq ?? 0)}
                  />
                ) : null}
                <ServiceProblem result={state.refusal} />
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
                className="plan-main"
                data-region="plan"
                aria-labelledby="plan-heading"
                tabIndex={-1}
              >
                <div className="plan-head">
                  <h2 className="title" id="plan-heading">
                    Plan: decisions, a goal and limits
                  </h2>
                  <fieldset className="view-switch">
                    <legend className="visually-hidden">View</legend>
                    <button
                      type="button"
                      aria-pressed={view === "table"}
                      onClick={() => setView("table")}
                    >
                      <TableIcon aria-hidden="true" size={16} />
                      Table
                    </button>
                    <button
                      type="button"
                      aria-pressed={view === "diagram"}
                      onClick={() => setView("diagram")}
                    >
                      <GraphIcon aria-hidden="true" size={16} />
                      Diagram
                    </button>
                  </fieldset>
                </div>
                {indexed ? (
                  <p className="notice" data-testid="indexed-notice">
                    This plan is indexed: some decisions and limits repeat over sets, with numbers
                    from tables. The views show them as written; change their sets, tables and terms
                    in the model file or with an assistant. A run solves every repeat, and Results
                    names each one, as in ship[north,city].
                  </p>
                ) : null}
                <ReviewList
                  marks={marks}
                  model={model}
                  shows={(item) =>
                    item.after !== undefined &&
                    ((item.ref.kind === "top" && item.ref.key === "objective") ||
                      (item.ref.kind === "list" &&
                        (item.ref.key === "variables" || item.ref.key === "constraints")))
                  }
                  onShow={(item) => {
                    const ref = item.ref;
                    if (ref.kind === "top") open("/objective/sense");
                    else if (ref.kind === "list") {
                      const rows =
                        ref.key === "variables" ? variablesOf(model) : constraintsOf(model);
                      const found = rows.find((row) => row.item.id === ref.id);
                      if (found) open(`/${ref.key}/${found.index}/id`);
                    }
                  }}
                />
                {views}
              </section>
              <ProblemsList
                model={model}
                issues={state.issues}
                checking={state.checking}
                onChoose={(issue) => open(issue.path)}
              />
            </div>
          </div>
        </ReviewContext.Provider>
      </RevisionContext.Provider>
    </BusyContext.Provider>
  );
}
