/**
 * The Run monitor (spec 3 "Screens" 5, "Progress events" and "Run monitor, Results and
 * Settings") against a fake service and fake sockets.
 */
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { Project } from "../api/types";
import { LOST_CONTACT } from "../components/ServiceProblem";
import { FakeService, type FakeSocket } from "../test/fakes";
import { aRun, RID } from "../test/runs";
import { CANCEL_WAIT, chooseRun, NO_LIVE_NUMBERS, RunMonitor } from "./RunMonitor";

const PROJECT: Project = {
  id: "p1",
  name: "Shop",
  created: null,
  layout_version: 1,
  model_revision: 0,
  path: "/p1",
  available: true,
};
const OLD = "20261108T090000-AAAAAA";
const NEXT = "20261108T110000-BBBBBB";

function monitor(fake: FakeService, runId?: string) {
  const go = vi.fn();
  const view = render(
    <RunMonitor client={fake.client()} project={PROJECT} runId={runId} onGo={go} />,
  );
  return { go, view, user: userEvent.setup() };
}

/** The run's events socket, once opened. */
async function runSocket(fake: FakeService, rid = RID): Promise<FakeSocket> {
  await waitFor(() =>
    expect(fake.sockets.some((socket) => socket.url.endsWith(`/v1/runs/${rid}/events`))).toBe(true),
  );
  const socket = fake.sockets.filter((item) => item.url.endsWith(`/v1/runs/${rid}/events`)).at(-1);
  if (socket === undefined) throw new Error("no socket");
  return socket;
}

function projectSocket(fake: FakeService): FakeSocket {
  const socket = fake.sockets.find((item) => item.url.endsWith("/v1/projects/p1/events"));
  if (socket === undefined) throw new Error("no project socket");
  return socket;
}

