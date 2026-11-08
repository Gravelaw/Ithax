/**
 * The comparison behind the review of an outside change (spec 3 "Canvas behaviour",
 * External edits; `docs/design/canvas-interactions.md` "Reviewing an outside change").
 */
import { describe, expect, it } from "vitest";
import type { Model } from "../api/types";
import { coffeeShop } from "../test/fakeModel";
import {
  type Change,
  changeKind,
  changesBetween,
  describeChange,
  fieldChanges,
  isShown,
  mergeReview,
  type ReviewItem,
  renameIn,
  restore,
  restoreAll,
  sameValue,
} from "./review";

function edited(change: (model: Model) => void, from: Model = coffeeShop()): Model {
  const copy = structuredClone(from);
  change(copy);
  return copy;
}

function items(changes: Change[]): ReviewItem[] {
  return changes.map((change, index) => ({ ...change, id: index + 1, accepted: false }));
}

const till = (model: Model) => model.components?.find((item) => item.id === "till");

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
    const before = coffeeShop();
    const after = edited((model) => {
      model.components?.reverse();
      model.connections?.reverse();
    });
    expect(changesBetween(before, after)).toEqual([]);
  });

  it("marks components, connections, parameters and experiments added, changed or removed", () => {
    const before = coffeeShop();
    const after = edited((model) => {
      const found = till(model);
      if (found) found.params.capacity = 2;
      model.components?.push({ id: "queue_1", type: "queue", params: {} });
      model.components = model.components?.filter((item) => item.id !== "exit");
      model.connections = [{ from: "arrivals.out", to: "queue_1.in" }];
      model.parameters = { staff: { value: 2, type: "integer" } };
      model.experiments?.push({ id: "long", length: "40 h" });
    });
    const found = changesBetween(before, after).map((change) => [
      JSON.stringify(change.ref),
      changeKind(change),
    ]);
    // In the order of the model's keys (parameters come first), then of the items.
    expect(found).toEqual([
      ['{"kind":"map","key":"parameters","id":"staff"}', "added"],
      ['{"kind":"map","key":"parameters","id":"tills"}', "removed"],
      ['{"kind":"list","key":"components","id":"till"}', "changed"],
      ['{"kind":"list","key":"components","id":"queue_1"}', "added"],
      ['{"kind":"list","key":"components","id":"exit"}', "removed"],
      ['{"kind":"list","key":"connections","id":"arrivals.out"}', "changed"],
      ['{"kind":"list","key":"connections","id":"till.out"}', "removed"],
      ['{"kind":"list","key":"experiments","id":"long"}', "added"],
    ]);
  });

  it("takes any other top-level key as one item", () => {
    const after = edited((model) => {
      model.meta = { name: "Cafe" };
      model.run = { target: "local", fidelity: "standard", seed: 3 };
    });
    expect(changesBetween(coffeeShop(), after).map((change) => change.ref)).toEqual([
      { kind: "top", key: "meta" },
      { kind: "top", key: "run" },
    ]);
  });

  it("takes a list without distinct ids as one item", () => {
    const after = edited((model) => {
      model.components?.push({ id: "till", type: "server", params: {} });
    });
    expect(changesBetween(coffeeShop(), after).map((change) => change.ref)).toEqual([
      { kind: "top", key: "components" },
    ]);
  });

  it("gives a removed item its place in its list", () => {
    const after = edited((model) => {
      model.components = model.components?.filter((item) => item.id !== "till");
    });
    const [removed] = changesBetween(coffeeShop(), after);
    expect(removed?.index).toBe(1);
  });

  it("finds a rename as one change, the references it rewrote unmarked", () => {
    const before = coffeeShop();
    before.components?.push({
      id: "breaks",
      type: "failure",
      params: { target: "till" },
      ui: { x: 0, y: 200 },
    });
    const after = renameIn(before, "till", "counter");
    const changes = changesBetween(before, after);
    expect(changes).toHaveLength(1);
    expect(changes[0]?.ref).toEqual({ kind: "rename", was: "till", id: "counter" });
    expect(changeKind(changes[0] as Change)).toBe("renamed");
  });

  it("does not take a rename that also changed the block as a rename", () => {
    const after = renameIn(coffeeShop(), "till", "counter");
    const counter = after.components?.find((item) => item.id === "counter");
    if (counter) counter.params.capacity = 3;
    const kinds = changesBetween(coffeeShop(), after).map(changeKind);
    expect(kinds).toContain("added");
    expect(kinds).toContain("removed");
    expect(kinds).not.toContain("renamed");
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
    expect(changesBetween(before, after).map((change) => change.ref)).toEqual([
      { kind: "list", key: "variables", id: "tables" },
      { kind: "top", key: "objective" },
      { kind: "list", key: "constraints", id: "wood" },
    ]);
  });
});

