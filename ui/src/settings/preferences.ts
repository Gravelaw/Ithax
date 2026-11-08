/**
 * Applies the interface preferences of `settings.json` to the page (spec 3 `GET
 * /v1/settings`; `docs/design/design-system.md` "Themes", "Type" and "Motion";
 * `docs/design/accessibility.md` "Text size").
 */
import type { InterfacePreferences } from "../api/types";

export const DEFAULT_PREFERENCES: InterfacePreferences = {
  first_start_seen: false,
  ask_before_deleting: true,
  undo_steps: null,
  theme: "system",
  text_size: 100,
  motion: "system",
  colour_blind_charts: false,
};

/** Sets the theme, text size, motion and chart palette on the document's root element. */
export function applyPreferences(root: HTMLElement, preferences: InterfacePreferences): void {
  root.dataset.theme = preferences.theme;
  root.dataset.motion = preferences.motion;
  root.dataset.charts = preferences.colour_blind_charts ? "colour-blind" : "standard";
  // All sizes are in rem, so the root size scales every text together (WCAG 1.4.4).
  root.style.fontSize = `${preferences.text_size}%`;
}
