/**
 * The side panel as an overlay when the window is narrow (#93; design-system.md "Spacing
 * and layout": "Below 1024 px wide the side panel becomes an overlay that opens on
 * selection"). It opens when a block or connection is selected, and in a lesson, whose
 * step card it holds; "Close the panel" closes it, and "Show the panel" in the top bar
 * opens it on the model's parameters. Closed, it is hidden and inert, so F6 passes it by
 * and its fields keep what they hold. At the designed width it is the plain column.
 */
import { SidebarSimpleIcon, XIcon } from "@phosphor-icons/react";
import { type ReactNode, useEffect, useState } from "react";

/** Whether the overlay is open: opened by each new selection, and at a lesson's start. */
export function useSheet(learning: boolean, selected: string): [boolean, (open: boolean) => void] {
  const [open, setOpen] = useState(learning);
  useEffect(() => {
    if (selected !== "") setOpen(true);
  }, [selected]);
  return [open, setOpen];
}

export function SideSheet(props: {
  narrow: boolean;
  open: boolean;
  onClose: () => void;
  children: ReactNode;
}): ReactNode {
  if (!props.narrow) return props.children;
  return (
    <div className="side-sheet" hidden={!props.open} inert={!props.open}>
      <div className="side-sheet-bar">
        <button
          type="button"
          className="icon-button"
          aria-label="Close the panel"
          onClick={props.onClose}
        >
          <XIcon aria-hidden="true" size={16} />
        </button>
      </div>
      {props.children}
    </div>
  );
}

export function ShowPanel(props: { onShow: () => void }): ReactNode {
  return (
    <button type="button" className="secondary" onClick={props.onShow}>
      <SidebarSimpleIcon aria-hidden="true" size={16} />
      Show the panel
    </button>
  );
}
