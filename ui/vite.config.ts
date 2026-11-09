import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";
import { notices } from "./plugins/notices.ts";

const licence = fileURLToPath(new URL("../LICENSE", import.meta.url));

// The service serves the build at /v1/ui/ (spec 3 "Endpoints"), so every asset address is
// relative to index.html.
export default defineConfig({
  base: "./",
  plugins: [react(), notices(licence)],
  build: {
    outDir: "dist",
    emptyOutDir: true,
    // Fonts are files, never inlined as data: addresses, so the licence notices list them.
    assetsInlineLimit: 0,
    sourcemap: false,
  },
  server: {
    // The design tokens live in docs/design/tokens.json, outside ui/.
    fs: { allow: [".."] },
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.ts", "src/**/*.test.tsx", "plugins/**/*.test.ts"],
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    restoreMocks: true,
  },
});