describe("restore puts one item back as it was", () => {
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
    const back = changes.reduce(restore, after);
    expect(back).toEqual(before);
    expect(restoreAll(after, changes)).toEqual(before);
    // One at a time: only that item moves.
    const tillBack = restore(after, changes[0] as Change);
    expect(till(tillBack)?.params.capacity).toEqual({ $param: "tills" });
    expect(tillBack.components?.some((item) => item.id === "queue_1")).toBe(true);
  });

  it("renames back, with the references", () => {
    const before = coffeeShop();
    before.components?.push({ id: "breaks", type: "failure", params: { target: "till" } });
    const after = renameIn(before, "till", "counter");
    const [rename] = changesBetween(before, after);
    expect(restore(after, rename as Change)).toEqual(before);
  });

  it("restores the other items before the renames when rejecting all", () => {
    const before = coffeeShop();
    const renamed = renameIn(before, "till", "counter");
    renamed.connections = renamed.connections?.filter((item) => item.from !== "counter.out");
    const changes = changesBetween(before, renamed);
    expect(restoreAll(renamed, changes)).toEqual(before);
  });

  it("restores a parameter, a top-level key and a removed top-level key", () => {
    const before = coffeeShop();
    const after = edited((model) => {
      delete model.parameters;
      model.meta = { name: "Cafe" };
      delete model.run;
    });
    expect(restoreAll(after, changesBetween(before, after))).toEqual(before);
  });
});

describe("a mark is shown while the item is as the other client left it", () => {
  it("hides a mark once the item changes again, or when accepted", () => {
    const before = coffeeShop();
    const after = edited((model) => {
      const found = till(model);
      if (found) found.params.capacity = 2;
    });
    const [item] = items(changesBetween(before, after));
    expect(isShown(item as ReviewItem, after)).toBe(true);
    const edited2 = edited((model) => {
      const found = till(model);
      if (found) found.label = "Till";
    }, after);
    expect(isShown(item as ReviewItem, edited2)).toBe(false);
    expect(isShown({ ...(item as ReviewItem), accepted: true }, after)).toBe(false);
  });

  it("shows a rename only while the old id is gone and the block is as renamed", () => {
    const before = coffeeShop();
    const after = renameIn(before, "till", "counter");
    const [item] = items(changesBetween(before, after));
    expect(isShown(item as ReviewItem, after)).toBe(true);
    expect(isShown(item as ReviewItem, before)).toBe(false);
  });
});

describe("mergeReview adds a later outside change to the marks", () => {
  it("keeps an item's first before, drops one put back, and adds new ones", () => {
    const first = coffeeShop();
    const second = edited((model) => {
      const found = till(model);
      if (found) found.params.capacity = 2;
      model.meta = { name: "Cafe" };
    }, first);
    let review = mergeReview([], changesBetween(first, second), 1);
    expect(review.map((item) => item.id)).toEqual([1, 2]);
    const third = edited((model) => {
      const found = till(model);
      if (found) found.params.capacity = 3;
      model.meta = { name: "Shop" };
      model.components?.push({ id: "queue_1", type: "queue", params: {} });
    }, second);
    review = mergeReview(review, changesBetween(second, third), 3);
    expect(review.map((item) => [item.id, JSON.stringify(item.ref)])).toEqual([
      [3, '{"kind":"list","key":"components","id":"till"}'],
      [4, '{"kind":"list","key":"components","id":"queue_1"}'],
    ]);
    expect(restore(third, review[0] as Change)).toEqual(
      edited((model) => {
        model.meta = { name: "Shop" };
        model.components?.push({ id: "queue_1", type: "queue", params: {} });
      }, first),
    );
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
    const before = coffeeShop();
    const after = renameIn(
      edited((model) => {
        const found = till(model);
        if (found) found.params.capacity = 2;
        model.components?.push({ id: "queue_1", type: "queue", params: {} });
      }),
      "exit",
      "door",
    );
    expect(
      changesBetween(before, after).map((change) => describeChange(change, "process")),
    ).toEqual([
      "Changed: block till (capacity: tills → 2)",
      "Added: block queue_1",
      "Renamed: block exit → door",
    ]);
    const plan: Model = { domain: "optimization", variables: [], constraints: [] };
    const more = edited((model) => {
      (model.variables as unknown[]).push({ id: "chairs", type: "continuous" });
      (model.constraints as unknown[]).push({ id: "wood", linear: {}, op: "<=", rhs: 0 });
      model.objective = { sense: "minimize", linear: {} };
    }, plan);
    expect(
      changesBetween(plan, more).map((change) => describeChange(change, "optimization")),
    ).toEqual(["Added: decision chairs", "Added: limit wood", "Added: the goal"]);
  });
});
