import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, sep } from "node:path";
import { describe, expect, it } from "vitest";
import {
  copyrightHolder,
  noticesText,
  packageAuthors,
  packageRoot,
  packagesJson,
  readPackage,
} from "./notices";

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
      authors: "not given",
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
      { name: "zeta", version: "1", license: "ISC", authors: "Z", text: "Z" },
      { name: "alpha", version: "2", license: "MIT", authors: "A", text: "A" },
    ]);
    expect(text.indexOf("alpha 2")).toBeLessThan(text.indexOf("zeta 1"));
    expect(text).toContain("Licence: MIT\n\nA\n");
  });

  it("names a package's authors without their addresses (pull request for issue 89)", () => {
    expect(packageAuthors({ author: "Ann Lee <ann@example.com> (https://ann.example)" })).toBe(
      "Ann Lee",
    );
    expect(packageAuthors({ author: { name: "Meta" } })).toBe("Meta");
    expect(
      packageAuthors({ author: "", contributors: ["Bo <b@c.d>", { name: "Cy" }, "<x@y.z>"] }),
    ).toBe("Bo, Cy");
    expect(packageAuthors({ maintainers: [{ name: "Dee" }] })).toBe("Dee");
    expect(packageAuthors({})).toBe("not given");
    expect(
      packageAuthors({}, "MIT License\n\nCopyright (c) Meta Platforms, Inc. and affiliates."),
    ).toBe("Meta Platforms, Inc. and affiliates.");
  });

  it("finds the copyright holder of a licence, skipping a template line", () => {
    expect(copyrightHolder("Copyright (c) 2019-2025 webkid GmbH")).toBe("webkid GmbH");
    expect(copyrightHolder("Copyright (c) 2017, Baidu Inc.")).toBe("Baidu Inc.");
    expect(
      copyrightHolder(
        "   Copyright [yyyy] [name of copyright owner]\n\nCopyright 2017-2026 The Apache Software Foundation",
      ),
    ).toBe("The Apache Software Foundation");
    expect(copyrightHolder("© 2020 Someone")).toBeNull();
    expect(copyrightHolder("      copyright license to reproduce, prepare")).toBeNull();
    expect(copyrightHolder("Copyright notice of the work")).toBeNull();
    expect(copyrightHolder("The above copyright notice and this permission notice")).toBeNull();
  });

  it("lists the packages with their authors for Help, sorted by name", () => {
    const rows = JSON.parse(
      packagesJson([
        { name: "zeta", version: "1", license: "ISC", authors: "Zed", text: "Z" },
        { name: "alpha", version: "2", license: "MIT", authors: "Al", text: "A" },
      ]),
    );
    expect(rows).toEqual([
      { name: "alpha", version: "2", licence: "MIT", authors: "Al" },
      { name: "zeta", version: "1", licence: "ISC", authors: "Zed" },
    ]);
  });
});
