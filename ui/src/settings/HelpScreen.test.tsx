/**
 * Help, "Open source licences" (issue 89): every package and engine with its licence and
 * authors, from `GET /v1/licences` and the interface's own `third-party.json`.
 */
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { LicencedPart, Licences } from "../api/types";
import { errorBody, FakeService } from "../test/fakes";
import { CRATES_ELSEWHERE, HelpScreen } from "./HelpScreen";

const LICENCES: Licences = {
  product: {
    name: "Ithax",
    version: "0.1.0",
    licence: "AGPL-3.0-only",
    source: "https://github.com/Gravelaw/Ithax",
  },
  engines: [
    {
      name: "simpy",
      version: "4.1.2",
      licence: "MIT",
      distribution: "simpy",
      authors: "Ontje Lünsdorf, Stefan Scherfke",
    },
  ],
  python: {
    name: "CPython",
    version: "3.13.16",
    licence: "PSF-2.0",
    bundled: [{ name: "OpenSSL", version: "3.5.9", licence: "Apache-2.0" }],
  },
  packages: [{ name: "numpy", version: "2.5.4", licence: "BSD-3-Clause", authors: "NumPy" }],
  crates: [],
};

const INTERFACE: LicencedPart[] = [
  { name: "react", version: "19.2.0", licence: "MIT", authors: "not given" },
];

function table(name: string): HTMLElement {
  return screen.getByRole("table", { name });
}

describe("Help", () => {
  it("lists every package and engine with its licence and authors", async () => {
    const fake = new FakeService()
      .answer("GET /v1/licences", LICENCES)
      .answer("GET /v1/ui/third-party.json", INTERFACE);
    render(<HelpScreen client={fake.client()} />);
    expect(await screen.findByRole("heading", { name: "Open source licences" })).toBeVisible();
    const engines = await screen.findByRole("table", { name: "Engines" });
    expect(within(engines).getByRole("row", { name: /simpy 4\.1\.2 MIT Ontje/ })).toBeVisible();
    expect(within(table("Libraries built into Python")).getByText("OpenSSL")).toBeVisible();
    expect(within(table("Python")).getByText("PSF-2.0")).toBeVisible();
    const packages = table("Python packages");
    expect(
      within(packages).getByRole("row", { name: "numpy 2.5.4 BSD-3-Clause NumPy" }),
    ).toBeVisible();
    // A library built into Python has no authors column.
    expect(within(table("Libraries built into Python")).queryByText("Authors")).toBeNull();
    const interfaceTable = await screen.findByRole("table", { name: "Interface packages" });
    expect(within(interfaceTable).getByText("react")).toBeVisible();
    expect(screen.getByText(CRATES_ELSEWHERE)).toBeVisible();
    expect(screen.getByText(/0\.1\.0 is free software under AGPL-3\.0-only/)).toBeVisible();
    expect(screen.getByRole("link", { name: "https://github.com/Gravelaw/Ithax" })).toBeVisible();
  });

  it("lists the desktop shell's crates when the package names them", async () => {
    const crates = [{ name: "tauri", version: "2.11.1", licence: "Apache-2.0 OR MIT" }];
    const fake = new FakeService()
      .answer("GET /v1/licences", { ...LICENCES, crates })
      .answer("GET /v1/ui/third-party.json", INTERFACE);
    render(<HelpScreen client={fake.client()} />);
    const shell = await screen.findByRole("table", { name: "Desktop shell crates" });
    expect(within(shell).getByText("tauri")).toBeVisible();
    expect(screen.queryByText(CRATES_ELSEWHERE)).toBeNull();
  });

  it("shows the service's refusal, and the interface's list without it", async () => {
    const fake = new FakeService()
      .answer("GET /v1/licences", errorBody("E900", "Broken."), 500)
      .answer("GET /v1/ui/third-party.json", INTERFACE);
    render(<HelpScreen client={fake.client()} />);
    expect(await screen.findByText(/Broken\./)).toBeVisible();
    expect(await screen.findByRole("table", { name: "Interface packages" })).toBeVisible();
    expect(screen.queryByRole("table", { name: "Engines" })).toBeNull();
  });
});
