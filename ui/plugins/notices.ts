/**
 * A Vite plugin that ships the licences with the built interface (AKS-119).
 *
 * The bundled fonts are under the SIL Open Font License 1.1, which asks that the licence
 * travel with the font files, and the MIT, ISC and BSD licences of the bundled code ask for
 * their notices too. At build time this plugin lists every npm package whose modules went
 * into the bundle, and writes `THIRD-PARTY-NOTICES.txt` beside `index.html` with each
 * package's name, version, licence and licence text, followed by the package's `NOTICE` file
 * when it has one (Apache-2.0, section 4(d), asks that it travel with the work; Apache
 * ECharts has one, AKS-120) and the files of its `licenses/` folder (the licences of code it
 * embeds). It also copies the product's own
 * licence, the repository's `LICENSE` (GNU AGPL version 3), as `LICENSE.txt`, which the
 * first-start notice and Settings, About point to. The same packages, with their authors,
 * go to `third-party.json`, which Help, "Open source licences" lists (#89).
 */
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join, sep } from "node:path";
import type { Plugin } from "vite";

export interface BundledPackage {
  name: string;
  version: string;
  license: string;
  /** The people its `package.json` names, without addresses, or "not given". */
  authors: string;
  text: string;
}

/** A person as `package.json` gives one, a string or an object. */
type Person = string | { name?: string };

/** A person's name, without the `<mail>` and `(url)` a string may add. */
function personName(person: Person): string {
  const name = typeof person === "string" ? person.replace(/<[^>]*>|\([^)]*\)/g, "") : person.name;
  return (name ?? "").trim();
}

/**
 * The holder in the first copyright line of a licence or notice text, "Meta Platforms, Inc.
 * and affiliates." in "Copyright (c) Meta Platforms, Inc. and affiliates."; a template line
 * with brackets, as in the Apache-2.0 appendix, is skipped. `null` when there is none.
 */
export function copyrightHolder(text: string): string | null {
  for (const line of text.split("\n")) {
    // "Copyright", then "(c)" or "©", a year or both: a line of the licence's own text
    // ("copyright license to reproduce") has neither.
    const match = /^\s*Copyright\s+(\([cC]\)\s*|©\s*)?(\d[\d\s,–-]*\s)?(.+)$/.exec(line);
    const holder = match?.[3]?.trim().replace(/^,\s*/, "");
    const marked = match?.[1] !== undefined || match?.[2] !== undefined;
    if (holder && marked && !line.includes("[")) return holder;
  }
  return null;
}

/**
 * The authors of a package: its `author`, else its `contributors`, else `maintainers`,
 * else the copyright holder its licence or notice names (`text`), else "not given".
 */
export function packageAuthors(
  manifest: {
    author?: Person;
    contributors?: Person[];
    maintainers?: Person[];
  },
  text = "",
): string {
  for (const people of [[manifest.author], manifest.contributors, manifest.maintainers]) {
    const names = (people ?? []).flatMap((person) =>
      person === undefined || personName(person) === "" ? [] : [personName(person)],
    );
    if (names.length > 0) return names.join(", ");
  }
  return copyrightHolder(text) ?? "not given";
}

const LICENCE_FILE = /^(licen[cs]e|copying)(\.(md|txt))?$/i;
const NOTICE_FILE = /^notice(\.(md|txt))?$/i;

/** The folder of the npm package a module id belongs to, or `null` for the app's own code. */
export function packageRoot(id: string): string | null {
  const marker = `${sep}node_modules${sep}`;
  const at = id.lastIndexOf(marker);
  if (at < 0) return null;
  const rest = id.slice(at + marker.length).split(sep);
  const depth = rest[0]?.startsWith("@") ? 2 : 1;
  if (rest.length <= depth) return null;
  return id.slice(0, at + marker.length) + rest.slice(0, depth).join(sep);
}

/** A package's name, version, licence and licence text, read from its folder. */
export function readPackage(root: string): BundledPackage {
  const manifest = JSON.parse(readFileSync(join(root, "package.json"), "utf8")) as {
    name: string;
    version: string;
    license?: string;
    author?: Person;
    contributors?: Person[];
    maintainers?: Person[];
  };
  const file = readdirSync(root).find((name) => LICENCE_FILE.test(name));
  if (file === undefined) {
    throw new Error(`${manifest.name} has no licence file to ship with the interface`);
  }
  const parts = [readFileSync(join(root, file), "utf8").trim()];
  const notice = readdirSync(root).find((name) => NOTICE_FILE.test(name));
  if (notice !== undefined) parts.push(readFileSync(join(root, notice), "utf8").trim());
  // The licences of embedded subcomponents that the licence points to (ECharts embeds d3
  // code under BSD-3-Clause, in `licenses/LICENSE-d3`).
  const folder = join(root, "licenses");
  if (existsSync(folder)) {
    for (const name of readdirSync(folder).sort()) {
      parts.push(`licenses/${name}:\n\n${readFileSync(join(folder, name), "utf8").trim()}`);
    }
  }
  return {
    name: manifest.name,
    version: manifest.version,
    license: manifest.license ?? "UNKNOWN",
    authors: packageAuthors(manifest, parts.join("\n\n")),
    text: parts.join("\n\n"),
  };
}

/** The notices file for `packages`, sorted by name. */
export function noticesText(packages: BundledPackage[]): string {
  const sorted = [...packages].sort((a, b) => a.name.localeCompare(b.name));
  const parts = sorted.map(
    (item) => `${item.name} ${item.version}\nLicence: ${item.license}\n\n${item.text}\n`,
  );
  return [
    "Third-party software bundled with the Ithax interface",
    "",
    ...parts.flatMap((part) => ["=".repeat(72), part]),
  ].join("\n");
}

/** `third-party.json`: each package's name, version, licence and authors, by name. */
export function packagesJson(packages: BundledPackage[]): string {
  const sorted = [...packages].sort((a, b) => a.name.localeCompare(b.name));
  const rows = sorted.map(({ name, version, license, authors }) => ({
    name,
    version,
    licence: license,
    authors,
  }));
  return `${JSON.stringify(rows, null, 2)}\n`;
}

export function notices(productLicence: string): Plugin {
  return {
    name: "ithax-notices",
    apply: "build",
    generateBundle() {
      const roots = new Set<string>();
      for (const id of this.getModuleIds()) {
        const root = packageRoot(id.replace(/\?.*$/, "").replace(/\//g, sep));
        if (root !== null && existsSync(join(root, "package.json"))) roots.add(root);
      }
      // A package's own folder may hold nested package.json files (exports maps); keep the
      // outermost, which is the package.
      const outermost = [...roots].filter(
        (root) => ![...roots].some((other) => other !== root && root.startsWith(other + sep)),
      );
      const packages = outermost.map(readPackage);
      this.emitFile({
        type: "asset",
        fileName: "THIRD-PARTY-NOTICES.txt",
        source: noticesText(packages),
      });
      this.emitFile({
        type: "asset",
        fileName: "third-party.json",
        source: packagesJson(packages),
      });
      this.emitFile({
        type: "asset",
        fileName: "LICENSE.txt",
        source: readFileSync(productLicence, "utf8"),
      });
    },
  };
}
