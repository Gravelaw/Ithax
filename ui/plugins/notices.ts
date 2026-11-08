/**
 * A Vite plugin that ships the licences with the built interface (AKS-119).
 *
 * The bundled fonts are under the SIL Open Font License 1.1, which asks that the licence
 * travel with the font files, and the MIT, ISC and BSD licences of the bundled code ask for
 * their notices too. At build time this plugin lists every npm package whose modules went
 * into the bundle, and writes `THIRD-PARTY-NOTICES.txt` beside `index.html` with each
 * package's name, version, licence and licence text. It also copies the product's own
 * licence, the repository's `LICENSE` (GNU AGPL version 3), as `LICENSE.txt`, which the
 * first-start notice and Settings, About point to.
 */
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join, sep } from "node:path";
import type { Plugin } from "vite";

export interface BundledPackage {
  name: string;
  version: string;
  license: string;
  text: string;
}

const LICENCE_FILE = /^(licen[cs]e|copying)(\.(md|txt))?$/i;

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
  };
  const file = readdirSync(root).find((name) => LICENCE_FILE.test(name));
  if (file === undefined) {
    throw new Error(`${manifest.name} has no licence file to ship with the interface`);
  }
  return {
    name: manifest.name,
    version: manifest.version,
    license: manifest.license ?? "UNKNOWN",
    text: readFileSync(join(root, file), "utf8").trim(),
  };
}

/** The notices file for `packages`, sorted by name. */
export function noticesText(packages: BundledPackage[]): string {
  const sorted = [...packages].sort((a, b) => a.name.localeCompare(b.name));
  const parts = sorted.map(
    (item) => `${item.name} ${item.version}\nLicence: ${item.license}\n\n${item.text}\n`,
  );
  return [
    "Third-party software bundled with the lcsim interface",
    "",
    ...parts.flatMap((part) => ["=".repeat(72), part]),
  ].join("\n");
}

export function notices(productLicence: string): Plugin {
  return {
    name: "lcsim-notices",
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
      this.emitFile({
        type: "asset",
        fileName: "THIRD-PARTY-NOTICES.txt",
        source: noticesText(outermost.map(readPackage)),
      });
      this.emitFile({
        type: "asset",
        fileName: "LICENSE.txt",
        source: readFileSync(productLicence, "utf8"),
      });
    },
  };
}
