import { describe, expect, it } from "vitest";
import type { Component, Issue, Model } from "../api/types";
import componentTypes from "../test/component-types.json";
import { coffeeShop, emptyModel } from "../test/fakeModel";
import {
  categoryOf,
  countsText,
  freePlace,
  isRequired,
  issueComponent,
  issueSetting,
  moveEdit,
  nextId,
  paramOf,
  pointer,
  portsOf,
  positionOf,
  readNumber,
  references,
  settingEdit,
  shown,
  splitEnd,
  splitQuantity,
  typeLine,
  valueAt,
  withoutParameterField,
  withoutSetting,
  words,
} from "./model";

const types = componentTypes as Record<string, import("../api/types").ComponentType>;

function withComponents(...items: Component[]): Model {
  return { ...emptyModel(), components: items };
}

function issue(path: string, component: string | null = null): Issue {
  return { code: "E122", severity: "error", component, path, message: "m", hint: null };
}

describe("reading a model for the canvas", () => {
  it("groups block types as the design system does", () => {
    expect(["source", "server", "resource_pool", "mystery"].map(categoryOf)).toEqual([
      "flow",
      "work",
      "resource",
      "other",
    ]);
  });

  it("generates the next id from the highest number of that form, never reusing one", () => {
    expect(nextId(emptyModel(), "server")).toBe("server_1");
    const model = withComponents(
      { id: "server_1", type: "server", params: {} },
      { id: "server_7", type: "queue", params: {} },
      { id: "server_x", type: "server", params: {} },
      { id: "till", type: "server", params: {} },
    );
    expect(nextId(model, "server")).toBe("server_8");
    expect(nextId(model, "sink")).toBe("sink_1");
  });

  it("places blocks by their ui, else in a grid by order", () => {
    expect(positionOf({ id: "a", type: "sink", params: {}, ui: { x: 8, y: 16 } }, 0)).toEqual({
      x: 8,
      y: 16,
    });
    expect(positionOf({ id: "a", type: "sink", params: {} }, 5)).toEqual({ x: 264, y: 160 });
    expect(positionOf({ id: "a", type: "sink", params: {}, ui: { x: "1" } }, 0)).toEqual({
      x: 40,
      y: 40,
    });
  });

  it("moves a block keeping the other keys of its ui", () => {
    expect(
      moveEdit({ id: "a", type: "sink", params: {}, ui: { x: 0, y: 0, note: 1 } }, { x: 8, y: 16 }),
    ).toEqual({ edit: "set_ui", id: "a", ui: { x: 8, y: 16, note: 1 } });
  });

  it("finds a free place for a block added from the keyboard", () => {
    const model = withComponents({ id: "a", type: "sink", params: {}, ui: { x: 0, y: 0 } });
    expect(freePlace(model, { x: 88, y: 32 })).toEqual({ x: 0, y: 72 });
    expect(freePlace(emptyModel(), { x: 88, y: 32 })).toEqual({ x: 0, y: 0 });
  });

  it("splits a connection end at its first dot", () => {
    expect(splitEnd("till.in")).toEqual(["till", "in"]);
    expect(splitEnd("a.b.c")).toEqual(["a", "b.c"]);
    expect(splitEnd("till")).toBeNull();
    expect(splitEnd(".in")).toBeNull();
    expect(splitEnd("till.")).toBeNull();
  });

  it("gives a block its type's ports, a branch its routes", () => {
    const branch = { id: "b", type: "branch", params: { routes: ["left", 3, "right"] } };
    expect(portsOf(branch, types.branch)).toEqual({ inputs: ["in"], outputs: ["left", "right"] });
    expect(portsOf({ ...branch, params: {} }, types.branch).outputs).toEqual([]);
    expect(portsOf({ id: "s", type: "sink", params: {} }, types.sink)).toEqual({
      inputs: ["in"],
      outputs: [],
    });
    expect(portsOf({ id: "s", type: "x", params: {} }, undefined)).toEqual({
      inputs: [],
      outputs: [],
    });
  });

  it("finds the reference lines of pools, schedules and failures whose blocks exist", () => {
    const model = withComponents(
      { id: "staff", type: "resource_pool", params: { capacity: 2 } },
      { id: "pick", type: "server", params: { pool: "staff" } },
      { id: "lost", type: "server", params: { pool: "nobody" } },
      { id: "shifts", type: "schedule", params: { target: "staff" } },
      { id: "breaks", type: "failure", params: { target: "pick" } },
      { id: "odd", type: "queue", params: { pool: "staff", target: "pick" } },
    );
    expect(references(model)).toEqual([
      { from: "staff", to: "pick", kind: "pool" },
      { from: "shifts", to: "staff", kind: "schedule" },
      { from: "breaks", to: "pick", kind: "failure" },
    ]);
  });

  it("ties an issue to a block by its path, else by its component", () => {
    const model = coffeeShop();
    expect(issueComponent(issue("/components/1/params/service"), model)).toBe("till");
    expect(issueComponent(issue("/components/9", "ghost"), model)).toBe("ghost");
    expect(issueComponent(issue("/parameters/tills"), model)).toBeNull();
    expect(issueSetting(issue("/components/1/params/service/mean"))).toBe("/service/mean");
    expect(issueSetting(issue("/components/1"))).toBeNull();
  });

  it("counts errors and warnings in words", () => {
    const warning = { ...issue("/x"), severity: "warning" as const };
    expect(countsText([])).toBe("No problems");
    expect(countsText([issue("/a")])).toBe("1 error");
    expect(countsText([issue("/a"), issue("/b"), warning])).toBe("2 errors, 1 warning");
    expect(countsText([warning, warning])).toBe("2 warnings");
  });
});

