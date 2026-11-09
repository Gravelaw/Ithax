/**
 * Which screen is shown, kept in the address's fragment (`#/canvas/<project id>`), so a
 * reload of the tab stays on it. The Run monitor and Results may also name a run
 * (`#/monitor/<project id>/<run id>`, AKS-138); the Build form is `#/build` (AKS-124). The fragment `#token=...` belongs to the launcher and is
 * taken away before the router reads the address (`api/token.ts`).
 */
import { useCallback, useEffect, useState } from "react";

export type Screen =
  | "home"
  | "build"
  | "canvas"
  | "data"
  | "experiment"
  | "monitor"
  | "results"
  | "settings";

/** Screens that show one project, and so need one. */
export const PROJECT_SCREENS: readonly Screen[] = [
  "canvas",
  "data",
  "experiment",
  "monitor",
  "results",
];

/** Screens that may name one run of their project. */
export const RUN_SCREENS: readonly Screen[] = ["monitor", "results"];

export interface Route {
  screen: Screen;
  projectId: string | null;
  /** The run shown (Run monitor and Results); absent for the project's own choice. */
  runId?: string;
}

export const HOME: Route = { screen: "home", projectId: null };

/** The Build form (`#/build`, AKS-124) is part of Home, and not on the rail. */
const SCREENS: readonly Screen[] = ["home", "build", ...PROJECT_SCREENS, "settings"];

function decoded(part: string): string | null {
  try {
    return decodeURIComponent(part);
  } catch {
    return null;
  }
}

export function parseRoute(hash: string): Route {
  const [screen, id, run, ...rest] = hash.replace(/^#\/?/, "").split("/");
  if (rest.length > 0 || !SCREENS.includes(screen as Screen)) return HOME;
  const named = screen as Screen;
  if (PROJECT_SCREENS.includes(named)) {
    const projectId = id ? decoded(id) : null;
    if (projectId === null || projectId === "") return HOME;
    if (run === undefined) return { screen: named, projectId };
    const runId = RUN_SCREENS.includes(named) && run !== "" ? decoded(run) : null;
    return runId === null || runId === "" ? HOME : { screen: named, projectId, runId };
  }
  return id || run !== undefined ? HOME : { screen: named, projectId: null };
}

export function routeHash(route: Route): string {
  if (route.screen === "home") return "#/";
  if (route.projectId === null) return `#/${route.screen}`;
  const project = `#/${route.screen}/${encodeURIComponent(route.projectId)}`;
  return route.runId === undefined ? project : `${project}/${encodeURIComponent(route.runId)}`;
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
