import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import type { Edit } from "../api/types";
import { coffeeShop } from "../test/fakeModel";
import { changeMade, changeRows, paragraphs, parseLesson, valueText } from "./lesson";

const TEMPLATES = join(__dirname, "..", "..", "..", "templates");

function lessonText(id: string): string {
  return readFileSync(join(TEMPLATES, id, "lesson.md"), "utf8");
}

describe("parseLesson", () => {
  it("reads the coffee shop's lesson: steps, the exercise's parts and the right choice", () => {
    const lesson = parseLesson(lessonText("coffee_shop"));
    expect(lesson?.title).toBe("Coffee shop queue");
    expect(lesson?.steps.map((step) => [step.heading, step.component])).toEqual([
      ["Customers arrive", "arrivals"],
      ["One till serves them", "till"],
      ["Customers leave", "exit"],
    ]);
    expect(lesson?.steps[0]?.text).toMatch(/^Customers arrive at random/);
    expect(lesson?.exercise.heading).toBe("Exercise: open a second till");
    expect(lesson?.exercise.component).toBe("till");
    expect(lesson?.exercise.change).toBe(
      "Set the parameter `tills` to 2, so that two customers can be served at once, and run again.",
    );
    expect(lesson?.exercise.choices).toEqual([
      { text: "The wait halves, to about 2.2 minutes.", right: false },
      { text: "The wait falls to about a quarter of a minute, far less than half.", right: true },
      { text: "The wait hardly changes: the till was only 75% busy.", right: false },
    ]);
    expect(lesson?.exercise.explanation).toMatch(/^Two tills are each busy 37.5%/);
  });

  it("reads every template's lesson, one step per '## ' section", () => {
    const ids = readdirSync(TEMPLATES).filter((id) => !id.startsWith("."));
    expect(ids).toHaveLength(10);
    for (const id of ids) {
      const text = lessonText(id);
      const lesson = parseLesson(text);
      const sections = text.split("\n").filter((line) => line.startsWith("## ")).length;
      expect(lesson, id).not.toBeNull();
      expect((lesson?.steps.length ?? 0) + 1, id).toBe(sections);
      expect(
        lesson?.exercise.choices.filter((choice) => choice.right),
        id,
      ).toHaveLength(1);
    }
  });

  it.each([
    ["no title", "## A\nComponent: `a`\n\nText.\n\n## Exercise\nComponent: `a`\n"],
    ["text before the steps", "# T\nIntro\n## A\nComponent: `a`\nText\n## Exercise: x\n"],
    ["one step", "# T\n## Exercise: x\nComponent: `a`\n### Change\nc\n"],
    ["a step without a component", "# T\n## A\nText\n## Exercise: x\nComponent: `a`\n"],
    ["an empty step", "# T\n## A\n\n## Exercise: x\nComponent: `a`\n"],
    ["a part in a step", "# T\n## A\nComponent: `a`\n### Change\nc\n## Exercise: x\n"],
    [
      "a last step that is not an exercise",
      "# T\n## A\nComponent: `a`\nt\n## B\nComponent: `a`\n### Change\nc\n### Prediction\n- [x] y\n- [ ] n\n### Explanation\ne\n",
    ],
    [
      "parts out of order",
      "# T\n## A\nComponent: `a`\nt\n## Exercise: x\nComponent: `a`\n### Prediction\n- [x] y\n- [ ] n\n### Change\nc\n### Explanation\ne\n",
    ],
    [
      "text before the parts",
      "# T\n## A\nComponent: `a`\nt\n## Exercise: x\nComponent: `a`\nIntro\n### Change\nc\n### Prediction\n- [x] y\n- [ ] n\n### Explanation\ne\n",
    ],
    [
      "a line that is not a choice",
      "# T\n## A\nComponent: `a`\nt\n## Exercise: x\nComponent: `a`\n### Change\nc\n### Prediction\n- [x] y\nmaybe\n### Explanation\ne\n",
    ],
    [
      "no right choice",
      "# T\n## A\nComponent: `a`\nt\n## Exercise: x\nComponent: `a`\n### Change\nc\n### Prediction\n- [ ] y\n- [ ] n\n### Explanation\ne\n",
    ],
    [
      "one choice",
      "# T\n## A\nComponent: `a`\nt\n## Exercise: x\nComponent: `a`\n### Change\nc\n### Prediction\n- [x] y\n### Explanation\ne\n",
    ],
    ["an exercise without a component", "# T\n## A\nComponent: `a`\nt\n## Exercise: x\nc\n"],
  ])("gives null for a lesson with %s", (_what, text) => {
    expect(parseLesson(text)).toBeNull();
  });

  it("reads Windows line ends", () => {
    const text = lessonText("coffee_shop").replace(/\n/g, "\r\n");
    expect(parseLesson(text)?.steps).toHaveLength(3);
  });
});

