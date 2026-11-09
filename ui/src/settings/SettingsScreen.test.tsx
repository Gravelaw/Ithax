/**
 * The Settings screen (spec 3 "Screens" 7, `GET`/`PUT /v1/settings`, "Run monitor, Results
 * and Settings") against a fake service that keeps the settings as `PUT` writes them.
 */
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type { Issue, Settings } from "../api/types";
import { FakeService, SETTINGS } from "../test/fakes";
import { DEFAULT_PREFERENCES } from "./preferences";
import { SettingsProvider } from "./SettingsContext";
import {
  AT_NEXT_RESULTS,
  AT_NEXT_START,
  bytesText,
  IDLE_LABEL,
  SETTINGS_WAIT,
  SettingsScreen,
  typed,
} from "./SettingsScreen";

const W220: Issue = {
  code: "W220",
  severity: "warning",
  component: null,
  path: "/finding_thresholds/bottleneck_utilization",
  message: "The threshold 'bottleneck_utilization' in settings.json is 2.",
  hint: "Give a number from 0 to 1.",
};

/** A service whose `PUT /v1/settings` applies a valid change, and refuses a text value. */
function settingsService(initial: Settings = SETTINGS, issues: Issue[] = []) {
  let settings = structuredClone(initial);
  const fake = new FakeService()
    .on("GET /v1/settings", () => ({ status: 200, body: { settings, issues } }))
    .answer("GET /v1/system", {
      cores: 8,
      memory: 16e9,
      graphics: ["intel"],
      tier: "mid",
      workers: 8,
    })
    .answer("GET /v1/engines", [
      {
        name: "simpy",
        version: "0.0.0",
        domains: ["process"],
        component_types: [],
        hardware: [],
        parallel_modes: ["replications"],
        licence: "MIT",
        invocation: "in-process",
      },
    ]);
  fake.on("PUT /v1/settings", (body) => {
    const change = body as Record<string, unknown>;
    const bad = Object.entries(change).flatMap(([key, value]) => {
      const values =
        typeof value === "object" && value !== null ? Object.entries(value) : [[key, value]];
      return values
        .filter(([, item]) => typeof item === "string" && key !== "tier" && key !== "interface")
        .map(([name]) => ({
          code: "E184",
          severity: "error",
          component: null,
          path: key === name ? `/${key}` : `/${key}/${name}`,
          message: `'${name}' must be a number.`,
          hint: null,
        }));
    });
    if (bad.length > 0) {
      return {
        status: 400,
        body: { error: { code: "E184", message: "The settings were not written." }, issues: bad },
      };
    }
    const next: Record<string, unknown> = { ...settings };
    for (const [key, value] of Object.entries(change)) {
      next[key] = value === null ? (SETTINGS as unknown as Record<string, unknown>)[key] : value;
    }
    settings = next as unknown as Settings;
    return { status: 200, body: { settings, issues } };
  });
  return { fake, current: () => settings };
}

/** Opens the screen and waits until it has read the settings, the system and the engines. */
async function open(fake: FakeService, initial: Settings = SETTINGS) {
  const client = fake.client();
  render(
    <SettingsProvider client={client} initial={initial} root={document.documentElement}>
      <SettingsScreen client={client} />
    </SettingsProvider>,
  );
  await screen.findByRole("heading", { name: "Engines" });
  await waitFor(() => expect(fake.requested("GET", "/v1/engines")).toHaveLength(1));
  await new Promise((resolve) => setTimeout(resolve, 0));
  return userEvent.setup();
}

function lastPut(fake: FakeService): unknown {
  return fake.requested("PUT", "/v1/settings").at(-1)?.body;
}

