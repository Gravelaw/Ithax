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
import { AnswerOrder } from "../components/answerOrder";
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
  // An answer is taken against what is known now, not when it was sent: a read sent
  // before or during a write is not taken, the write's own answer being newer (CI and
  // review of pull request 200).
  const order = useRef(new AnswerOrder());
  const take = useCallback(
    async (request: Promise<ApiResult<SettingsBody>>, settle: (ok: boolean) => boolean) => {
      const result = await request;
      if (settle(result.kind === "ok") && result.kind === "ok") {
        setBody(result.data);
        applyPreferences(root, result.data.settings.interface);
      }
      return result;
    },
    [root],
  );
  const save = useCallback(
    (change: SettingsChange) => {
      const settle = order.current.write();
      return take(client.putSettings(change), settle);
    },
    [client, take],
  );
  const refresh = useCallback(() => {
    const settle = order.current.read();
    return take(client.getSettings(), settle);
  }, [client, take]);
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
