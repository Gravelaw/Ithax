/**
 * The design tokens as CSS custom properties (`docs/design/design-system.md`, "Colour
 * tokens": "Interface code reads token names, never raw colours").
 *
 * `docs/design/tokens.json` is the single source; each token becomes `--color-<name>`, for
 * the light theme on `:root` and `[data-theme="light"]`, for the dark theme on
 * `[data-theme="dark"]`, and on `[data-theme="system"]` when the system prefers dark.
 */
import tokens from "../../../docs/design/tokens.json";

export type ThemeName = "light" | "dark";
export type TokenSet = Record<string, string>;

export interface DesignTokens {
  themes: Record<ThemeName, TokenSet>;
}

export const designTokens: DesignTokens = tokens as DesignTokens;

function declarations(set: TokenSet): string {
  return Object.entries(set)
    .map(([name, value]) => `--color-${name}: ${value};`)
    .join(" ");
}

/** The style sheet that defines every token in both themes. */
export function themeCss(source: DesignTokens = designTokens): string {
  const light = declarations(source.themes.light);
  const dark = declarations(source.themes.dark);
  return [
    `:root, :root[data-theme="light"] { color-scheme: light; ${light} }`,
    `:root[data-theme="dark"] { color-scheme: dark; ${dark} }`,
    `@media (prefers-color-scheme: dark) { :root[data-theme="system"] { color-scheme: dark; ${dark} } }`,
  ].join("\n");
}

export const THEME_STYLE_ID = "lcsim-tokens";

/** Adds the token style sheet to `document` once. */
export function installTheme(document: Document): void {
  if (document.getElementById(THEME_STYLE_ID) !== null) return;
  const style = document.createElement("style");
  style.id = THEME_STYLE_ID;
  style.textContent = themeCss();
  document.head.append(style);
}