describe("Settings reads", () => {
  it("shows the run targets, hardware, engines and when each setting takes effect", async () => {
    const { fake } = settingsService();
    await open(fake);
    expect(
      await screen.findByText(/Detected: 8 cores, 16 GB memory, graphics: intel/),
    ).toBeVisible();
    expect(screen.getByText(/This start uses the mid tier, with 8 workers per run/)).toBeVisible();
    const targets = screen.getByRole("table", { name: "Where runs happen" });
    expect(
      within(targets).getByRole("rowheader", { name: "local" }).closest("tr"),
    ).toHaveTextContent("available");
    expect(
      within(targets).getByRole("rowheader", { name: "remote (SSH)" }).closest("tr"),
    ).toHaveTextContent("Not available in this version");
    expect(screen.getByRole("rowheader", { name: "simpy" }).closest("tr")).toHaveTextContent(
      "simpy0.0.0processMIT",
    );
    // The run settings and the idle timeout each say so.
    expect(screen.getAllByText(AT_NEXT_START)).toHaveLength(2);
    expect(screen.getByText(new RegExp(`^${AT_NEXT_RESULTS}`))).toBeVisible();
    expect(screen.getAllByText("Takes effect at once.")).toHaveLength(2);
    expect(screen.getByRole("textbox", { name: "Time limit, in seconds" })).toHaveValue("600");
    expect(screen.getByText("= 10 min")).toBeVisible();
    expect(screen.getByText("= 8.59 GB")).toBeVisible();
    expect(screen.getByRole("textbox", { name: IDLE_LABEL })).toHaveValue("30");
    expect(screen.getByText("= 30 min (1 to 10,080)")).toBeVisible();
    expect(screen.getByText("= 1 per hour")).toBeVisible();
    expect(screen.getByRole("combobox", { name: "Tier at the next start" })).toHaveValue("mid");
    expect(screen.getByText("Empty: the tier's recommendation, 500 (100 to 10,000)")).toBeVisible();
    expect(fake.requested("GET", "/v1/settings")).toHaveLength(1);
  });

  it("shows the service's W220 issues, and what it could not say", async () => {
    const { fake } = settingsService(SETTINGS, [W220]);
    fake.answer("GET /v1/system", {
      cores: 2,
      memory: null,
      graphics: null,
      tier: "low",
      workers: 2,
    });
    fake.answer(
      "GET /v1/engines",
      { error: { code: "E187", message: "The service failed." }, issues: [] },
      500,
    );
    await open(fake);
    expect(await screen.findByText(W220.message)).toBeVisible();
    expect(await screen.findByText(/memory unknown, graphics: unknown/)).toBeVisible();
    expect(await screen.findByText("The service failed.")).toBeVisible();
  });

  it("says when the settings cannot be read again", async () => {
    const fake = new FakeService()
      .answer(
        "GET /v1/settings",
        { error: { code: "E187", message: "No settings." }, issues: [] },
        500,
      )
      .answer("GET /v1/system", { cores: 1, memory: 1, graphics: [], tier: "low", workers: 1 })
      .answer("GET /v1/engines", []);
    await open(fake);
    expect(await screen.findByText("No settings.")).toBeVisible();
    expect(screen.getByText(/graphics: none/)).toBeVisible();
  });
});

