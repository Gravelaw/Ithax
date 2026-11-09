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
  isIndexed,
  limitText,
  removeDecision,
  removeLimit,
  renameDecision,
  repeatsText,
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

/** The transport plan of spec 2 "Indexed problems" (format 0.2; AKS-123), as written. */
function transport(): Model {
  return {
    format_version: "0.2",
    meta: { name: "Transport plan" },
    domain: "optimization",
    sets: {
      depots: ["north", "centre", "south"],
      customers: ["city", "harbour", "park", "market"],
    },
    tables: {
      supply: { over: ["depots"], values: { north: 300, centre: 200, south: 250 } },
      demand: { over: ["customers"], values: { city: 180, harbour: 220, park: 150, market: 170 } },
      cost: {
        over: ["depots", "customers"],
        values: {
          north: { city: 4, harbour: 6, park: 9, market: 5 },
          centre: { city: 7, harbour: 3, park: 5, market: 8 },
          south: { city: 6, harbour: 8, park: 4, market: 3 },
        },
      },
    },
    variables: [{ id: "ship", type: "continuous", lower: 0, over: ["depots", "customers"] }],
    objective: {
      sense: "minimize",
      terms: [{ variable: "ship", coefficient: { $table: "cost" } }],
    },
    constraints: [
      {
        id: "supply",
        for: ["depots"],
        terms: [{ variable: "ship" }],
        op: "<=",
        rhs: { $table: "supply" },
      },
      {
        id: "demand",
        for: ["customers"],
        terms: [{ variable: "ship" }],
        op: ">=",
        rhs: { $table: "demand" },
      },
    ],
  };
}

describe("an indexed plan (AKS-123)", () => {
  it("is told apart from a flat one", () => {
    expect(isIndexed(transport())).toBe(true);
    expect(isIndexed(mix())).toBe(false);
    expect(isIndexed(empty())).toBe(false);
    expect(
      isIndexed({ ...mix(), constraints: [{ id: "a", for: [], linear: {}, op: "<=", rhs: 1 }] }),
    ).toBe(true);
  });

  it("reads its decisions, goal and limits in words", () => {
    const model = transport();
    expect(repeatsText(variablesOf(model)[0]?.item)).toBe("one for each depots × customers");
    expect(repeatsText(variablesOf(mix())[0]?.item)).toBeNull();
    expect(goalSentence(model)).toBe(
      "Minimize Σ over depots, customers cost[depots, customers] × ship[depots, customers]",
    );
    const [supply, demand] = constraintsOf(model).map((row) => row.item);
    expect(supply && limitText(supply, model)).toBe(
      "For each depots: Σ over customers ship[depots, customers] ≤ supply[depots]",
    );
    expect(demand && limitText(demand, model)).toBe(
      "For each customers: Σ over depots ship[depots, customers] ≥ demand[customers]",
    );
    // Coefficients and terms together, a number coefficient, and a flat limit unchanged.
    const both = {
      id: "x",
      linear: { extra: 2 },
      terms: [{ variable: "ship", coefficient: 3 }],
      op: "<=",
      rhs: 9,
    };
    expect(limitText(both, model)).toBe(
      "2 × extra + Σ over depots, customers 3 × ship[depots, customers] ≤ 9",
    );
    expect(limitText({ id: "w", linear: { chairs: 5 }, op: "<=", rhs: 400 }, model)).toBe(
      "5 × chairs ≤ 400",
    );
  });

  it("draws a line for each term, labelled with its table or number", () => {
    const layout = diagramLayout(transport());
    expect(layout.decisions.map((card) => card.id)).toEqual(["ship"]);
    expect(layout.lines).toEqual([
      { from: "ship", to: "goal", label: "cost" },
      { from: "ship", to: "limit:0", label: "1" },
      { from: "ship", to: "limit:1", label: "1" },
    ]);
  });

  it("renames and removes a decision with its terms", () => {
    const model = transport();
    expect(renameDecision(model, 0, "send")).toEqual([
      { edit: "set_path", path: "/variables/0/id", value: "send" },
      { edit: "set_path", path: "/objective/terms/0/variable", value: "send" },
      { edit: "set_path", path: "/constraints/0/terms/0/variable", value: "send" },
      { edit: "set_path", path: "/constraints/1/terms/0/variable", value: "send" },
    ]);
    const twice = transport();
    (twice.constraints as { terms: unknown[] }[])[0]?.terms.push(
      { variable: "other" },
      { variable: "ship" },
    );
    expect(removeDecision(twice, 0)).toEqual([
      { edit: "remove_path", path: "/variables/0" },
      { edit: "remove_path", path: "/objective/terms/0" },
      { edit: "remove_path", path: "/constraints/0/terms/2" },
      { edit: "remove_path", path: "/constraints/0/terms/0" },
      { edit: "remove_path", path: "/constraints/1/terms/0" },
    ]);
  });

  it("renames and removes the expanded names of a decision in coefficients (review of PR #53)", () => {
    const model = transport();
    (model.constraints as unknown[]).push({
      id: "closed",
      linear: { "ship[north,park]": 1, shipping: 2, "ship[x": 3 },
      op: "==",
      rhs: 0,
    });
    (model.objective as { linear?: unknown }).linear = { "ship[south,city]": 1 };
    const renamed = renameDecision(model, 0, "send");
    expect(renamed).toContainEqual({
      edit: "set_path",
      path: "/objective/linear",
      value: { "send[south,city]": 1 },
    });
    expect(renamed).toContainEqual({
      edit: "set_path",
      path: "/constraints/2/linear",
      value: { "send[north,park]": 1, shipping: 2, "ship[x": 3 },
    });
    const removed = removeDecision(model, 0);
    expect(removed).toContainEqual({
      edit: "remove_path",
      path: "/objective/linear/ship[south,city]",
    });
    expect(removed).toContainEqual({
      edit: "remove_path",
      path: "/constraints/2/linear/ship[north,park]",
    });
    expect(
      removed?.filter((edit) =>
        String((edit as { path?: string }).path).startsWith("/constraints/2/linear"),
      ),
    ).toHaveLength(1);
  });
});
