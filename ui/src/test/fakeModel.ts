/**
 * A project's model in the fake service, for the Canvas's component tests: `GET .../model`,
 * `POST .../model/edits` (the edit kinds the Canvas sends, applied as spec 3 "Model edits"
 * says, enough for these tests; the real rules are the service's, tested in `tests/`),
 * `PUT .../model?base_revision=N`, `POST .../validate` (issues from a function the test
 * gives) and the schema routes, from `component-types.json`, which
 * `tests/test_ui_fixtures.py` keeps equal to the service's own.
 */
import type { Component, Edit, Issue, Model, Parameter } from "../api/types";
import { hasOwn, own, setOwn } from "../canvas/own";
import componentTypes from "./component-types.json";
import { errorBody, type FakeService } from "./fakes";

export const PID = "p1";

export function emptyModel(): Model {
  return {
    format_version: "0.1",
    meta: { name: "Shop" },
    domain: "process",
    parameters: {},
    components: [],
    connections: [],
    experiments: [{ id: "base", length: "8 h", warmup: "0 s", replications: 30 }],
    run: { target: "local", fidelity: "standard" },
  };
}

export function coffeeShop(): Model {
  return {
    ...emptyModel(),
    parameters: { tills: { value: 1, type: "integer", min: 1, max: 5 } },
    components: [
      {
        id: "arrivals",
        type: "source",
        params: { interarrival: { dist: "exponential", mean: "2 min" } },
        ui: { x: 0, y: 0 },
      },
      {
        id: "till",
        type: "server",
        params: {
          capacity: { $param: "tills" },
          service: { dist: "exponential", mean: "1.5 min" },
        },
        ui: { x: 240, y: 0 },
      },
      { id: "exit", type: "sink", params: {}, ui: { x: 480, y: 0 } },
    ],
    connections: [
      { from: "arrivals.out", to: "till.in" },
      { from: "till.out", to: "exit.in" },
    ],
  };
}

function rejected(index: number, message: string) {
  return {
    status: 400,
    body: errorBody("E180", message, [
      {
        code: "E180",
        severity: "error",
        component: null,
        path: `/edits/${index}`,
        message,
        hint: null,
      },
    ]),
  };
}

function tokens(path: string): string[] {
  return path
    .split("/")
    .slice(1)
    .map((part) => part.replace(/~1/g, "/").replace(/~0/g, "~"));
}

