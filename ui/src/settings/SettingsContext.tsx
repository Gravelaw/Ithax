/**
 * The settings every screen reads, loaded once from `GET /v1/settings` and saved through
 * `PUT /v1/settings` (spec 3; AKS-119). Browser storage is not used: the page's origin, and
 * with it the storage, changes with the service's port.
 */
import { createContext, type ReactNode, useCallback, useContext, useMemo, useState } from "react";
import type { ApiClient, ApiResult } from "../api/client";
import type { Settings, SettingsBody, SettingsChange } from "../api/types";
import { applyPreferences } from "./preferences";

export interface SettingsState {
  settings: Settings;
  /** Writes `change`; on success the new settings apply at once. */
  save(change: SettingsChange): Promise<ApiResult<SettingsBody>>;
}

const SettingsContext = createContext<SettingsState | null>(null);

export function SettingsProvider({
  client,
  initial,
  root,
  children,
}: {
  client: ApiClient;
  initial: Settings;
  root: HTMLElement;
  children: ReactNode;
}) {
  const [settings, setSettings] = useState(initial);
  const save = useCallback(
    async (change: SettingsChange) => {
      const result = await client.putSettings(change);
      if (result.kind === "ok") {
        setSettings(result.data.settings);
        applyPreferences(root, result.data.settings.interface);
      }
      return result;
    },
    [client, root],
  );
  const value = useMemo(() => ({ settings, save }), [settings, save]);
  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>;
}

export function useSettings(): SettingsState {
  const state = useContext(SettingsContext);
  if (state === null) throw new Error("useSettings needs a SettingsProvider");
  return state;
}
