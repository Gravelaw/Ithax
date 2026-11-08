/**
 * The app frame (`docs/design/design-system.md` "Spacing and layout"): the navigation
 * rail, the top bar and the current screen, and the first-start notice until it has been
 * seen. Screens later tickets build are placeholders that keep their route.
 */
import { useEffect, useState } from "react";
import type { ApiClient, ApiResult } from "../api/client";
import type { Project, SettingsBody } from "../api/types";
import { ServiceProblem } from "../components/ServiceProblem";
import { FirstStartNotice } from "../screens/FirstStartNotice";
import { Home } from "../screens/Home";
import { CanvasPlaceholder, ScreenPlaceholder, SettingsPlaceholder } from "../screens/Placeholders";
import { useSettings } from "../settings/SettingsContext";
import { NAV_ITEMS, NavRail } from "./NavRail";
import { cycleRegion } from "./regions";
import { HOME, type Route, useRoute } from "./router";

function screenTitle(route: Route): string {
  return NAV_ITEMS.find((item) => item.screen === route.screen)?.label ?? "Home";
}

export function App({ client }: { client: ApiClient }) {
  const [route, go] = useRoute();
  const { settings, save } = useSettings();
  const [noticeOpen, setNoticeOpen] = useState(!settings.interface.first_start_seen);
  const [saveProblem, setSaveProblem] = useState<ApiResult<SettingsBody> | null>(null);
  const [project, setProject] = useState<Project | null>(null);

  // A route that names a project (after a reload) finds it in the project list.
  useEffect(() => {
    const wanted = route.projectId;
    if (wanted === null || project?.id === wanted) return;
    let current = true;
    void client.listProjects().then((listed) => {
      if (!current) return;
      const found = listed.kind === "ok" ? listed.data.find((item) => item.id === wanted) : null;
      if (found) setProject(found);
      else go(HOME);
    });
    return () => {
      current = false;
    };
  }, [client, route.projectId, project, go]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "F6") return;
      event.preventDefault();
      cycleRegion(document, event.shiftKey);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  const open = (opened: Project) => {
    setProject(opened);
    go({ screen: "canvas", projectId: opened.id });
  };

  const continueFromNotice = async () => {
    setNoticeOpen(false);
    const result = await save({ interface: { ...settings.interface, first_start_seen: true } });
    setSaveProblem(result.kind === "ok" ? null : result);
  };

  const shownProject = route.projectId !== null && project?.id === route.projectId ? project : null;
  const title =
    route.screen === "home" || route.screen === "settings"
      ? screenTitle(route)
      : (shownProject?.name ?? screenTitle(route));

  return (
    <div className="frame">
      <NavRail route={route} projectId={project?.id ?? null} onGo={go} />
      <header className="topbar" data-region="top" tabIndex={-1}>
        <p className="topbar-title">{title}</p>
        <div className="topbar-notices">
          <ServiceProblem result={saveProblem} />
        </div>
      </header>
      <main className="main" data-region="main" tabIndex={-1}>
        {route.screen === "home" ? <Home client={client} onOpen={open} /> : null}
        {route.screen === "canvas" ? (
          <CanvasPlaceholder client={client} project={shownProject} />
        ) : null}
        {route.screen === "settings" ? <SettingsPlaceholder /> : null}
        {route.screen !== "home" && route.screen !== "canvas" && route.screen !== "settings" ? (
          <ScreenPlaceholder title={screenTitle(route)} />
        ) : null}
      </main>
      {noticeOpen ? <FirstStartNotice onContinue={() => void continueFromNotice()} /> : null}
    </div>
  );
}
