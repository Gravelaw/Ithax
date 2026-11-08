/**
 * The edits the Table view of an optimization model sends (spec 3 "Canvas behaviour",
 * Optimization models; "Model edits", Pointers).
 */
import { describe, expect, it } from "vitest";
import type { Model } from "../api/types";
import {
  addDecision,
  addLimit,
  coefficientEdits,
  constraintsOf,
  diagramLayout,
  fieldEdits,
  goalSentence,
  limitText,
  removeDecision,
  removeLimit,
  renameDecision,
  variablesOf,
} from "./plan";

function mix(): Model {
  return {
    format_version: "0.1",
    meta: { name: "Product mix" },
    domain: "optimization",
    variables: [
      { id: "chairs", type: "continuous", lower: 0 },
      { id: "tables", type: "continuous", lower: 0 },
    ],
    objective: { sense: "maximize", linear: { chairs: 45, tables: 80 } },
    constraints: [
      { id: "wood", linear: { chairs: 5, tables: 20 }, op: "<=", rhs: 400 },
      { id: "labour", linear: { chairs: 10, tables: 15 }, op: "<=", rhs: 450 },
    ],
    run: { target: "local", fidelity: "standard" },
  };
}

function empty(): Model {
  return {
    format_version: "0.1",
    meta: { name: "Plan" },
    domain: "optimization",
    variables: [],
    objective: { sense: "maximize", linear: {} },
    constraints: [],
  };
}

describe("reading the plan", () => {
  it("lists the decisions and limits with their places, skipping what is not an object", () => {
    const model = mix();
    (model.variables as unknown[]).push(3);
    expect(variablesOf(model).map((row) => [row.index, row.item.id])).toEqual([
      [0, "chairs"],
      [1, "tables"],
    ]);
    expect(constraintsOf(model).map((row) => row.item.id)).toEqual(["wood", "labour"]);
    expect(variablesOf({ domain: "optimization" })).toEqual([]);
  });

  it("reads the goal and a limit as sentences", () => {
    expect(goalSentence(mix())).toBe("Maximize 45 × chairs + 80 × tables");
    expect(goalSentence(empty())).toBe("Maximize: no decision has a coefficient yet");
    expect(limitText({ id: "wood", linear: { chairs: 5, tables: -2 }, op: "<=", rhs: 400 })).toBe(
      "5 × chairs − 2 × tables ≤ 400",
    );
    expect(limitText({ id: "x", linear: {}, op: "==", rhs: 0 })).toBe("0 = 0");
  });
});

describe("the edits of each change", () => {
  it("adds a decision and a limit with the next free names", () => {
    expect(addDecision(mix())).toEqual([
      { edit: "set_path", path: "/variables/-", value: { id: "decision_1", type: "continuous" } },
    ]);
    const model = mix();
    (model.variables as unknown[]).push({ id: "decision_4", type: "integer" });
    expect(addDecision(model)[0]).toMatchObject({ value: { id: "decision_5" } });
    expect(addLimit(empty())).toEqual([
      {
        edit: "set_path",
        path: "/constraints/-",
        value: { id: "limit_1", linear: {}, op: "<=", rhs: 0 },
      },
    ]);
    // A list that is missing (or not a list) is written whole.
    expect(addLimit({ domain: "optimization" })).toEqual([
      {
        edit: "set_path",
        path: "/constraints",
        value: [{ id: "limit_1", linear: {}, op: "<=", rhs: 0 }],
      },
    ]);
  });

  it("sets a field as a number when it reads as one, and removes an emptied optional one", () => {
    const model = mix();
    expect(fieldEdits(model, "/variables/0/upper", "12", true)).toEqual([
      { edit: "set_path", path: "/variables/0/upper", value: 12 },
    ]);
    expect(fieldEdits(model, "/variables/0/lower", " ", true)).toEqual([
      { edit: "remove_path", path: "/variables/0/lower" },
    ]);
    expect(fieldEdits(model, "/variables/0/upper", "", true)).toBeNull();
    expect(fieldEdits(model, "/constraints/0/rhs", "4x", false)).toEqual([
      { edit: "set_path", path: "/constraints/0/rhs", value: "4x" },
    ]);
    expect(fieldEdits(model, "/constraints/0/rhs", "400", false)).toBeNull();
  });

  it("sets and removes a coefficient, creating the coefficients when they are missing", () => {
    const model = mix();
    expect(coefficientEdits(model, "/objective", "chairs", "50")).toEqual([
      { edit: "set_path", path: "/objective/linear/chairs", value: 50 },
    ]);
    expect(coefficientEdits(model, "/constraints/1", "tables", "")).toEqual([
      { edit: "remove_path", path: "/constraints/1/linear/tables" },
    ]);
    const broken = mix();
    (broken.constraints as { linear: unknown }[])[0] = {
      id: "wood",
      linear: 3,
      op: "<=",
      rhs: 1,
    } as never;
    expect(coefficientEdits(broken, "/constraints/0", "chairs", "2")).toEqual([
      { edit: "set_path", path: "/constraints/0/linear", value: { chairs: 2 } },
    ]);
  });

  it("renames a decision with its coefficients, keeping their order", () => {
    expect(renameDecision(mix(), 0, "seats")).toEqual([
      { edit: "set_path", path: "/variables/0/id", value: "seats" },
      { edit: "set_path", path: "/objective/linear", value: { seats: 45, tables: 80 } },
      { edit: "set_path", path: "/constraints/0/linear", value: { seats: 5, tables: 20 } },
      { edit: "set_path", path: "/constraints/1/linear", value: { seats: 10, tables: 15 } },
    ]);
    expect(
      Object.keys(((renameDecision(mix(), 0, "seats") ?? [])[1] as { value: object }).value),
    ).toEqual(["seats", "tables"]);
    // A name another decision has: the coefficients stay; the service reports the duplicate.
    expect(renameDecision(mix(), 0, "tables")).toEqual([
      { edit: "set_path", path: "/variables/0/id", value: "tables" },
    ]);
    expect(renameDecision(mix(), 0, "chairs")).toBeNull();
  });

  it("removes a decision with its coefficients, and a limit", () => {
    expect(removeDecision(mix(), 1)).toEqual([
      { edit: "remove_path", path: "/variables/1" },
      { edit: "remove_path", path: "/objective/linear/tables" },
      { edit: "remove_path", path: "/constraints/0/linear/tables" },
      { edit: "remove_path", path: "/constraints/1/linear/tables" },
    ]);
    expect(removeLimit(mix(), 0)).toEqual([{ edit: "remove_path", path: "/constraints/0" }]);
  });
});

describe("the Diagram view's layout", () => {
  it("puts decisions left, the goal and limits right, and a line per coefficient", () => {
    const layout = diagramLayout(mix());
    expect(layout.decisions.map((card) => [card.id, card.x])).toEqual([
      ["chairs", 0],
      ["tables", 0],
    ]);
    expect(layout.targets.map((card) => card.key)).toEqual(["goal", "limit:0", "limit:1"]);
    expect(layout.lines.map((line) => `${line.from}>${line.to}:${line.label}`)).toEqual([
      "chairs>goal:45",
      "tables>goal:80",
      "chairs>limit:0:5",
      "tables>limit:0:20",
      "chairs>limit:1:10",
      "tables>limit:1:15",
    ]);
    expect(layout.height).toBeGreaterThan(0);
  });
});
