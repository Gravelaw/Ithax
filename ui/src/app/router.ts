/**
 * Which screen is shown, kept in the address's fragment (`#/canvas/<project id>`), so a
 * reload of the tab stays on it. The fragment `#token=...` belongs to the launcher and is
 * taken away before the router reads the address (`api/token.ts`).
 */
import { useCallback, useEffect, useState } from "react";

export type Screen = "home" | "canvas" | "data" | "experiment" | "monitor" | "results" | "settings";

/** Screens that show one project, and so need one. */
export const PROJECT_SCREENS: readonly Screen[] = [
  "canvas",
  "data",
  "experiment",
  "monitor",
  "results",
];

export interface Route {
  screen: Screen;
  projectId: string | null;
}

export const HOME: Route = { screen: "home", projectId: null };

const SCREENS: readonly Screen[] = ["home", ...PROJECT_SCREENS, "settings"];

export function parseRoute(hash: string): Route {
  const [screen, id, ...rest] = hash.replace(/^#\/?/, "").split("/");
  if (rest.length > 0 || !SCREENS.includes(screen as Screen)) return HOME;
  const named = screen as Screen;
  if (PROJECT_SCREENS.includes(named)) {
    return id ? { screen: named, projectId: decodeURIComponent(id) } : HOME;
  }
  return id ? HOME : { screen: named, projectId: null };
}

export function routeHash(route: Route): string {
  if (route.screen === "home") return "#/";
  if (route.projectId === null) return `#/${route.screen}`;
  return `#/${route.screen}/${encodeURIComponent(route.projectId)}`;
}

/** The current route and a function that goes to another, through the address. */
export function useRoute(win: Window = window): [Route, (route: Route) => void] {
  const [route, setRoute] = useState(() => parseRoute(win.location.hash));
  useEffect(() => {
    const changed = () => setRoute(parseRoute(win.location.hash));
    win.addEventListener("hashchange", changed);
    return () => win.removeEventListener("hashchange", changed);
  }, [win]);
  const go = useCallback(
    (next: Route) => {
      const hash = routeHash(next);
      if (win.location.hash !== hash) win.location.hash = hash;
      setRoute(next);
    },
    [win],
  );
  return [route, go];
}
