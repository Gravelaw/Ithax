import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { designTokens, installTheme, THEME_STYLE_ID, themeCss } from "./tokens";

describe("design tokens", () => {
  it("defines every token of both themes as a CSS variable", () => {
    const css = themeCss();
    for (const theme of ["light", "dark"] as const) {
      for (const [name, value] of Object.entries(designTokens.themes[theme])) {
        expect(css).toContain(`--color-${name}: ${value};`);
      }
    }
  });

  it("gives both themes the same tokens", () => {
    expect(Object.keys(designTokens.themes.dark).sort()).toEqual(
      Object.keys(designTokens.themes.light).sort(),
    );
  });

  it("follows the system's preference in the system theme", () => {
    const css = themeCss({ themes: { light: { text: "#000" }, dark: { text: "#fff" } } });
    expect(css).toBe(
      [
        ':root, :root[data-theme="light"] { color-scheme: light; --color-text: #000; }',
        ':root[data-theme="dark"] { color-scheme: dark; --color-text: #fff; }',
        '@media (prefers-color-scheme: dark) { :root[data-theme="system"] { color-scheme: dark; --color-text: #fff; } }',
      ].join("\n"),
    );
  });

  it("installs the style sheet once", () => {
    installTheme(document);
    installTheme(document);
    expect(document.querySelectorAll(`#${THEME_STYLE_ID}`)).toHaveLength(1);
  });

  it("is the only place colours are written: the code names tokens", () => {
    const sources: string[] = [];
    const walk = (folder: string) => {
      for (const entry of readdirSync(folder, { withFileTypes: true })) {
        const path = join(folder, entry.name);
        if (entry.isDirectory()) walk(path);
        else if (/\.(css|tsx?)$/.test(entry.name) && !/\.test\.tsx?$/.test(entry.name)) {
          sources.push(path);
        }
      }
    };
    walk(join(__dirname, ".."));
    const raw = sources.filter((path) => /#[0-9a-fA-F]{3,8}\b/.test(readFileSync(path, "utf8")));
    expect(raw).toEqual([]);
  });
});
