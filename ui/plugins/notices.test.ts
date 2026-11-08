import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, sep } from "node:path";
import { describe, expect, it } from "vitest";
import { noticesText, packageRoot, readPackage } from "./notices";

const modules = `${sep}app${sep}node_modules${sep}`;

describe("the notices plugin", () => {
  it("finds the package of a bundled module, scoped or not", () => {
    expect(packageRoot(`${modules}react${sep}index.js`)).toBe(`${modules}react`);
    expect(packageRoot(`${modules}@xyflow${sep}react${sep}dist${sep}a.js`)).toBe(
      `${modules}@xyflow${sep}react`,
    );
    expect(packageRoot(`${modules}a${sep}node_modules${sep}b${sep}x.js`)).toBe(
      `${modules}a${sep}node_modules${sep}b`,
    );
    expect(packageRoot(`${sep}app${sep}src${sep}main.tsx`)).toBeNull();
    expect(packageRoot(`${modules}@scope`)).toBeNull();
  });

  it("reads a package's licence, and refuses one without a licence file", () => {
    const root = mkdtempSync(join(tmpdir(), "notices-"));
    writeFileSync(
      join(root, "package.json"),
      JSON.stringify({ name: "x", version: "1.0.0", license: "MIT" }),
    );
    writeFileSync(join(root, "LICENSE.md"), "\nMIT License\n");
    expect(readPackage(root)).toEqual({
      name: "x",
      version: "1.0.0",
      license: "MIT",
      text: "MIT License",
    });
    const bare = join(root, "bare");
    mkdirSync(bare);
    writeFileSync(join(bare, "package.json"), JSON.stringify({ name: "bare", version: "2.0.0" }));
    expect(() => readPackage(bare)).toThrow("bare has no licence file");
    writeFileSync(join(bare, "COPYING"), "text");
    expect(readPackage(bare).license).toBe("UNKNOWN");
  });

  it("ships a package's NOTICE file after its licence (Apache-2.0, section 4(d))", () => {
    const root = mkdtempSync(join(tmpdir(), "notices-"));
    writeFileSync(
      join(root, "package.json"),
      JSON.stringify({ name: "e", version: "6.1.0", license: "Apache-2.0" }),
    );
    writeFileSync(join(root, "LICENSE"), "Apache License\n");
    writeFileSync(join(root, "NOTICE"), "\nApache ECharts\nCopyright\n");
    expect(readPackage(root).text).toBe("Apache License\n\nApache ECharts\nCopyright");
    mkdirSync(join(root, "licenses"));
    writeFileSync(join(root, "licenses", "LICENSE-d3"), "BSD 3-Clause\n");
    expect(readPackage(root).text).toBe(
      "Apache License\n\nApache ECharts\nCopyright\n\nlicenses/LICENSE-d3:\n\nBSD 3-Clause",
    );
  });

  it("writes the notices sorted by package name", () => {
    const text = noticesText([
      { name: "zeta", version: "1", license: "ISC", text: "Z" },
      { name: "alpha", version: "2", license: "MIT", text: "A" },
    ]);
    expect(text.indexOf("alpha 2")).toBeLessThan(text.indexOf("zeta 1"));
    expect(text).toContain("Licence: MIT\n\nA\n");
  });
});