describe("building setting edits", () => {
  const till = coffeeShop().components?.[1] as Component;

  it("writes JSON Pointers", () => {
    expect(pointer(["service", "mean"])).toBe("/service/mean");
    expect(pointer(["a/b", "c~d", 0])).toBe("/a~1b/c~0d/0");
    expect(valueAt({ a: [{ b: 1 }] }, ["a", 0, "b"])).toBe(1);
    expect(valueAt({ a: 1 }, ["a", "b"])).toBeUndefined();
  });

  it("sends set_setting where the path exists, holding the rest", () => {
    expect(settingEdit(till, ["service", "mean"], "2 min")).toEqual({
      edit: "set_setting",
      id: "till",
      path: "/service/mean",
      value: "2 min",
    });
    expect(settingEdit(till, ["queue_capacity"], 3)).toEqual({
      edit: "set_setting",
      id: "till",
      path: "/queue_capacity",
      value: 3,
    });
    expect(settingEdit({ ...till, params: {} }, ["service", "mean"], "2 min")).toEqual({
      edit: "set_setting",
      id: "till",
      path: "/service",
      value: { mean: "2 min" },
    });
    expect(settingEdit({ ...till, params: {} }, ["shifts", 0, "start"], "0 h")).toEqual({
      edit: "set_setting",
      id: "till",
      path: "/shifts",
      value: [{ start: "0 h" }],
    });
  });

  it("clears a setting or a parameter field by copying the model without it", () => {
    const model = coffeeShop();
    const cleared = withoutSetting(model, "till", ["service", "mean"]);
    expect(cleared.components?.[1]?.params.service).toEqual({ dist: "exponential" });
    expect(model.components?.[1]?.params.service).toEqual({ dist: "exponential", mean: "1.5 min" });
    const rows = withComponents({
      id: "s",
      type: "schedule",
      params: { shifts: [{ a: 1 }, { b: 2 }] },
    });
    expect(withoutSetting(rows, "s", ["shifts", 0]).components?.[0]?.params.shifts).toEqual([
      { b: 2 },
    ]);
    expect(withoutSetting(model, "ghost", ["x"])).toEqual(model);
    expect(withoutParameterField(model, "tills", "max").parameters?.tills).toEqual({
      value: 1,
      type: "integer",
      min: 1,
    });
  });

  it("reads numbers by spec 1's grammar and sends other text as typed", () => {
    expect(readNumber("2")).toBe(2);
    expect(readNumber(" -1.5e2 ")).toBe(-150);
    expect(readNumber("two")).toBe("two");
    expect(readNumber(".5")).toBe(".5");
    expect(readNumber("1e400")).toBe("1e400");
  });

  it("splits a time quantity into number and unit", () => {
    expect(splitQuantity("1.5 min")).toEqual({ number: "1.5", unit: "min" });
    expect(splitQuantity("2min")).toBeNull();
    expect(splitQuantity("2 m")).toBeNull();
    expect(splitQuantity(2)).toBeNull();
  });

  it("shows values and parameters as text", () => {
    expect(paramOf({ $param: "tills" })).toBe("tills");
    expect(paramOf({ $param: "tills", x: 1 })).toBeNull();
    expect(paramOf([1])).toBeNull();
    expect(shown({ $param: "tills" })).toBe("tills");
    expect(shown(undefined)).toBe("");
    expect(shown([1, 2])).toBe("[1,2]");
    expect(words("queue_capacity")).toBe("Queue capacity");
  });

  it("writes the type line with one key setting", () => {
    const [arrivals, till, exit] = coffeeShop().components as Component[];
    expect(typeLine(arrivals as Component)).toBe("source · every 2 min");
    expect(typeLine(till as Component)).toBe("server · capacity = tills");
    expect(typeLine(exit as Component)).toBe("sink");
    expect(typeLine({ id: "q", type: "queue", params: { capacity: 4 } })).toBe(
      "queue · capacity 4",
    );
    expect(typeLine({ id: "d", type: "delay", params: { time: { dist: "uniform" } } })).toBe(
      "delay · uniform",
    );
    expect(
      typeLine({ id: "s", type: "source", params: { interarrival: { dist: "uniform" } } }),
    ).toBe("source · uniform");
  });

  it("knows when a setting is required", () => {
    const weights = types.branch?.settings.find((item) => item.name === "weights");
    expect(weights && isRequired(weights, { rule: "probability" })).toBe(true);
    expect(weights && isRequired(weights, { rule: "shortest_queue" })).toBe(false);
  });
});
