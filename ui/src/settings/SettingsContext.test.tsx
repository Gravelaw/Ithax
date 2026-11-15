/**
 * The settings the interface holds are the latest the service committed, whatever the order
 * in which the service answers (CI and reviews of pull request 200: ticking "Never" while
 * Settings read the settings showed the old value; a read sent during a write, or two
 * overlapping writes answered out of order, could leave an older value shown). Every read
 * and write goes through one queue in the provider, so only one is in flight.
 */
import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { ApiClient } from "../api/client";
import type { Settings } from "../api/types";
import { ORIGIN, SETTINGS, TOKEN } from "../test/fakes";
import { SettingsProvider, useSettings } from "./SettingsContext";

type Policy = "oldest first" | "newest first";

/**
 * A service that answers the requests in flight only when the test says, in the order of
 * `policy`, committing each write when it answers it, as a service that takes requests in
 * any order would.
 */
function service(policy: Policy) {
  let stored: Settings = structuredClone(SETTINGS);
  const waiting: { method: string; body: unknown; answer: (response: Response) => void }[] = [];
  let mostAtOnce = 0;
  const fetch = (_input: RequestInfo | URL, init?: RequestInit): Promise<Response> =>
    new Promise<Response>((answer) => {
      const body = typeof init?.body === "string" ? JSON.parse(init.body) : undefined;
      waiting.push({ method: init?.method ?? "GET", body, answer });
      mostAtOnce = Math.max(mostAtOnce, waiting.length);
    });
  /** Answers one request in flight, if any. */
  const answerOne = () => {
    const request = policy === "oldest first" ? waiting.shift() : waiting.pop();
    if (request === undefined) return;
    if (request.method === "PUT") stored = { ...stored, ...(request.body as Partial<Settings>) };
    const json = JSON.stringify({ settings: stored, issues: [] });
    request.answer(new Response(json, { headers: { "Content-Type": "application/json" } }));
  };
  const client = new ApiClient({
    origin: ORIGIN,
    token: TOKEN,
    fetch,
    webSocket: () => {
      throw new Error("no sockets here");
    },
  });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <SettingsProvider client={client} initial={SETTINGS} root={document.documentElement}>
      {children}
    </SettingsProvider>
  );
  return {
    wrapper,
    answerOne,
    mostAtOnce: () => mostAtOnce,
    stored: () => stored,
    elsewhere: (change: Partial<Settings>) => {
      stored = { ...stored, ...change };
    },
  };
}

/** Answers requests until `pending` have all settled, each queued one sent in its turn. */
async function answerAll(answerOne: () => void, pending: Promise<unknown>[]): Promise<void> {
  let settled = false;
  const all = Promise.all(pending).then(() => {
    settled = true;
  });
  for (let turn = 0; turn < 50 && !settled; turn += 1) {
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
      answerOne();
    });
  }
  await act(async () => {
    await all;
  });
}

describe("the settings held by the interface", () => {
  it.each<Policy>(["oldest first", "newest first"])(
    "are the latest committed after two overlapping writes and a read between them, answered %s",
    async (policy) => {
      const fake = service(policy);
      const { result } = renderHook(() => useSettings(), { wrapper: fake.wrapper });
      let pending: Promise<unknown>[] = [];
      act(() => {
        pending = [
          result.current.save({ idle_timeout_minutes: 45 }),
          result.current.refresh(),
          result.current.save({ idle_timeout_minutes: 0 }),
        ];
      });
      await answerAll(fake.answerOne, pending);
      expect(fake.mostAtOnce()).toBe(1);
      expect(fake.stored().idle_timeout_minutes).toBe(0);
      expect(result.current.settings.idle_timeout_minutes).toBe(0);
    },
  );

  it.each<Policy>(["oldest first", "newest first"])(
    "are not taken back by a read sent before a write, answered %s",
    async (policy) => {
      const fake = service(policy);
      const { result } = renderHook(() => useSettings(), { wrapper: fake.wrapper });
      let pending: Promise<unknown>[] = [];
      act(() => {
        pending = [result.current.refresh(), result.current.save({ idle_timeout_minutes: 0 })];
      });
      await answerAll(fake.answerOne, pending);
      expect(fake.mostAtOnce()).toBe(1);
      expect(result.current.settings.idle_timeout_minutes).toBe(0);
    },
  );

  it("take a read sent after a write, with another client's change", async () => {
    const fake = service("oldest first");
    const { result } = renderHook(() => useSettings(), { wrapper: fake.wrapper });
    let pending: Promise<unknown>[] = [];
    act(() => {
      pending = [result.current.save({ idle_timeout_minutes: 45 })];
    });
    await answerAll(fake.answerOne, pending);
    fake.elsewhere({ idle_timeout_minutes: 0 });
    act(() => {
      pending = [result.current.refresh()];
    });
    await answerAll(fake.answerOne, pending);
    expect(result.current.settings.idle_timeout_minutes).toBe(0);
  });
});
