/** A setting entered in a unit the user picks (#87 and #96). */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { BYTES, IDLE_MINUTES, inUnits, shownIn, UnitField, unitFor } from "./UnitField";

describe("the unit a value is shown in", () => {
  it("is the largest that shows it whole, else the largest it reaches", () => {
    expect(unitFor(30, IDLE_MINUTES).label).toBe("minutes");
    expect(unitFor(120, IDLE_MINUTES).label).toBe("hours");
    expect(unitFor(10_080, IDLE_MINUTES).label).toBe("days");
    expect(unitFor(90, IDLE_MINUTES).label).toBe("minutes");
    expect(unitFor(8_589_934_592, BYTES).label).toBe("GB");
    expect(unitFor(4_000_000, BYTES).label).toBe("MB");
    expect(unitFor(null, BYTES).label).toBe("GB");
    expect(shownIn(8_589_934_592, unitFor(8_589_934_592, BYTES))).toBe("8.589934592");
  });

  it("turns a typed number back into the base unit, whole when it is", () => {
    const hours = IDLE_MINUTES[1];
    if (hours === undefined) throw new Error("no hours");
    expect(inUnits("1.5", hours, true)).toBe(90);
    expect(inUnits("0.1", hours, true)).toBe(6);
    expect(inUnits("0.01", hours, true)).toBe(0.6);
    expect(inUnits("", hours, true)).toBeNull();
    expect(inUnits("lots", hours, true)).toBe("lots");
    const gb = BYTES[1];
    if (gb === undefined) throw new Error("no GB");
    expect(inUnits("8.59", gb, false)).toBe(8_590_000_000);
  });
});

describe("UnitField", () => {
  it("writes the number in the unit picked, and a new unit re-reads it", async () => {
    const commit = vi.fn();
    const user = userEvent.setup();
    render(
      <UnitField
        label="Stop when idle for"
        term="idle_timeout_minutes"
        saved={30}
        units={IDLE_MINUTES}
        whole
        busy={false}
        onCommit={commit}
      />,
    );
    const box = screen.getByRole("textbox", { name: "Stop when idle for" });
    expect(box).toHaveValue("30");
    expect(screen.getByRole("combobox", { name: "Unit of Stop when idle for" })).toHaveValue(
      "minutes",
    );
    await user.clear(box);
    await user.type(box, "2{Enter}");
    expect(commit).toHaveBeenLastCalledWith(2);
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Unit of Stop when idle for" }),
      "hours",
    );
    expect(commit).toHaveBeenLastCalledWith(120);
  });

  it("offers never as its own choice, which writes 0, and unticked the default", async () => {
    const commit = vi.fn();
    const user = userEvent.setup();
    const { rerender } = render(
      <UnitField
        label="Stop when idle for"
        term="idle_timeout_minutes"
        saved={30}
        units={IDLE_MINUTES}
        whole
        never
        busy={false}
        onCommit={commit}
      />,
    );
    await user.click(screen.getByRole("checkbox", { name: "Never" }));
    expect(commit).toHaveBeenLastCalledWith(0);
    rerender(
      <UnitField
        label="Stop when idle for"
        term="idle_timeout_minutes"
        saved={0}
        units={IDLE_MINUTES}
        whole
        never
        busy={false}
        onCommit={commit}
      />,
    );
    expect(screen.getByRole("checkbox", { name: "Never" })).toBeChecked();
    expect(screen.getByRole("textbox", { name: "Stop when idle for" })).toBeDisabled();
    await user.click(screen.getByRole("checkbox", { name: "Never" }));
    expect(commit).toHaveBeenLastCalledWith(null);
  });
});
