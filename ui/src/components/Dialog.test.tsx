import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useRef, useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { Dialog } from "./Dialog";

function Opener({ onEscape }: { onEscape?: () => void }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>
        Open
      </button>
      {open ? (
        <Dialog
          labelledBy="t"
          onEscape={() => {
            onEscape?.();
            setOpen(false);
          }}
        >
          <h1 id="t">Title</h1>
          <button type="button">First</button>
          <button type="button" onClick={() => setOpen(false)}>
            Close
          </button>
        </Dialog>
      ) : null}
    </>
  );
}

function Notice() {
  const target = useRef<HTMLButtonElement>(null);
  return (
    <Dialog labelledBy="n" initialFocus={target}>
      <h1 id="n">Notice</h1>
      <button type="button">Other</button>
      <button type="button" ref={target}>
        Go
      </button>
    </Dialog>
  );
}

describe("Dialog", () => {
  it("is a named modal dialog that takes focus and makes the rest inert", async () => {
    const { container } = render(<Opener />);
    await userEvent.click(screen.getByRole("button", { name: "Open" }));
    const dialog = screen.getByRole("dialog", { name: "Title" });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(screen.getByRole("button", { name: "First" })).toHaveFocus();
    expect(container).toHaveAttribute("inert");
  });

  it("gives focus back and the page back when it closes", async () => {
    const { container } = render(<Opener />);
    const opener = screen.getByRole("button", { name: "Open" });
    await userEvent.click(opener);
    await userEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(container).not.toHaveAttribute("inert");
    expect(opener).toHaveFocus();
  });

  it("closes with Escape when it may", async () => {
    const onEscape = vi.fn();
    render(<Opener onEscape={onEscape} />);
    await userEvent.click(screen.getByRole("button", { name: "Open" }));
    await userEvent.keyboard("{Escape}");
    expect(onEscape).toHaveBeenCalledOnce();
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("starts on the control it is given, and ignores Escape without a handler", async () => {
    render(<Notice />);
    expect(screen.getByRole("button", { name: "Go" })).toHaveFocus();
    await userEvent.keyboard("{Escape}");
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("leaves an element that was already inert as it was", () => {
    const outside = document.createElement("div");
    outside.setAttribute("inert", "");
    document.body.append(outside);
    const { unmount } = render(
      <Dialog labelledBy="x">
        <h1 id="x">X</h1>
      </Dialog>,
    );
    unmount();
    expect(outside).toHaveAttribute("inert");
    outside.remove();
  });
});
