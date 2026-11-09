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

/** A template's `template.json` (spec 4 "Template package"); none before M10. */
export interface Template {
  id: string;
  title: string;
  summary?: string;
  audience?: string;
  minutes?: number;
  [key: string]: unknown;
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

/** `GET /v1/projects/{pid}/model`. */
export interface ModelBody {
  model: Record<string, unknown>;
  revision: number;
}

/** The first and every later event of `GET /v1/projects/{pid}/events`. */
export type ProjectEvent =
  | { type: "model"; revision: number; client: string | null }
  | { type: "run"; run_id: string; state: string };
