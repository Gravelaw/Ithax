/**
 * F6 and Shift+F6 move between the window's regions in reading order: the navigation
 * rail, the top bar and the main area, and inside the Canvas screen its palette, canvas, side
 * panel and problems list (`docs/design/accessibility.md` "Focus order"). A
 * region is an element with `data-region`; focus goes to its `data-region-entry` element
 * when it has one (the rail's current screen), else to the region itself.
 */
export function cycleRegion(document: Document, backwards: boolean): void {
  const regions = Array.from(document.querySelectorAll<HTMLElement>("[data-region]")).filter(
    (region) => region.closest("[inert]") === null,
  );
  if (regions.length === 0) return;
  const active = document.activeElement;
  // The innermost region holding the focus: the Canvas screen's regions sit in the main area.
  const at = regions.findLastIndex((region) => active !== null && region.contains(active));
  const step = backwards ? -1 : 1;
  const next = at < 0 ? (backwards ? regions.length - 1 : 0) : at + step;
  const region = regions[(next + regions.length) % regions.length];
  if (region === undefined) return;
  const entry = region.querySelector<HTMLElement>("[data-region-entry]") ?? region;
  entry.focus();
}
