/**
 * Starting the page: the settings first (`GET /v1/settings`), since every screen reads
 * them, then the app. While they load the page says it is connecting; if the service does
 * not answer it says so, with Try again (`docs/design/flows.md` "Error and edge paths").
 */
import { useCallback, useEffect, useState } from "react";
import type { ApiClient, ApiResult } from "../api/client";
import type { SettingsBody } from "../api/types";
import { ServiceProblem } from "../components/ServiceProblem";
import { LearnProvider } from "../learn/LearnContext";
import { applyPreferences } from "../settings/preferences";
import { SettingsProvider } from "../settings/SettingsContext";
import { App } from "./App";

export const CONNECTING = "Connecting to the engine service…";
export const NOT_ANSWERING = "The engine service did not answer.";
export const NO_TOKEN =
  "This page needs the engine service's token. Open the interface with the launcher: python -m lcsim.launcher";

export function Boot({ client, root }: { client: ApiClient; root: HTMLElement }) {
  const [loaded, setLoaded] = useState<ApiResult<SettingsBody> | null>(null);

  const load = useCallback(async () => {
    setLoaded(null);
    const result = await client.getSettings();
    if (result.kind === "ok") applyPreferences(root, result.data.settings.interface);
    setLoaded(result);
  }, [client, root]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loaded === null) {
    return (
      <p className="splash" role="status">
        {CONNECTING}
      </p>
    );
  }
  if (loaded.kind !== "ok") {
    return (
      <div className="splash">
        {loaded.kind === "failed" ? <p role="alert">{NOT_ANSWERING}</p> : null}
        <ServiceProblem result={loaded.kind === "refused" ? loaded : null} />
        <button type="button" className="primary" onClick={() => void load()}>
          Try again
        </button>
      </div>
    );
  }
  return (
    <SettingsProvider
      client={client}
      initial={loaded.data.settings}
      initialIssues={loaded.data.issues}
      root={root}
    >
      <LearnProvider>
        <App client={client} />
      </LearnProvider>
    </SettingsProvider>
  );
}

export function NoToken() {
  return (
    <p className="splash" role="alert">
      {NO_TOKEN}
    </p>
  );
}
