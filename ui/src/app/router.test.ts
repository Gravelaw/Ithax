import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { HOME, parseRoute, routeHash, useRoute } from "./router";

describe("routes", () => {
  it.each([
    ["", HOME],
    ["#/", HOME],
    ["#/settings", { screen: "settings", projectId: null }],
    ["#/build", { screen: "build", projectId: null }],
    ["#/build/x", HOME],
    ["#/canvas/abc", { screen: "canvas", projectId: "abc" }],
    ["#/results/a%2Fb", { screen: "results", projectId: "a/b" }],
    ["#/canvas", HOME],
    ["#/settings/x", HOME],
    ["#/nowhere", HOME],
    ["#/canvas/a/b", HOME],
    ["#token=abc", HOME],
    [
      "#/monitor/p/20261108T101502-K3QX7A",
      { screen: "monitor", projectId: "p", runId: "20261108T101502-K3QX7A" },
    ],
    ["#/results/p/r%2F1", { screen: "results", projectId: "p", runId: "r/1" }],
    ["#/monitor/p/", HOME],
    ["#/results/p/r/x", HOME],
    ["#/data/p/r", HOME],
    ["#/settings//", HOME],
    ["#/canvas/%E0%A4%A", HOME],
    ["#/results/p/%E0%A4%A", HOME],
  ])("%s is %o", (hash, route) => {
    expect(parseRoute(hash)).toEqual(route);
  });

  it("writes each route back to its fragment", () => {
    expect(routeHash(HOME)).toBe("#/");
    expect(routeHash({ screen: "settings", projectId: null })).toBe("#/settings");
    expect(routeHash({ screen: "build", projectId: null })).toBe("#/build");
    expect(routeHash({ screen: "monitor", projectId: "a/b" })).toBe("#/monitor/a%2Fb");
    expect(routeHash({ screen: "results", projectId: "p", runId: "r/1" })).toBe(
      "#/results/p/r%2F1",
    );
    expect(parseRoute(routeHash({ screen: "data", projectId: "x y" }))).toEqual({
      screen: "data",
      projectId: "x y",
    });
  });

  it("follows the address and goes through it", () => {
    const { result } = renderHook(() => useRoute());
    expect(result.current[0]).toEqual(HOME);
    act(() => result.current[1]({ screen: "canvas", projectId: "p" }));
    expect(window.location.hash).toBe("#/canvas/p");
    expect(result.current[0]).toEqual({ screen: "canvas", projectId: "p" });
    act(() => {
      window.location.hash = "#/settings";
      window.dispatchEvent(new HashChangeEvent("hashchange"));
    });
    expect(result.current[0]).toEqual({ screen: "settings", projectId: null });
  });
});
