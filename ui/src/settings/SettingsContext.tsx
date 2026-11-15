/**
 * The settings every screen reads, loaded once from `GET /v1/settings` and saved through
 * `PUT /v1/settings` (spec 3; AKS-119). Browser storage is not used: the page's origin, and
 * with it the storage, changes with the service's port.
 *
 * `issues` are the W220 issues of the finding thresholds as the service last reported
 * them; `refresh` reads both again (the Settings screen, when it opens, AKS-138), so a
 * change made in the file is seen.
 */
import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
} from "react";
import type { ApiClient, ApiResult } from "../api/client";
import type { Issue, Settings, SettingsBody, SettingsChange } from "../api/types";
import { oneAtATime } from "../components/oneAtATime";
import { applyPreferences } from "./preferences";

export interface SettingsState {
  settings: Settings;
  issues: Issue[];
  /** Writes `change`; on success the new settings apply at once. */
  save(change: SettingsChange): Promise<ApiResult<SettingsBody>>;
  /** Reads the settings again; on success they apply at once. */
  refresh(): Promise<ApiResult<SettingsBody>>;
}

const SettingsContext = createContext<SettingsState | null>(null);

export function SettingsProvider({
  client,
  initial,
  initialIssues = [],
  root,
  children,
}: {
  client: ApiClient;
  initial: Settings;
  initialIssues?: Issue[];
  root: HTMLElement;
  children: ReactNode;
}) {
  const [body, setBody] = useState<SettingsBody>({ settings: initial, issues: initialIssues });
  // Every read and write of the settings waits for the one before (review of pull request
  // 200): with one in flight, each answer is the settings at its turn, so taking every
  // answer in the order they arrive leaves the latest shown.
  const queue = useRef(oneAtATime());
  const take = useCallback(
    async (start: () => Promise<ApiResult<SettingsBody>>) => {
      const result = await queue.current(start);
      if (result.kind === "ok") {
        setBody(result.data);
        applyPreferences(root, result.data.settings.interface);
      }
      return result;
    },
    [root],
  );
  const save = useCallback(
    (change: SettingsChange) => take(() => client.putSettings(change)),
    [client, take],
  );
  const refresh = useCallback(() => take(() => client.getSettings()), [client, take]);
  const value = useMemo(
    () => ({ settings: body.settings, issues: body.issues, save, refresh }),
    [body, save, refresh],
  );
  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>;
}

export function useSettings(): SettingsState {
  const state = useContext(SettingsContext);
  if (state === null) throw new Error("useSettings needs a SettingsProvider");
  return state;
}
