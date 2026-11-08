/**
 * The end-to-end fixtures: `service`, a real engine service per test, and a `page` that
 * refuses every request leaving the machine (spec 0 principle 6: nothing is fetched from
 * the network at run time) and records the requests the interface makes to the service.
 */
import { test as base, expect } from "@playwright/test";
import { type Service, startService } from "./service";

export interface SentRequest {
  method: string;
  path: string;
  headers: Record<string, string>;
}

export const test = base.extend<{ service: Service; sent: SentRequest[]; outside: string[] }>({
  // biome-ignore lint/correctness/noEmptyPattern: Playwright's fixture signature
  service: async ({}, use) => {
    const service = await startService();
    try {
      await use(service);
    } finally {
      await service.stop();
    }
  },
  sent: async ({ page }, use) => {
    const sent: SentRequest[] = [];
    page.on("request", (request) => {
      const url = new URL(request.url());
      if (url.pathname.startsWith("/v1/") && !url.pathname.startsWith("/v1/ui/")) {
        sent.push({ method: request.method(), path: url.pathname, headers: request.headers() });
      }
    });
    await use(sent);
  },
  outside: async ({ context }, use) => {
    const outside: string[] = [];
    await context.route("**/*", async (route) => {
      const host = new URL(route.request().url()).hostname;
      if (host === "127.0.0.1" || host === "localhost") await route.continue();
      else {
        outside.push(route.request().url());
        await route.abort();
      }
    });
    await use(outside);
    expect(outside, "requests that left the machine").toEqual([]);
  },
});

export { expect };
