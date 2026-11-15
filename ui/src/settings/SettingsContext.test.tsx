/**
 * The settings the interface holds follow the latest request sent, not the latest answer
 * received (CI of pull request 200: ticking "Never" while Settings was still reading the
 * settings showed the old value, since the read, sent first, was answered last).
 */
import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { ApiClient } from "../api/client";
import type { Settings } from "../api/types";
import { FakeService, ORIGIN, SETTINGS, TOKEN } from "../test/fakes";
import { SettingsProvider, useSettings } from "./SettingsContext";

/** A service whose `GET /v1/settings` is answered only when the test lets it go. */
function slowReads() {
  let stored: Settings = structuredClone(SETTINGS);
  const fake = new FakeService()
    .on("GET /v1/settings", () => ({ status: 200, body: { settings: stored, issues: [] } }))
    .on("PUT /v1/settings", (body) => {
      stored = { ...stored, ...(body as Partial<Settings>) };
      return { status: 200, body: { settings: stored, issues: [] } };
    });
  const held: (() => void)[] = [];
  const fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    // The answer is computed when the request arrives, then held back.
    const answer = fake.fetch(input, init);
    if ((init?.method ?? "GET") === "GET") await new Promise<void>((go) => held.push(go));
    return answer;
  };
  const client = new ApiClient({ origin: ORIGIN, token: TOKEN, fetch, webSocket: fake.webSocket });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <SettingsProvider client={client} initial={SETTINGS} root={document.documentElement}>
      {children}
    </SettingsProvider>
  );
  /** Another client's write, straight into the service. */
  const elsewhere = (change: Partial<Settings>) => {
    stored = { ...stored, ...change };
  };
  const release = () => {
    for (const go of held.splice(0)) go();
  };
  return { wrapper, elsewhere, release };
}

describe("the settings held by the interface", () => {
  it("are not taken back by a read sent before a write and answered after it", async () => {
    const { wrapper, release } = slowReads();
    const { result } = renderHook(() => useSettings(), { wrapper });
    let read: Promise<unknown> = Promise.resolve();
    await act(async () => {
      read = result.current.refresh();
      await result.current.save({ idle_timeout_minutes: 0 });
    });
    expect(result.current.settings.idle_timeout_minutes).toBe(0);
    await act(async () => {
      release();
      await read;
    });
    expect(result.current.settings.idle_timeout_minutes).toBe(0);
  });

  it("take a read sent after a write, with another client's change", async () => {
    const { wrapper, elsewhere, release } = slowReads();
    const { result } = renderHook(() => useSettings(), { wrapper });
    await act(async () => {
      await result.current.save({ idle_timeout_minutes: 45 });
    });
    elsewhere({ idle_timeout_minutes: 0 });
    await act(async () => {
      const read = result.current.refresh();
      release();
      await read;
    });
    expect(result.current.settings.idle_timeout_minutes).toBe(0);
  });
});
