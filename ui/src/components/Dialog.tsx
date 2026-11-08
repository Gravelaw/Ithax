/**
 * A modal dialog (`docs/design/design-system.md` "Confirmation dialog";
 * `docs/design/accessibility.md` "Focus order").
 *
 * It renders on a scrim at the end of `document.body` and makes everything else `inert`,
 * so neither the pointer nor Tab can leave it (no keyboard trap: the dialog's own controls
 * close it). Opening moves focus to `initialFocus`, else to the first control; closing
 * returns focus to where it was. Escape calls `onEscape` when given.
 */
import { type ReactNode, type RefObject, useEffect, useRef } from "react";
import { createPortal } from "react-dom";

const FOCUSABLE =
  'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export interface DialogProps {
  labelledBy: string;
  describedBy?: string;
  onEscape?: () => void;
  initialFocus?: RefObject<HTMLElement | null>;
  children: ReactNode;
}

export function Dialog({ labelledBy, describedBy, onEscape, initialFocus, children }: DialogProps) {
  const host = useRef<HTMLDivElement | null>(null);
  if (host.current === null && typeof document !== "undefined") {
    host.current = document.createElement("div");
    host.current.className = "dialog-host";
  }
  const panel = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const element = host.current;
    if (element === null) return;
    const before = document.activeElement as HTMLElement | null;
    document.body.append(element);
    const made: Element[] = [];
    for (const sibling of Array.from(document.body.children)) {
      if (sibling !== element && !sibling.hasAttribute("inert")) {
        sibling.setAttribute("inert", "");
        made.push(sibling);
      }
    }
    const target =
      initialFocus?.current ?? panel.current?.querySelector<HTMLElement>(FOCUSABLE) ?? null;
    target?.focus();
    return () => {
      for (const sibling of made) sibling.removeAttribute("inert");
      element.remove();
      before?.focus();
    };
  }, [initialFocus]);

  if (host.current === null) return null;
  return createPortal(
    <div className="scrim">
      <div
        ref={panel}
        className="dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
        aria-describedby={describedBy}
        onKeyDown={(event) => {
          if (event.key === "Escape" && onEscape !== undefined) {
            event.stopPropagation();
            onEscape();
          }
        }}
      >
        {children}
      </div>
    </div>,
    host.current,
  );
}