describe("which run the monitor shows", () => {
  it("takes the most recent unfinished run, else the most recent", () => {
    expect(chooseRun([])).toBeNull();
    expect(
      chooseRun([
        aRun({ run_id: OLD, state: "running" }),
        aRun({ run_id: RID, state: "queued" }),
        aRun({ run_id: NEXT, state: "done" }),
      ]),
    ).toBe(RID);
    expect(chooseRun([aRun({ run_id: OLD }), aRun({ run_id: NEXT, state: "failed" })])).toBe(NEXT);
  });

  it("finds the running run on a fresh load, and shows its state, progress and message", async () => {
    const fake = new FakeService().answer("GET /v1/projects/p1/runs", [
      aRun({ run_id: OLD }),
      aRun({ state: "running", fraction: 0.4 }),
    ]);
    monitor(fake);
    const socket = await runSocket(fake);
    socket.open();
    expect(socket.sent).toEqual([JSON.stringify({ token: "test-token" })]);
    act(() => {
      socket.emit({ type: "state", state: "running" });
      socket.emit({
        type: "progress",
        fraction: 0.4,
        message: "Scenario 1 of 1, replication 12 of 30",
      });
    });
    expect(screen.getByRole("heading", { name: `Run ${RID}` })).toBeVisible();
    expect(screen.getByRole("status")).toHaveTextContent("Running");
    const bar = screen.getByRole("progressbar", { name: `Progress of run ${RID}` });
    expect(bar).toHaveAttribute("aria-valuenow", "40");
    expect(bar).toHaveAttribute("aria-valuetext", "40%, Scenario 1 of 1, replication 12 of 30");
    expect(
      screen.getByText("Scenario 1 of 1, replication 12 of 30", { exact: false }),
    ).toBeVisible();
    expect(screen.getByText(NO_LIVE_NUMBERS)).toBeVisible();
    expect(screen.getByText(/Experiment base · accepted/)).toBeVisible();
    act(() => {
      socket.emit({ type: "metrics", scenario: "default", values: { x: 1 } });
      socket.emit("not json");
      socket.emitRaw(new ArrayBuffer(1));
      socket.emit({ type: "progress", fraction: 1, message: "" });
      socket.emit({ type: "state", state: "done" });
      socket.serverClose(1000, "");
    });
    expect(screen.getByRole("status")).toHaveTextContent("Done");
    expect(screen.queryByText(LOST_CONTACT)).toBeNull();
    expect(screen.queryByRole("button", { name: "Cancel run" })).toBeNull();
  });

  it("shows the run its address names, and opens its results once done", async () => {
    const fake = new FakeService().answer("GET /v1/projects/p1/runs", [aRun({ run_id: OLD })]);
    const { go, user } = monitor(fake, RID);
    const socket = await runSocket(fake);
    act(() => {
      socket.emit({ type: "state", state: "done" });
      socket.emit({ type: "progress", fraction: 1, message: "" });
    });
    await user.click(screen.getByRole("button", { name: "See the results" }));
    expect(go).toHaveBeenCalledWith({ screen: "results", projectId: "p1", runId: RID });
    await user.click(screen.getByRole("button", { name: `Watch ${OLD}` }));
    expect(go).toHaveBeenCalledWith({ screen: "monitor", projectId: "p1", runId: OLD });
    await user.click(screen.getByRole("button", { name: `Results of ${OLD}` }));
    expect(go).toHaveBeenCalledWith({ screen: "results", projectId: "p1", runId: OLD });
  });

  it("says when there is no run yet, and when the project is still opening", async () => {
    const fake = new FakeService().answer("GET /v1/projects/p1/runs", []);
    const { go, user, view } = monitor(fake);
    expect(await screen.findByText(/No run of this project yet/)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Canvas" }));
    expect(go).toHaveBeenCalledWith({ screen: "canvas", projectId: "p1" });
    view.unmount();
    render(<RunMonitor client={fake.client()} project={null} runId={undefined} onGo={go} />);
    expect(screen.getByText("Opening the project…")).toBeVisible();
  });

  it("shows a list the service refused", async () => {
    const fake = new FakeService().answer(
      "GET /v1/projects/p1/runs",
      { error: { code: "E186", message: "The project cannot be used." }, issues: [] },
      400,
    );
    monitor(fake);
    expect(await screen.findByText("The project cannot be used.")).toBeVisible();
  });
});

describe("following the run", () => {
  it("reads the list again at each run event, keeping only the latest answer", async () => {
    let answers = 0;
    const fake = new FakeService().on("GET /v1/projects/p1/runs", () => {
      answers += 1;
      return {
        status: 200,
        body:
          answers === 1
            ? [aRun({ state: "running" })]
            : [
                aRun({
                  state: "failed",
                  error: {
                    code: "E190",
                    severity: "error",
                    component: null,
                    path: "",
                    message: "The engine simpy failed.",
                    hint: null,
                  },
                }),
              ],
      };
    });
    monitor(fake);
    const socket = await runSocket(fake);
    act(() => {
      socket.emit({ type: "state", state: "failed" });
      projectSocket(fake).emit({ type: "model", revision: 1, client: null });
      projectSocket(fake).emit({ type: "run", run_id: RID, state: "failed" });
    });
    expect(await screen.findByText("The engine simpy failed.")).toBeVisible();
    expect(answers).toBe(2);
    expect(within(screen.getByRole("table")).getByText("Failed")).toBeVisible();
  });

  it("says contact was lost when the stream closes early, and connects again", async () => {
    const fake = new FakeService().answer("GET /v1/projects/p1/runs", [aRun({ state: "running" })]);
    const { user } = monitor(fake);
    const first = await runSocket(fake);
    act(() => {
      first.emit({ type: "state", state: "running" });
      first.serverClose(1006, "");
    });
    expect(screen.getByText(LOST_CONTACT)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Connect again" }));
    expect(first.closedWith).toBe(1000);
    await waitFor(() =>
      expect(
        fake.sockets.filter((socket) => socket.url.endsWith(`/v1/runs/${RID}/events`)),
      ).toHaveLength(2),
    );
    expect(screen.queryByText(LOST_CONTACT)).toBeNull();
  });

  it("shows the service's words for a run it does not know", async () => {
    const fake = new FakeService()
      .answer("GET /v1/projects/p1/runs", [])
      .answer(
        `GET /v1/runs/${RID}`,
        { error: { code: "E185", message: `There is no run '${RID}'.` }, issues: [] },
        404,
      );
    monitor(fake, RID);
    const socket = await runSocket(fake);
    act(() => socket.serverClose(1008, "E185"));
    expect(await screen.findByText(`There is no run '${RID}'.`)).toBeVisible();
  });

  it("ignores what arrives after the view of a run is gone", async () => {
    const fake = new FakeService().answer("GET /v1/projects/p1/runs", [aRun({ state: "running" })]);
    const { view } = monitor(fake);
    const socket = await runSocket(fake);
    view.unmount();
    expect(socket.closedWith).toBe(1000);
    expect(projectSocket(fake).closedWith).toBe(1000);
    act(() => {
      socket.emit({ type: "state", state: "done" });
      socket.serverClose(1008, "E185");
    });
    expect(fake.requested("GET", `/v1/runs/${RID}`)).toHaveLength(0);
  });
});

describe("cancel", () => {
  it("cancels the run shown, one cancel at a time, and shows a refusal", async () => {
    const fake = new FakeService()
      .answer("GET /v1/projects/p1/runs", [
        aRun({ state: "running" }),
        aRun({ run_id: NEXT, state: "queued" }),
      ])
      .answer(`POST /v1/runs/${NEXT}/cancel`, aRun({ run_id: NEXT, state: "cancelled" }))
      .answer(
        `POST /v1/runs/${RID}/cancel`,
        {
          error: {
            code: "E188",
            message: `The run '${RID}' has ended, so it cannot be cancelled.`,
          },
          issues: [],
        },
        409,
      );
    const { user } = monitor(fake, RID);
    const socket = await runSocket(fake);
    act(() => socket.emit({ type: "state", state: "running" }));
    const release = fake.holdWrites();
    const cancel = screen.getByRole("button", { name: "Cancel run" });
    await user.click(cancel);
    await waitFor(() => expect(fake.held).toBe(1));
    expect(cancel).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByRole("button", { name: `Cancel ${NEXT}` })).toHaveAttribute(
      "aria-disabled",
      "true",
    );
    await user.click(screen.getByRole("button", { name: `Cancel ${NEXT}` }));
    expect(screen.getByText(CANCEL_WAIT)).toBeVisible();
    release();
    expect(
      await screen.findByText(`The run '${RID}' has ended, so it cannot be cancelled.`),
    ).toBeVisible();
    expect(fake.requested("POST", `/v1/runs/${NEXT}/cancel`)).toHaveLength(0);
    await user.click(screen.getByRole("button", { name: `Cancel ${NEXT}` }));
    await waitFor(() => expect(fake.requested("POST", `/v1/runs/${NEXT}/cancel`)).toHaveLength(1));
    await waitFor(() =>
      expect(
        screen.queryByText(`The run '${RID}' has ended, so it cannot be cancelled.`),
      ).toBeNull(),
    );
    expect(screen.queryByText(CANCEL_WAIT)).toBeNull();
  });
});
