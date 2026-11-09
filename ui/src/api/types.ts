/**
 * The service's response bodies, as spec 3 "Endpoints" and spec 1 "Validation issues"
 * define them. Only what the interface reads is typed; later tickets add their routes here.
 */

/** A spec 1 issue object: the interface shows these as the service wrote them. */
export interface Issue {
  code: string;
  severity: "error" | "warning";
  component: string | null;
  path: string;
  message: string;
  hint: string | null;
}

/** Spec 3 "Status codes and errors": every error body. */
export interface ErrorBody {
  error: { code: string; message: string };
  issues: Issue[];
}

export type TierName = "low" | "mid" | "high";

/** `GET /v1/system`. */
export interface SystemInfo {
  cores: number;
  memory: number | null;
  graphics: string[] | null;
  tier: TierName;
  workers: number;
}

export type Domain = "process" | "optimization";

/** A project as `GET /v1/projects` lists it. */
export interface Project {
  id: string;
  name: string | null;
  created: string | null;
  layout_version: number | null;
  model_revision: number | null;
  path: string;
  available: boolean;
}

/** `POST /v1/projects`. */
export interface CreateProject {
  name: string;
  domain?: Domain;
  template?: string;
  path?: string;
}

/** A template's `template.json` (spec 4 "Template package"; AKS-122). */
export interface Template {
  id: string;
  title: string;
  summary?: string;
  audience?: string;
  minutes?: number;
  concepts?: string[];
  /** The experiment the lesson runs; `null` for an `optimization` model. */
  experiment?: string | null;
  /** The exercise's change, as spec 3 model edits. */
  exercise?: { edits: Edit[] };
  [key: string]: unknown;
}

/** `GET /v1/templates/{tid}`: `template.json`, `lesson.md`'s text and `expected.json`. */
export interface TemplateBody {
  template: Template;
  lesson: string;
  expected: unknown[];
}

export type Theme = "system" | "light" | "dark";
export type TextSize = 100 | 125 | 150 | 175 | 200;
export type Motion = "system" | "full" | "reduced" | "off";

/** The interface's preferences in `settings.json` (spec 3 `GET /v1/settings`). */
export interface InterfacePreferences {
  first_start_seen: boolean;
  ask_before_deleting: boolean;
  undo_steps: number | null;
  theme: Theme;
  text_size: TextSize;
  motion: Motion;
  colour_blind_charts: boolean;
}

export interface FindingThresholds {
  bottleneck_utilization: number;
  idle_utilization: number;
  relative_half_width: number;
  min_time_s: number;
  min_rate_per_s: number;
}

/** `settings` of `GET /v1/settings`. */
export interface Settings {
  tier: TierName;
  max_concurrent_runs: number;
  run_time_limit_s: number;
  run_memory_limit_bytes: number | null;
  finding_thresholds: FindingThresholds;
  interface: InterfacePreferences;
}

/** `GET /v1/settings` and `PUT /v1/settings`. */
export interface SettingsBody {
  settings: Settings;
  issues: Issue[];
}

/** A `PUT /v1/settings` body: a key given replaces the stored one whole; `null` removes it. */
export type SettingsChange = {
  [K in keyof Settings]?: K extends "finding_thresholds" | "interface"
    ? Partial<Settings[K]> | null
    : Settings[K] | null;
};

/** A component of a `process` model (spec 1 "Components and ports"). */
export interface Component {
  id: string;
  type: string;
  params: Record<string, unknown>;
  label?: string;
  ui?: Record<string, unknown>;
}

/** A connection: `<id>.<port>` to `<id>.<port>`. */
export interface Connection {
  from: string;
  to: string;
}

export type ParameterType = "integer" | "number" | "quantity";

/** A parameter (spec 1 "Parameters"). Values are as the file holds them. */
export interface Parameter {
  value: unknown;
  type: ParameterType | string;
  min?: unknown;
  max?: unknown;
  description?: string;
}

export interface Experiment {
  id: string;
  [key: string]: unknown;
}

/**
 * A model file (spec 1 "Model file"). Only what the interface reads is typed; every other
 * key is kept as the file holds it, so a whole-model write (undo, redo) loses nothing.
 */
export interface Model {
  domain?: string;
  parameters?: Record<string, Parameter>;
  components?: Component[];
  connections?: Connection[];
  experiments?: Experiment[];
  [key: string]: unknown;
}

/** A variable of an `optimization` model (spec 2 "Mathematical optimization"); as the file holds it. */
export interface Variable {
  id: string;
  type: unknown;
  lower?: unknown;
  upper?: unknown;
}

/** The objective of an `optimization` model. */
export interface LinearObjective {
  sense: unknown;
  linear: Record<string, unknown>;
}

/** A constraint of an `optimization` model. */
export interface LinearConstraint {
  id: string;
  linear: Record<string, unknown>;
  op: unknown;
  rhs: unknown;
}

/** `GET /v1/projects/{pid}/model`. */
export interface ModelBody {
  model: Model;
  revision: number;
}

/** `PUT /v1/projects/{pid}/model` and `POST .../model/edits`. */
export interface ModelWriteBody {
  model: Model;
  revision: number;
  issues: Issue[];
}

/** `POST /v1/projects/{pid}/validate`. */
export interface ValidateBody {
  revision: number;
  issues: Issue[];
}

