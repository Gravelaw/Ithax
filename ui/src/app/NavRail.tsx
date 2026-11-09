/**
 * The navigation rail: the seven screens of spec 3, each an icon with its word under it
 * (`docs/design/design-system.md` "Spacing and layout" and "Icons"). The current screen
 * has `aria-current="page"` and a filled icon, so the weight is never the only cue.
 * Screens of a project wait until one is open; they stay focusable, with the reason as
 * their description. Arrow keys, Home and End move between the items; Enter opens one
 * (`docs/design/accessibility.md` "Keyboard map", "Switch screens").
 */
import {
  ChartBarIcon,
  FlaskIcon,
  FlowArrowIcon,
  GearSixIcon,
  HouseIcon,
  type Icon,
  PulseIcon,
  TableIcon,
} from "@phosphor-icons/react";
import { type KeyboardEvent, useRef } from "react";
import { PROJECT_SCREENS, type Route, type Screen } from "./router";

export interface NavItem {
  screen: Screen;
  label: string;
  icon: Icon;
}

export const NAV_ITEMS: readonly NavItem[] = [
  { screen: "home", label: "Home", icon: HouseIcon },
  { screen: "canvas", label: "Canvas", icon: FlowArrowIcon },
  { screen: "data", label: "Data", icon: TableIcon },
  { screen: "experiment", label: "Experiment", icon: FlaskIcon },
  { screen: "monitor", label: "Run monitor", icon: PulseIcon },
  { screen: "results", label: "Results", icon: ChartBarIcon },
  { screen: "settings", label: "Settings", icon: GearSixIcon },
];

export const NEEDS_PROJECT = "Open a project first.";

export function NavRail({
  route,
  projectId,
  onGo,
}: {
  route: Route;
  projectId: string | null;
  onGo: (route: Route) => void;
}) {
  const list = useRef<HTMLUListElement>(null);

  const move = (event: KeyboardEvent<HTMLUListElement>) => {
    const buttons = Array.from(list.current?.querySelectorAll("button") ?? []);
    const at = buttons.indexOf(document.activeElement as HTMLButtonElement);
    if (at < 0) return;
    const last = buttons.length - 1;
    const next = { ArrowDown: at + 1, ArrowUp: at - 1, Home: 0, End: last }[event.key];
    if (next === undefined) return;
    event.preventDefault();
    buttons[(next + buttons.length) % buttons.length]?.focus();
  };

  return (
    <nav className="rail" aria-label="Screens" data-region="rail">
      <ul ref={list} onKeyDown={move}>
        {NAV_ITEMS.map((item) => {
          // The Build form belongs to Home (spec 3 "Screens" 1).
          const current =
            route.screen === item.screen || (route.screen === "build" && item.screen === "home");
          const needsProject = PROJECT_SCREENS.includes(item.screen);
          const blocked = needsProject && projectId === null;
          const IconFor = item.icon;
          return (
            <li key={item.screen}>
              <button
                type="button"
                className="rail-item"
                aria-current={current ? "page" : undefined}
                aria-disabled={blocked ? "true" : undefined}
                aria-describedby={blocked ? "rail-needs-project" : undefined}
                tabIndex={current ? 0 : -1}
                data-region-entry={current ? "" : undefined}
                onClick={() => {
                  if (blocked) return;
                  onGo({ screen: item.screen, projectId: needsProject ? projectId : null });
                }}
              >
                <IconFor aria-hidden="true" size={24} weight={current ? "fill" : "regular"} />
                <span>{item.label}</span>
              </button>
            </li>
          );
        })}
      </ul>
      <p id="rail-needs-project" hidden>
        {NEEDS_PROJECT}
      </p>
    </nav>
  );
}
