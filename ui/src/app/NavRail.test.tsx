import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { NAV_ITEMS, NavRail, NEEDS_PROJECT } from "./NavRail";
import { HOME } from "./router";

describe("NavRail", () => {
  it("shows the seven screens of spec 3, each with its word", () => {
    render(<NavRail route={HOME} projectId={null} onGo={() => {}} />);
    const nav = screen.getByRole("navigation", { name: "Screens" });
    const names = Array.from(nav.querySelectorAll("button")).map((button) => button.textContent);
    expect(names).toEqual([
      "Home",
      "Canvas",
      "Data",
      "Experiment",
      "Run monitor",
      "Results",
      "Settings",
    ]);
    expect(NAV_ITEMS).toHaveLength(7);
  });

  it("marks the current screen, the only one in the tab order", () => {
    render(<NavRail route={HOME} projectId={null} onGo={() => {}} />);
    const home = screen.getByRole("button", { name: "Home" });
    expect(home).toHaveAttribute("aria-current", "page");
    expect(home).toHaveAttribute("tabindex", "0");
    expect(screen.getByRole("button", { name: "Settings" })).toHaveAttribute("tabindex", "-1");
  });

  it("keeps the project screens waiting, with the reason, until a project is open", async () => {
    const onGo = vi.fn();
    render(<NavRail route={HOME} projectId={null} onGo={onGo} />);
    const canvas = screen.getByRole("button", { name: "Canvas" });
    expect(canvas).toHaveAttribute("aria-disabled", "true");
    expect(canvas).toHaveAccessibleDescription(NEEDS_PROJECT);
    await userEvent.click(canvas);
    expect(onGo).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Settings" }));
    expect(onGo).toHaveBeenCalledWith({ screen: "settings", projectId: null });
  });

  it("opens a project screen of the open project", async () => {
    const onGo = vi.fn();
    render(<NavRail route={HOME} projectId="p1" onGo={onGo} />);
    expect(screen.getByRole("button", { name: "Data" })).not.toHaveAttribute("aria-disabled");
    await userEvent.click(screen.getByRole("button", { name: "Data" }));
    expect(onGo).toHaveBeenCalledWith({ screen: "data", projectId: "p1" });
  });

  it("moves with the arrow keys, Home and End, wrapping around", async () => {
    render(<NavRail route={HOME} projectId={null} onGo={() => {}} />);
    screen.getByRole("button", { name: "Home" }).focus();
    await userEvent.keyboard("{ArrowDown}");
    expect(screen.getByRole("button", { name: "Canvas" })).toHaveFocus();
    await userEvent.keyboard("{End}");
    expect(screen.getByRole("button", { name: "Settings" })).toHaveFocus();
    await userEvent.keyboard("{ArrowDown}");
    expect(screen.getByRole("button", { name: "Home" })).toHaveFocus();
    await userEvent.keyboard("{ArrowUp}");
    expect(screen.getByRole("button", { name: "Settings" })).toHaveFocus();
    await userEvent.keyboard("{Home}");
    expect(screen.getByRole("button", { name: "Home" })).toHaveFocus();
    await userEvent.keyboard("a");
    expect(screen.getByRole("button", { name: "Home" })).toHaveFocus();
  });

  it("ignores keys when focus is not on an item", async () => {
    const { container } = render(<NavRail route={HOME} projectId={null} onGo={() => {}} />);
    const list = container.querySelector("ul");
    list?.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true }));
    expect(document.body).toHaveFocus();
  });
});