describe("Settings writes", () => {
  it("writes each run setting, the tier and every threshold", async () => {
    const { fake, current } = settingsService();
    const user = await open(fake);
    const field = async (name: string, value: string) => {
      const box = await screen.findByRole("textbox", { name });
      await user.clear(box);
      await user.type(box, `${value}{Enter}`);
      await waitFor(() => expect(screen.getByRole("textbox", { name })).toHaveValue(value));
    };
    await field("Runs at once", "2");
    expect(lastPut(fake)).toEqual({ max_concurrent_runs: 2 });
    await field("Time limit, in seconds", "1200");
    expect(lastPut(fake)).toEqual({ run_time_limit_s: 1200 });
    await field("Memory limit, in bytes", "4000000000");
    expect(lastPut(fake)).toEqual({ run_memory_limit_bytes: 4000000000 });
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Tier at the next start" }),
      "high",
    );
    await waitFor(() => expect(lastPut(fake)).toEqual({ tier: "high" }));
    await user.selectOptions(screen.getByRole("combobox", { name: "Tier at the next start" }), "");
    await waitFor(() => expect(lastPut(fake)).toEqual({ tier: null }));
    await field("Bottleneck at", "0.9");
    expect(lastPut(fake)).toEqual({
      finding_thresholds: { ...SETTINGS.finding_thresholds, bottleneck_utilization: 0.9 },
    });
    await field("Idle below", "0.2");
    await field("Likely range wider than", "0.05");
    await field("Shortest time judged, in seconds", "30");
    await field("Lowest rate judged, per second", "0.001");
    expect(current().finding_thresholds).toEqual({
      bottleneck_utilization: 0.9,
      idle_utilization: 0.2,
      relative_half_width: 0.05,
      min_time_s: 30,
      min_rate_per_s: 0.001,
    });
    // Leaving a field unchanged sends nothing; emptying it restores the default.
    const before = fake.requested("PUT", "/v1/settings").length;
    await user.click(screen.getByRole("textbox", { name: "Runs at once" }));
    await user.tab();
    expect(fake.requested("PUT", "/v1/settings")).toHaveLength(before);
    await user.clear(screen.getByRole("textbox", { name: "Runs at once" }));
    await user.tab();
    await waitFor(() => expect(lastPut(fake)).toEqual({ max_concurrent_runs: null }));
  });

  it("writes the idle timeout, and shows the service's refusal of one it cannot use", async () => {
    const { fake, current } = settingsService();
    const user = await open(fake);
    const box = await screen.findByRole("textbox", { name: IDLE_LABEL });
    await user.clear(box);
    await user.type(box, "5{Enter}");
    await waitFor(() => expect(current().idle_timeout_minutes).toBe(5));
    expect(lastPut(fake)).toEqual({ idle_timeout_minutes: 5 });
    expect(screen.getByRole("textbox", { name: IDLE_LABEL })).toHaveValue("5");
    expect(screen.getByText("= 5 min (1 to 10,080)")).toBeVisible();
    // The service's own E184 issue is shown, never text the interface makes up.
    const refusal: Issue = {
      code: "E184",
      severity: "error",
      component: null,
      path: "/idle_timeout_minutes",
      message:
        "The setting 'idle_timeout_minutes' must be a whole number of minutes from 1 to " +
        "10,080 (7 days).",
      hint: "Send a whole number of minutes from 1 to 10,080 (7 days), or null to use the default.",
    };
    fake.answer(
      "PUT /v1/settings",
      { error: { code: "E184", message: "The settings were not written." }, issues: [refusal] },
      400,
    );
    const again = screen.getByRole("textbox", { name: IDLE_LABEL });
    await user.clear(again);
    await user.type(again, "0{Enter}");
    expect(await screen.findByText(refusal.message)).toBeVisible();
    expect(lastPut(fake)).toEqual({ idle_timeout_minutes: 0 });
    await waitFor(() => expect(screen.getByRole("textbox", { name: IDLE_LABEL })).toHaveValue("5"));
  });

  it("restores the idle timeout's default when its field is emptied", async () => {
    const changed: Settings = { ...SETTINGS, idle_timeout_minutes: 120 };
    const { fake, current } = settingsService(changed);
    const user = await open(fake, changed);
    expect(screen.getByText("= 2 h (1 to 10,080)")).toBeVisible();
    await user.clear(screen.getByRole("textbox", { name: IDLE_LABEL }));
    await user.tab();
    await waitFor(() => expect(lastPut(fake)).toEqual({ idle_timeout_minutes: null }));
    await waitFor(() => expect(current().idle_timeout_minutes).toBe(30));
  });

  it("restores one threshold's default by leaving it out of the object sent", async () => {
    const changed: Settings = {
      ...SETTINGS,
      finding_thresholds: { ...SETTINGS.finding_thresholds, idle_utilization: 0.2 },
    };
    const { fake } = settingsService(changed);
    const user = await open(fake, changed);
    await user.clear(screen.getByRole("textbox", { name: "Idle below" }));
    await user.tab();
    await waitFor(() => expect(fake.requested("PUT", "/v1/settings")).toHaveLength(1));
    const { idle_utilization: _cleared, ...kept } = changed.finding_thresholds;
    expect(lastPut(fake)).toEqual({ finding_thresholds: kept });
  });

  it("writes every preference, whole, at once", async () => {
    const { fake, current } = settingsService();
    const user = await open(fake);
    await screen.findByText(/Detected/);
    await user.click(screen.getByRole("radio", { name: "Dark" }));
    await waitFor(() => expect(current().interface.theme).toBe("dark"));
    expect(lastPut(fake)).toEqual({ interface: { ...DEFAULT_PREFERENCES, theme: "dark" } });
    expect(document.documentElement.dataset.theme).toBe("dark");
    await user.click(screen.getByRole("radio", { name: "150%" }));
    await waitFor(() => expect(current().interface.text_size).toBe(150));
    await user.click(screen.getByRole("radio", { name: "Reduced" }));
    await waitFor(() => expect(current().interface.motion).toBe("reduced"));
    await user.click(screen.getByRole("checkbox", { name: "Colour-blind safe charts" }));
    await waitFor(() => expect(current().interface.colour_blind_charts).toBe(true));
    await user.click(screen.getByRole("checkbox", { name: "Ask before deleting" }));
    await waitFor(() => expect(current().interface.ask_before_deleting).toBe(false));
    await user.type(screen.getByRole("textbox", { name: "Undo steps" }), "300{Enter}");
    await waitFor(() => expect(current().interface.undo_steps).toBe(300));
    expect(screen.getByText("300 steps (100 to 10,000)")).toBeVisible();
    document.documentElement.removeAttribute("data-theme");
    document.documentElement.style.fontSize = "";
  });

  it("shows a refusal as the service's issues and the saved values again", async () => {
    const { fake } = settingsService();
    const user = await open(fake);
    const box = await screen.findByRole("textbox", { name: "Idle below" });
    await user.clear(box);
    await user.type(box, "lots{Enter}");
    expect(await screen.findByText("'idle_utilization' must be a number.")).toBeVisible();
    expect(lastPut(fake)).toEqual({
      finding_thresholds: { ...SETTINGS.finding_thresholds, idle_utilization: "lots" },
    });
    await waitFor(() =>
      expect(screen.getByRole("textbox", { name: "Idle below" })).toHaveValue("0.3"),
    );
  });

  it("sends one change at a time; one tried meanwhile is not sent, and a notice says so", async () => {
    const { fake } = settingsService();
    const user = await open(fake);
    await screen.findByText(/Detected/);
    const release = fake.holdWrites();
    await user.click(screen.getByRole("radio", { name: "Light" }));
    await waitFor(() => expect(fake.held).toBe(1));
    expect(screen.getByRole("radio", { name: "Dark" })).toHaveAttribute("aria-disabled", "true");
    await user.click(screen.getByRole("radio", { name: "Dark" }));
    expect(screen.getByText(SETTINGS_WAIT)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Restore all defaults" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    release();
    await waitFor(() => expect(screen.getByRole("radio", { name: "Light" })).toBeChecked());
    expect(screen.getByRole("radio", { name: "Dark" })).not.toBeChecked();
    expect(fake.requested("PUT", "/v1/settings")).toHaveLength(1);
    document.documentElement.removeAttribute("data-theme");
  });

  it("restores the preferences only, after a question whose focus starts on Cancel", async () => {
    const changed: Settings = {
      ...SETTINGS,
      tier: "high",
      interface: { ...SETTINGS.interface, first_start_seen: true, theme: "dark", undo_steps: 400 },
    };
    const { fake } = settingsService(changed);
    const user = await open(fake, changed);
    await user.click(await screen.findByRole("button", { name: "Restore all defaults" }));
    const dialog = screen.getByRole("dialog", { name: "Restore all defaults?" });
    expect(within(dialog).getByRole("button", { name: "Cancel" })).toHaveFocus();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
    await user.click(screen.getByRole("button", { name: "Restore all defaults" }));
    await user.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Cancel" }));
    expect(fake.requested("PUT", "/v1/settings")).toHaveLength(0);
    await user.click(screen.getByRole("button", { name: "Restore all defaults" }));
    await user.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Restore" }));
    await waitFor(() =>
      expect(lastPut(fake)).toEqual({
        interface: { ...DEFAULT_PREFERENCES, first_start_seen: true },
      }),
    );
    document.documentElement.removeAttribute("data-theme");
  });
});

describe("the helpers", () => {
  it("writes typed text as the service checks it", () => {
    expect(typed(" ")).toBeNull();
    expect(typed("2")).toBe(2);
    expect(typed("1e3")).toBe(1000);
    expect(typed("lots")).toBe("lots");
    expect(typed("9223372036854775807")).toBe("9223372036854775807");
    expect(bytesText(8 * 1024 ** 3)).toBe("8.59 GB");
    expect(bytesText(2e12)).toBe("2 TB");
    expect(bytesText(5e6)).toBe("5 MB");
    expect(bytesText(1500)).toBe("1.5 kB");
    expect(bytesText(12)).toBe("12 bytes");
  });
});
