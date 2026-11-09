import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { HOME, parseRoute, routeHash, useRoute } from "./router";

describe("routes", () => {
  it.each([
    ["", HOME],
    ["#/", HOME],
    ["#/settings", { screen: "settings", projectId: null }],
    ["#/canvas/abc", { screen: "canvas", projectId: "abc" }],
    ["#/results/a%2Fb", { screen: "results", projectId: "a/b" }],
    ["#/canvas", HOME],
    ["#/settings/x", HOME],
    ["#/nowhere", HOME],
    ["#/canvas/a/b", HOME],
    ["#token=abc", HOME],
  ])("%s is %o", (hash, route) => {
    expect(parseRoute(hash)).toEqual(route);
  });

  it("writes each route back to its fragment", () => {
    expect(routeHash(HOME)).toBe("#/");
    expect(routeHash({ screen: "settings", projectId: null })).toBe("#/settings");
    expect(routeHash({ screen: "monitor", projectId: "a/b" })).toBe("#/monitor/a%2Fb");
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
