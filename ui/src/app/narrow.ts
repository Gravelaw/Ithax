/**
 * Whether the window is narrow (#93; docs/design/design-system.md "Spacing and layout",
 * accessibility.md WCAG 1.4.10): below 1,024 px at 100% text, the side panel becomes an
 * overlay. The width is counted in the root's rem, so the text-size setting narrows the
 * window as a smaller one would: 1,280 px at 200% text is 40 rem, as 640 px is at 100%.
 * A media query cannot say this, since its rem is the browser's, not the root's.
 */
import { useEffect, useState } from "react";

/** The designed minimum, 1,024 px at 16 px to the rem. */
export const NARROW_REM = 64;

export function isNarrow(width: number, remPx: number): boolean {
  return remPx > 0 && width / remPx < NARROW_REM;
}

function measure(): boolean {
  const rem = Number.parseFloat(getComputedStyle(document.documentElement).fontSize);
  return isNarrow(window.innerWidth, Number.isFinite(rem) ? rem : 16);
}

/** Follows the window's width and the root's text size (`applyPreferences` sets its style). */
export function useNarrow(): boolean {
  const [narrow, setNarrow] = useState(measure);
  useEffect(() => {
    const update = () => setNarrow(measure());
    window.addEventListener("resize", update);
    const observer = new MutationObserver(update);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["style"] });
    update();
    return () => {
      window.removeEventListener("resize", update);
      observer.disconnect();
    };
  }, []);
  return narrow;
}