/** One edit of spec 3 "Model edits"; `edit` names its kind. */
export type Edit =
  | {
      edit: "add_component";
      id: string;
      type: string;
      params: Record<string, unknown>;
      ui?: Record<string, unknown>;
    }
  | { edit: "remove_component"; id: string }
  | { edit: "rename_component"; id: string; new_id: string }
  | { edit: "set_setting"; id: string; path: string; value: unknown }
  | { edit: "connect"; from: string; to: string }
  | { edit: "disconnect"; from: string }
  | {
      edit: "set_parameter";
      id: string;
      value?: unknown;
      type?: unknown;
      min?: unknown;
      max?: unknown;
    }
  | { edit: "remove_parameter"; id: string }
  | { edit: "set_ui"; id: string; ui: Record<string, unknown> }
  | { edit: "set_label"; id: string; label: string | null }
  | { edit: "set_experiment"; id: string; [field: string]: unknown }
  | { edit: "remove_experiment"; id: string }
  | { edit: "set_scenario"; experiment_id: string; id: string; set: Record<string, unknown> }
  | { edit: "remove_scenario"; experiment_id: string; id: string }
  | { edit: "set_path"; path: string; value: unknown }
  | { edit: "remove_path"; path: string };

/** One setting of a component type, as `GET /v1/schema/components/{type}` describes it. */
export interface SettingDescription {
  name: string;
  kind: "number" | "quantity" | "distribution" | "identifier" | "object" | string;
  required: boolean;
  dimension?: string;
  integer?: boolean;
  many?: boolean;
  choices?: string[];
  refers_to?: string[];
  fields?: SettingDescription[];
  keyed_by?: string;
  values?: SettingDescription;
  required_when?: [string, string];
  minimum?: number;
  exclusive_minimum?: boolean;
  min_items?: number;
  default?: unknown;
}

/** `GET /v1/schema/components/{type}`. */
export interface ComponentType {
  type: string;
  domain: string;
  engine: string;
  description: string;
  inputs: string[];
  outputs: string[];
  outputs_from: string | null;
  settings: SettingDescription[];
  metrics: string[];
}

/** `GET /v1/schema`: the composed schema; the interface reads its component types. */
export interface SchemaBody {
  "x-component-types": Record<string, ComponentType>;
  [key: string]: unknown;
}

/** The first and every later event of `GET /v1/projects/{pid}/events`. */
export type ProjectEvent =
  | { type: "model"; revision: number; client: string | null }
  | { type: "run"; run_id: string; state: string };

/** A column of an imported file (spec 3 `GET .../data`). */
export interface DataColumn {
  name: string;
  type: "number" | "text" | "empty";
  /** A Phase 1 time unit, or `null` for plain numbers. */
  unit: string | null;
  /** A `number` column's largest absolute value; `null` for another type. */
  largest: number | null;
}

/** An imported file as `GET .../data` lists it. */
export interface DataFile {
  name: string;
  format: "csv" | "xlsx";
  sheet: string | null;
  size: number;
  sha256: string;
  imported: string;
  rows: number;
  columns: DataColumn[];
}

/** `POST .../data`: the file as listed, with its first 10 records. */
export interface ImportedFile extends DataFile {
  preview: (number | string | null)[][];
}

/** One candidate of a fit: a spec 1 distribution object and its Kolmogorov–Smirnov score. */
export interface FitCandidate {
  distribution: Record<string, unknown>;
  score: number;
}

/** `POST .../data/{file}/fit`. */
export interface FitBody {
  file: string;
  column: string;
  unit: string | null;
  values: number;
  score: string;
  candidates: FitCandidate[];
  /** The column's values counted in bins of equal width, in its unit (AKS-120). */
  histogram: { edges: number[]; counts: number[] };
}

/** A run's state (spec 1 "Job states"). */
export type RunState = "queued" | "running" | "done" | "failed" | "cancelled";

/** The run states that are final. */
export const FINAL_STATES: readonly RunState[] = ["done", "failed", "cancelled"];

/** A run as the run endpoints show it (spec 3; `engine` from AKS-138). */
export interface Run {
  run_id: string;
  project_id: string | null;
  experiment_id: string | null;
  engine: { name: string; version: string | null } | null;
  state: RunState;
  fraction: number;
  message: string;
  created: string;
  started: string | null;
  ended: string | null;
  error: Issue | null;
}

/** `POST /v1/projects/{pid}/runs`. */
export interface StartedRun {
  run_id: string;
}

/** An event of `GET /v1/runs/{rid}/events` (spec 3 "Progress events"). */
export type RunEvent =
  | { type: "state"; state: RunState }
  | { type: "progress"; fraction: number; message: string }
  | { type: "metrics"; scenario: string; values: Record<string, number> };

/** A metric's estimate in `summary.json` (spec 1), in SI units. */
export interface Estimate {
  mean: number | null;
  half_width: number | null;
  unit: string;
  n: number;
}

/** A finding of spec 4 "Finding rules". */
export interface Finding {
  rule: string;
  severity: "info" | "warning";
  component: string | null;
  scenario: string | null;
  text: string;
  evidence: Record<string, unknown>;
}

/**
 * `summary.json` (spec 1 "Run folder and results"; spec 2 for `search` and an optimization's
 * solution). Read defensively: what the interface does not find, it does not show.
 */
export type Summary = Record<string, unknown>;

/** `GET /v1/runs/{rid}/summary`. */
export interface SummaryBody {
  summary: Summary;
  findings: Finding[];
  issues: Issue[];
}

/** One row of `GET /v1/runs/{rid}/tables/{name}?format=json`. */
export type TableRow = Record<string, unknown>;

/** An installed adapter as `GET /v1/engines` lists it. */
export interface Engine {
  name: string;
  version: string;
  domains: string[];
  component_types: string[];
  hardware: string[];
  parallel_modes: string[];
  licence: string;
  invocation: string;
}
