import { act, render, renderHook, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiClient } from "../api/client";
import { NewProjectDialog } from "../screens/NewProjectDialog";
import { OpenProjectDialog } from "../screens/OpenProjectDialog";
import { ORIGIN, TOKEN } from "../test/fakes";
import { usePendingRequest } from "./usePendingRequest";

function deferred<T>() {
  let resolve: (value: T) => void = () => {};
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

describe("usePendingRequest", () => {
  it("runs one request at a time and hands its result on", async () => {
    const { result } = renderHook(() => usePendingRequest());
    const first = deferred<string>();
    const done = vi.fn();
    const second = vi.fn(async () => "second");
    act(() => {
      void result.current.run(() => first.promise, done);
    });
    expect(result.current.busy).toBe(true);
    await act(() => result.current.run(second, done));
    expect(second).not.toHaveBeenCalled();
    await act(async () => first.resolve("first"));
    expect(done).toHaveBeenCalledExactlyOnceWith("first");
    expect(result.current.busy).toBe(false);
  });

  it("makes no callback once its component is gone", async () => {
    const { result, unmount } = renderHook(() => usePendingRequest());
    const request = deferred<string>();
    const done = vi.fn();
    act(() => {
      void result.current.run(() => request.promise, done);
    });
    unmount();
    await act(async () => request.resolve("late"));
    expect(done).not.toHaveBeenCalled();
  });
});

function pendingClient() {
  const answer = deferred<Response>();
  const client = new ApiClient({ origin: ORIGIN, token: TOKEN, fetch: () => answer.promise });
  return { client, answer };
}

const created = {
  id: "p",
  name: "Late",
  created: null,
  layout_version: 1,
  model_revision: 0,
  path: "/p",
  available: true,
};

describe.each([
  ["New empty project", "Create", "Name"],
  ["Open a project folder", "Open", "Folder"],
] as const)("the %s dialog while its request is pending", (_title, submit, field) => {
  function show(client: ApiClient, onDone: () => void, onCancel: () => void) {
    return submit === "Create"
      ? render(<NewProjectDialog client={client} onCreated={onDone} onCancel={onCancel} />)
      : render(<OpenProjectDialog client={client} onOpened={onDone} onCancel={onCancel} />);
  }

  it("cannot be dismissed with Cancel or Escape", async () => {
    const { client, answer } = pendingClient();
    const onCancel = vi.fn();
    const onDone = vi.fn();
    show(client, onDone, onCancel);
    await userEvent.type(screen.getByRole("textbox", { name: field }), "x");
    await userEvent.click(screen.getByRole("button", { name: submit }));
    expect(screen.getByRole("button", { name: "Cancel" })).toHaveAttribute("aria-disabled", "true");
    await userEvent.keyboard("{Escape}");
    expect(onCancel).not.toHaveBeenCalled();
    await act(async () => answer.resolve(new Response(JSON.stringify(created))));
    expect(onDone).toHaveBeenCalledOnce();
    expect(screen.getByRole("button", { name: "Cancel" })).not.toHaveAttribute("aria-disabled");
    await userEvent.keyboard("{Escape}");
    expect(onCancel).toHaveBeenCalledOnce();
  });

  it("does not report a completion after it is gone", async () => {
    const { client, answer } = pendingClient();
    const onDone = vi.fn();
    const { unmount } = show(client, onDone, () => {});
    await userEvent.type(screen.getByRole("textbox", { name: field }), "x");
    await userEvent.click(screen.getByRole("button", { name: submit }));
    unmount();
    await act(async () => answer.resolve(new Response(JSON.stringify(created))));
    expect(onDone).not.toHaveBeenCalled();
  });
});
