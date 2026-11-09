/**
 * The comparison behind the review of an outside change (spec 3 "Canvas behaviour",
 * External edits; `docs/design/canvas-interactions.md` "Reviewing an outside change"):
 * the baseline against the model shown, item by item by stable id.
 */
import { describe, expect, it } from "vitest";
import type { Model } from "../api/types";
import { coffeeShop } from "../test/fakeModel";
import {
  absorb,
  adopt,
  type Change,
  changeKind,
  changesBetween,
  describeChange,
  fieldChanges,
  putItem,
  restore,
  sameValue,
} from "./review";

function edited(change: (model: Model) => void, from: Model = coffeeShop()): Model {
  const copy = structuredClone(from);
  change(copy);
  return copy;
}

const till = (model: Model) => model.components?.find((item) => item.id === "till");

/** Every change restored one by one: the baseline back, item by item. */
function rejectedAll(model: Model, changes: Change[]): Model {
  return changes.reduce(restore, model);
}

describe("sameValue", () => {
  it("ignores key order but not list order, and tells absent from null", () => {
    expect(sameValue({ a: 1, b: [1, 2] }, { b: [1, 2], a: 1 })).toBe(true);
    expect(sameValue([1, 2], [2, 1])).toBe(false);
    expect(sameValue({ a: undefined }, {})).toBe(false);
    expect(sameValue(undefined, null)).toBe(false);
    expect(sameValue(1, "1")).toBe(false);
  });
});

describe("changesBetween compares item by item", () => {
  it("finds nothing between equal models, whatever the key or list order", () => {
    const after = edited((model) => {
      model.components?.reverse();
      model.connections?.reverse();
    });
    expect(changesBetween(coffeeShop(), after)).toEqual([]);
  });

  it("marks components, connections, parameters and experiments added, changed or removed", () => {
    const after = edited((model) => {
      const found = till(model);
      if (found) found.params.capacity = 2;
      model.components?.push({ id: "queue_1", type: "queue", params: {} });
      model.components = model.components?.filter((item) => item.id !== "exit");
      model.connections = [{ from: "arrivals.out", to: "queue_1.in" }];
      model.parameters = { staff: { value: 2, type: "integer" } };
      model.experiments?.push({ id: "long", length: "40 h" });
    });
    // In the order of the model's keys (parameters come first), then of the items.
    expect(changesBetween(coffeeShop(), after).map((item) => [item.key, changeKind(item)])).toEqual(
      [
        ["map:parameters:staff", "added"],
        ["map:parameters:tills", "removed"],
        ["list:components:till", "changed"],
        ["list:components:queue_1", "added"],
        ["list:components:exit", "removed"],
        ["list:connections:arrivals.out", "changed"],
        ["list:connections:till.out", "removed"],
        ["list:experiments:long", "added"],
      ],
    );
  });

  it("takes any other top-level key, and a list without distinct ids, as one item", () => {
    const after = edited((model) => {
      model.meta = { name: "Cafe" };
      model.components?.push({ id: "till", type: "server", params: {} });
    });
    expect(changesBetween(coffeeShop(), after).map((item) => item.key)).toEqual([
      "top:meta",
      "top:components",
    ]);
  });

  it("takes a rename as a removal and an addition", () => {
    const after = edited((model) => {
      const found = till(model);
      if (found) found.id = "counter";
    });
    expect(changesBetween(coffeeShop(), after).map((item) => [item.key, changeKind(item)])).toEqual(
      [
        ["list:components:counter", "added"],
        ["list:components:till", "removed"],
      ],
    );
  });

  it("compares an optimization model's variables, constraints and objective", () => {
    const before: Model = {
      format_version: "0.1",
      meta: { name: "Mix" },
      domain: "optimization",
      variables: [{ id: "chairs", type: "continuous", lower: 0 }],
      objective: { sense: "maximize", linear: { chairs: 45 } },
      constraints: [{ id: "wood", linear: { chairs: 5 }, op: "<=", rhs: 400 }],
    };
    const after = edited((model) => {
      (model.variables as unknown[]).push({ id: "tables", type: "continuous" });
      (model.objective as { linear: Record<string, number> }).linear.tables = 80;
      model.constraints = [];
    }, before);
    expect(changesBetween(before, after).map((item) => item.key)).toEqual([
      "list:variables:tables",
      "top:objective",
      "list:constraints:wood",
    ]);
  });
});