function apply(model: Model, edit: Edit): string | null {
  model.components ??= [];
  model.connections ??= [];
  const all = model.components;
  const links = model.connections;
  const find = (id: string) => all.find((item) => item.id === id);
  switch (edit.edit) {
    case "add_component": {
      if (find(edit.id)) return `A component '${edit.id}' already exists.`;
      const made: Component = { id: edit.id, type: edit.type, params: edit.params };
      if (edit.ui) made.ui = edit.ui;
      all.push(made);
      return null;
    }
    case "remove_component": {
      if (!find(edit.id)) return `There is no component '${edit.id}'.`;
      model.components = all.filter((item) => item.id !== edit.id);
      model.connections = links.filter(
        (item) => !item.from.startsWith(`${edit.id}.`) && !item.to.startsWith(`${edit.id}.`),
      );
      return null;
    }
    case "rename_component": {
      const component = find(edit.id);
      if (!component) return `There is no component '${edit.id}'.`;
      if (find(edit.new_id)) return `A component '${edit.new_id}' already exists.`;
      component.id = edit.new_id;
      for (const link of links) {
        if (link.from.startsWith(`${edit.id}.`))
          link.from = edit.new_id + link.from.slice(edit.id.length);
        if (link.to.startsWith(`${edit.id}.`))
          link.to = edit.new_id + link.to.slice(edit.id.length);
      }
      for (const other of all) {
        for (const key of ["pool", "target"]) {
          if (other.params[key] === edit.id) other.params[key] = edit.new_id;
        }
      }
      return null;
    }
    case "set_setting": {
      const component = find(edit.id);
      if (!component) return `There is no component '${edit.id}'.`;
      const parts = tokens(edit.path);
      let here: Record<string, unknown> | unknown[] = component.params;
      for (const part of parts.slice(0, -1)) {
        const next: unknown = Array.isArray(here) ? here[Number(part)] : own(here, part);
        if (typeof next !== "object" || next === null) return `No '${part}' in '${edit.path}'.`;
        here = next as Record<string, unknown>;
      }
      const last = parts.at(-1) ?? "";
      if (Array.isArray(here)) {
        if (last === "-" || Number(last) === here.length) here.push(edit.value);
        else here[Number(last)] = edit.value;
      } else setOwn(here, last, edit.value);
      return null;
    }
    case "connect": {
      // A connection from the same port is replaced in place; otherwise one is added.
      if (links.some((item) => item.from === edit.from)) {
        model.connections = links.map((item) =>
          item.from === edit.from ? { from: edit.from, to: edit.to } : item,
        );
      } else links.push({ from: edit.from, to: edit.to });
      return null;
    }
    case "disconnect":
      model.connections = links.filter((item) => item.from !== edit.from);
      return null;
    case "set_parameter": {
      model.parameters ??= {};
      const parameters = model.parameters;
      const { edit: _kind, id, ...fields } = edit;
      if (!hasOwn(parameters, id) && (fields.value === undefined || fields.type === undefined)) {
        return `A new parameter '${id}' needs 'value' and 'type'.`;
      }
      setOwn(parameters, id, {
        ...(own<Parameter>(parameters, id) ?? { value: null, type: "number" }),
        ...fields,
      });
      return null;
    }
    case "remove_parameter": {
      if (!hasOwn(model.parameters, edit.id)) return `There is no parameter '${edit.id}'.`;
      if (JSON.stringify(model.components).includes(`{"$param":"${edit.id}"}`)) {
        return `Parameter '${edit.id}' is still used.`;
      }
      if (model.parameters) delete model.parameters[edit.id];
      return null;
    }
    case "set_ui": {
      const component = find(edit.id);
      if (!component) return `There is no component '${edit.id}'.`;
      component.ui = edit.ui;
      return null;
    }
    case "set_label": {
      const component = find(edit.id);
      if (!component) return `There is no component '${edit.id}'.`;
      if (edit.label === null) delete component.label;
      else component.label = edit.label;
      return null;
    }
    case "set_experiment": {
      model.experiments ??= [];
      const { edit: _kind, id, ...fields } = edit;
      let found = model.experiments.find((item) => item.id === id);
      if (found === undefined) {
        found = { id, length: "8 h", warmup: "0 s", replications: 30 };
        model.experiments.push(found);
      }
      Object.assign(found, structuredClone(fields));
      return null;
    }
    case "remove_experiment": {
      const found = model.experiments?.find((item) => item.id === edit.id);
      if (found === undefined) return `There is no experiment '${edit.id}'.`;
      model.experiments = model.experiments?.filter((item) => item !== found) ?? [];
      return null;
    }
    case "set_scenario": {
      const experiment = model.experiments?.find((item) => item.id === edit.experiment_id);
      if (experiment === undefined) return `There is no experiment '${edit.experiment_id}'.`;
      const unknown = Object.keys(edit.set).find((name) => !hasOwn(model.parameters, name));
      if (unknown !== undefined) return `'${unknown}' is not a parameter of the model.`;
      experiment.scenarios ??= [];
      const scenarios = experiment.scenarios as { id: string; set: unknown }[];
      const found = scenarios.find((item) => item.id === edit.id);
      if (found === undefined) scenarios.push({ id: edit.id, set: structuredClone(edit.set) });
      else found.set = structuredClone(edit.set);
      return null;
    }
    case "remove_scenario": {
      const experiment = model.experiments?.find((item) => item.id === edit.experiment_id);
      if (experiment === undefined) return `There is no experiment '${edit.experiment_id}'.`;
      const scenarios = (experiment.scenarios ?? []) as { id: string }[];
      if (!scenarios.some((item) => item.id === edit.id)) {
        return `The experiment '${edit.experiment_id}' has no scenario '${edit.id}'.`;
      }
      experiment.scenarios = scenarios.filter((item) => item.id !== edit.id);
      return null;
    }
    case "set_path":
    case "remove_path":
      return applyPath(model, edit);
  }
}

