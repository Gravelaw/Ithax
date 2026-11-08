/**
 * Starts a real engine service for an end-to-end test, the way a user does: through the
 * launcher (`python -m lcsim.launcher --print-url`), with temporary configuration and data
 * folders and the built interface (`ui/dist`), and stops it after the test with SIGTERM,
 * waiting until `service.json` is gone (spec 3 "Discovery").
 *
 * The Python is `LCSIM_PYTHON`, else the repository's `.venv`, else `python3`.
 */
import { execFileSync } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const UI = dirname(dirname(fileURLToPath(import.meta.url)));
const REPOSITORY = dirname(UI);

export interface Service {
  /** The address the launcher printed: `http://127.0.0.1:<port>/v1/ui/#token=<token>`. */
  url: string;
  origin: string;
  token: string;
  configDir: string;
  dataDir: string;
  /** Requests a test makes itself, as a script would. */
  api(method: string, path: string, body?: unknown): Promise<{ status: number; body: unknown }>;
  stop(): Promise<void>;
}

export function python(): string {
  if (process.env.LCSIM_PYTHON) return process.env.LCSIM_PYTHON;
  const venv = join(
    REPOSITORY,
    ".venv",
    process.platform === "win32" ? "Scripts" : "bin",
    "python",
  );
  return existsSync(venv) ? venv : "python3";
}

export async function startService(): Promise<Service> {
  const dist = join(UI, "dist");
  if (!existsSync(join(dist, "index.html"))) {
    throw new Error("ui/dist has no index.html: run `npm run build` before the end-to-end tests");
  }
  const folder = mkdtempSync(join(tmpdir(), "lcsim-e2e-"));
  const configDir = join(folder, "config");
  const dataDir = join(folder, "data");
  const printed = execFileSync(
    python(),
    [
      "-m",
      "lcsim.launcher",
      "--config-dir",
      configDir,
      "--data-dir",
      dataDir,
      "--ui-dir",
      dist,
      "--idle-minutes",
      "10",
      "--print-url",
    ],
    { encoding: "utf8", timeout: 60_000 },
  );
  const url = printed.trim().split("\n").pop() ?? "";
  const { port, token, pid } = JSON.parse(readFileSync(join(configDir, "service.json"), "utf8"));
  if (url !== `http://127.0.0.1:${port}/v1/ui/#token=${token}`) {
    throw new Error(`the launcher printed '${url}'`);
  }
  const origin = `http://127.0.0.1:${port}`;
  return {
    url,
    origin,
    token,
    configDir,
    dataDir,
    async api(method, path, body) {
      const response = await fetch(origin + path, {
        method,
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      });
      return { status: response.status, body: await response.json() };
    },
    async stop() {
      try {
        process.kill(pid, "SIGTERM");
      } catch {
        // Already gone.
      }
      const deadline = Date.now() + 30_000;
      while (existsSync(join(configDir, "service.json")) && Date.now() < deadline) {
        await new Promise((resolve) => setTimeout(resolve, 100));
      }
      const left = existsSync(join(configDir, "service.json"));
      rmSync(folder, { recursive: true, force: true });
      if (left) throw new Error("the service did not remove service.json when stopped");
    },
  };
}