describe("Reject and Accept move one item", () => {
  it("restores a changed, an added and a removed component, and a removed connection", () => {
    const before = coffeeShop();
    const after = edited((model) => {
      const found = till(model);
      if (found) found.params.capacity = 2;
      model.components?.push({ id: "queue_1", type: "queue", params: {} });
      model.components = model.components?.filter((item) => item.id !== "arrivals");
      model.connections = model.connections?.filter((item) => item.from !== "arrivals.out");
    });
    const changes = changesBetween(before, after);
    // A removed item goes back to its place in its list.
    expect(rejectedAll(after, changes).components).toEqual(before.components);
    expect(changesBetween(before, rejectedAll(after, changes))).toEqual([]);
    const tillBack = restore(after, changes[0] as Change);
    expect(till(tillBack)?.params.capacity).toEqual({ $param: "tills" });
    expect(tillBack.components?.some((item) => item.id === "queue_1")).toBe(true);
  });

  it("restores a parameter, a top-level key and a removed top-level key", () => {
    const before = coffeeShop();
    const after = edited((model) => {
      delete model.parameters;
      model.meta = { name: "Cafe" };
      delete model.run;
    });
    expect(rejectedAll(after, changesBetween(before, after))).toEqual(before);
  });

  it("accepts by taking the item as shown into the baseline", () => {
    const before = coffeeShop();
    const after = edited((model) => {
      const found = till(model);
      if (found) found.params.capacity = 2;
      model.meta = { name: "Cafe" };
    });
    const [meta, tillChange] = changesBetween(before, after);
    const baseline = adopt(before, tillChange as Change);
    expect(changesBetween(baseline, after).map((item) => item.key)).toEqual([meta?.key]);
  });

  it("folds the user's own write into the baseline, so it is never marked", () => {
    const baseline = coffeeShop();
    const shown = edited((model) => {
      model.meta = { name: "Cafe" };
    });
    const mine = edited((model) => {
      const found = till(model);
      if (found) found.label = "Till";
      model.components?.push({ id: "queue_9", type: "queue", params: {} });
    }, shown);
    const folded = absorb(baseline, shown, mine);
    expect(changesBetween(folded, mine).map((item) => item.key)).toEqual(["top:meta"]);
  });
});

describe("names a model holds that Object.prototype also has (review of PR #46)", () => {
  const names = ["constructor", "__proto__", "toString", "hasOwnProperty"];

  it("marks parameters with those names added, and rejects and accepts them", () => {
    const before = coffeeShop();
    const after = structuredClone(before);
    after.parameters = JSON.parse(
      `{${names.map((name) => `"${name}": {"value": 1, "type": "integer"}`).join(",")}}`,
    );
    const changes = changesBetween(before, after);
    expect(changes.map((item) => [item.key, changeKind(item)])).toEqual([
      ...names.map((name) => [`map:parameters:${name}`, "added"]),
      ["map:parameters:tills", "removed"],
    ]);
    // Each can be rejected (structuredClone of a baseline that is not a function).
    const back = rejectedAll(after, changes);
    expect(changesBetween(before, back)).toEqual([]);
    expect(Object.getPrototypeOf(back.parameters)).toBe(Object.prototype);
    // And accepted, one by one.
    const baseline = changes.reduce(adopt, before);
    expect(changesBetween(baseline, after)).toEqual([]);
    expect(Object.keys(baseline.parameters ?? {}).sort()).toEqual([...names].sort());
  });

  it("compares coefficients with those names inside an item", () => {
    const before = JSON.parse(
      `{"domain": "optimization", "objective": {"sense": "maximize", "linear": {}}}`,
    ) as Model;
    const after = JSON.parse(
      `{"domain": "optimization", "objective": {"sense": "maximize", "linear": {"constructor": 2, "__proto__": 3}}}`,
    ) as Model;
    const [goal] = changesBetween(before, after);
    expect(fieldChanges(goal?.before, goal?.after)).toEqual([
      { path: "/linear/constructor", before: undefined, after: 2 },
      { path: "/linear/__proto__", before: undefined, after: 3 },
    ]);
    expect(restore(after, goal as Change)).toEqual(before);
  });

  it("puts an item with such a name as an own property", () => {
    const model = putItem(
      coffeeShop(),
      { kind: "map", key: "parameters", id: "__proto__" },
      {
        value: 1,
        type: "integer",
      },
    );
    expect(Object.hasOwn(model.parameters ?? {}, "__proto__")).toBe(true);
    expect(JSON.stringify(model.parameters)).toContain('"__proto__"');
  });
});

describe("words", () => {
  it("lists a changed component's fields, old and new", () => {
    const before = till(coffeeShop());
    const after = structuredClone(before);
    if (after) {
      after.params.capacity = 2;
      after.label = "Till";
    }
    expect(fieldChanges(before, after)).toEqual([
      { path: "/params/capacity", before: { $param: "tills" }, after: 2 },
      { path: "/label", before: undefined, after: "Till" },
    ]);
  });

  it("names each change in the model's words", () => {
    const after = edited((model) => {
      const found = till(model);
      if (found) found.params.capacity = 2;
      model.components?.push({ id: "queue_1", type: "queue", params: {} });
    });
    expect(
      changesBetween(coffeeShop(), after).map((item) => describeChange(item, "process")),
    ).toEqual(["Changed: block till (capacity: tills → 2)", "Added: block queue_1"]);
    const plan: Model = { domain: "optimization", variables: [], constraints: [] };
    const more = edited((model) => {
      (model.variables as unknown[]).push({ id: "chairs", type: "continuous" });
      (model.constraints as unknown[]).push({ id: "wood", linear: {}, op: "<=", rhs: 0 });
      model.objective = { sense: "minimize", linear: {} };
    }, plan);
    expect(changesBetween(plan, more).map((item) => describeChange(item, "optimization"))).toEqual([
      "Added: decision chairs",
      "Added: limit wood",
      "Added: the goal",
    ]);
    expect(describeChange(changesBetween(plan, more)[0] as Change, "constructor")).toBe(
      "Added: variables chairs",
    );
  });
});