/** `set_path` and `remove_path` on the keys spec 3 lets them reach. */
function applyPath(
  model: Model,
  edit: { edit: "set_path"; path: string; value: unknown } | { edit: "remove_path"; path: string },
): string | null {
  const parts = tokens(edit.path);
  const head = parts[0] ?? "";
  const reached =
    ["meta", "run", "objectives", "constraints"].includes(head) ||
    (["variables", "objective"].includes(head) && model.domain === "optimization") ||
    (head === "experiments" && /^(0|[1-9][0-9]*)$/.test(parts[1] ?? "") && parts[2] === "search");
  if (!reached) return `The path '${edit.path}' is not one set_path and remove_path may change.`;
  let here: unknown = model;
  for (const part of parts.slice(0, -1)) {
    here = Array.isArray(here) ? here[Number(part)] : own(here, part);
    if (typeof here !== "object" || here === null) return `No '${part}' in '${edit.path}'.`;
  }
  const last = parts.at(-1) ?? "";
  if (Array.isArray(here)) {
    const index = last === "-" ? here.length : Number(last);
    if (edit.edit === "remove_path") {
      if (index >= here.length) return `Nothing at '${edit.path}'.`;
      here.splice(index, 1);
    } else if (index === here.length) here.push(edit.value);
    else here[index] = edit.value;
    return null;
  }
  const record = here as Record<string, unknown>;
  if (edit.edit === "remove_path") {
    if (!hasOwn(record, last)) return `Nothing at '${edit.path}'.`;
    delete record[last];
  } else setOwn(record, last, edit.value);
  return null;
}

export interface ModelServiceOptions {
  pid?: string;
  model?: Model;
  revision?: number;
  /** The issues `POST .../validate` reports for a model. */
  validate?: (model: Model) => Issue[];
}

/** The fake project's model; `model` and `revision` are what the service holds. */
export class ModelService {
  model: Model;
  revision: number;
  validateIssues: (model: Model) => Issue[];
  /** When set, writes answer nothing (a network failure) until it is cleared. */
  unreachable = false;

  constructor(
    readonly fake: FakeService,
    options: ModelServiceOptions = {},
  ) {
    this.model = structuredClone(options.model ?? emptyModel());
    this.revision = options.revision ?? 0;
    this.validateIssues = options.validate ?? (() => []);
    const base = `/v1/projects/${options.pid ?? PID}`;
    fake
      .answer("GET /v1/schema", { "x-component-types": componentTypes })
      .on(`GET ${base}/model`, () => ({
        status: 200,
        body: { model: structuredClone(this.model), revision: this.revision },
      }))
      .on(`POST ${base}/model/edits`, (body) =>
        this.edits(body as { edits: Edit[]; base_revision?: number }),
      )
      .on(`PUT ${base}/model`, (body, url) => this.put(body as Model, url))
      .on(`POST ${base}/validate`, () => ({
        status: 200,
        body: { revision: this.revision, issues: this.validateIssues(this.model) },
      }));
    for (const [type, description] of Object.entries(componentTypes)) {
      fake.answer(`GET /v1/schema/components/${type}`, description);
    }
  }

  private stale(base: number | undefined) {
    if (base === undefined || base === this.revision) return null;
    return {
      status: 409,
      body: {
        error: { code: "E181", message: `The model has changed since revision ${base}.` },
        issues: [],
        model: this.model,
        revision: this.revision,
      },
    };
  }

  private edits(body: { edits: Edit[]; base_revision?: number }) {
    if (this.unreachable) return "unreachable" as const;
    const stale = this.stale(body.base_revision);
    if (stale) return stale;
    const next = structuredClone(this.model);
    for (const [index, edit] of body.edits.entries()) {
      const problem = apply(next, edit);
      if (problem !== null) return rejected(index, problem);
    }
    return this.saved(next);
  }

  private put(model: Model, url: URL) {
    if (this.unreachable) return "unreachable" as const;
    const stale = this.stale(Number(url.searchParams.get("base_revision")));
    if (stale) return stale;
    return this.saved(structuredClone(model));
  }

  private saved(model: Model) {
    this.model = model;
    this.revision += 1;
    return {
      status: 200,
      body: { model: structuredClone(model), revision: this.revision, issues: [] },
    };
  }

  /** Another client's write: the model changes and the revision moves on. */
  outsideWrite(change: (model: Model) => void): void {
    change(this.model);
    this.revision += 1;
  }

  component(id: string): Component | undefined {
    return this.model.components?.find((item) => item.id === id);
  }
}
