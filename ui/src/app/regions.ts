/**
 * F6 and Shift+F6 move between the window's regions in reading order: the navigation
 * rail, the top bar and the main area (`docs/design/accessibility.md` "Focus order"). A
 * region is an element with `data-region`; focus goes to its `data-region-entry` element
 * when it has one (the rail's current screen), else to the region itself.
 */
export function cycleRegion(document: Document, backwards: boolean): void {
  const regions = Array.from(document.querySelectorAll<HTMLElement>("[data-region]")).filter(
    (region) => region.closest("[inert]") === null,
  );
  if (regions.length === 0) return;
  const active = document.activeElement;
  const at = regions.findIndex((region) => active !== null && region.contains(active));
  const step = backwards ? -1 : 1;
  const next = at < 0 ? (backwards ? regions.length - 1 : 0) : at + step;
  const region = regions[(next + regions.length) % regions.length];
  if (region === undefined) return;
  const entry = region.querySelector<HTMLElement>("[data-region-entry]") ?? region;
  entry.focus();
}