describe("paragraphs", () => {
  it("splits at blank lines, joins wrapped lines and marks code", () => {
    expect(paragraphs("Set `tills`\nto 2.\n\nThen `run`")).toEqual([
      [
        { code: false, text: "Set " },
        { code: true, text: "tills" },
        { code: false, text: " to 2." },
      ],
      [
        { code: false, text: "Then " },
        { code: true, text: "run" },
      ],
    ]);
    expect(paragraphs("  \n\n")).toEqual([]);
  });
});

describe("the exercise's change", () => {
  const tills: Edit[] = [{ edit: "set_parameter", id: "tills", value: 2 }];

  it("reads a parameter's value before and after, and whether the model holds it", () => {
    const model = coffeeShop();
    expect(changeRows(model, tills)).toEqual([{ where: "tills", now: 1, to: 2 }]);
    expect(changeMade(model, tills)).toBe(false);
    const changed = coffeeShop();
    changed.parameters = { tills: { value: 2, type: "integer", min: 1, max: 5 } };
    expect(changeMade(changed, tills)).toBe(true);
    const typed: Edit[] = [{ edit: "set_parameter", id: "tills", type: "number", max: 9 }];
    expect(changeRows(model, typed)).toEqual([
      { where: "tills type", now: "integer", to: "number" },
      { where: "tills max", now: 5, to: 9 },
    ]);
    const missing: Edit[] = [{ edit: "set_parameter", id: "staff", value: 3 }];
    expect(changeRows(model, missing)).toEqual([{ where: "staff", now: undefined, to: 3 }]);
    expect(changeMade({ ...model, parameters: undefined } as never, missing)).toBe(false);
  });

  it("reads a setting and a path, objects compared by value", () => {
    const model = coffeeShop();
    const service = { dist: "exponential", mean: "1 min" };
    const setting: Edit[] = [{ edit: "set_setting", id: "till", path: "/service", value: service }];
    expect(changeRows(model, setting)).toEqual([
      { where: "till/service", now: { dist: "exponential", mean: "1.5 min" }, to: service },
    ]);
    expect(changeMade(model, setting)).toBe(false);
    const till = (model.components ?? [])[1];
    if (till) till.params.service = { mean: "1 min", dist: "exponential" };
    expect(changeMade(model, setting)).toBe(true);
    const gone: Edit[] = [{ edit: "set_setting", id: "nobody", path: "/x", value: 1 }];
    expect(changeRows(model, gone)[0]?.now).toBeUndefined();

    const path: Edit[] = [{ edit: "set_path", path: "/meta/a~1b", value: [1, 2] }];
    expect(changeMade({ ...model, meta: { name: "Shop", "a/b": [1, 2] } }, path)).toBe(true);
    expect(changeMade({ ...model, meta: { name: "Shop", "a/b": [1] } }, path)).toBe(false);
    expect(changeMade({ ...model, meta: { name: "Shop", "a/b": { 0: 1, 1: 2 } } }, path)).toBe(
      false,
    );
    expect(changeMade({ ...model, meta: { name: "Shop", "a/b": null } }, path)).toBe(false);
  });

  it("cannot tell for another kind of edit", () => {
    const edits: Edit[] = [...tills, { edit: "set_label", id: "till", label: "Till" }];
    expect(changeMade(coffeeShop(), edits)).toBeNull();
    expect(changeRows(coffeeShop(), edits)[1]).toEqual({
      where: "set_label",
      now: undefined,
      to: edits[1],
    });
  });

  it("shows values in words", () => {
    expect(valueText(undefined)).toBe("not set");
    expect(valueText("5 min")).toBe("5 min");
    expect(valueText(3)).toBe("3");
    expect(valueText({ $param: "tills" })).toBe("= tills");
    expect(valueText({ dist: "constant", value: 1 })).toBe('{"dist":"constant","value":1}');
  });
});
