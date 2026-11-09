/**
 * The app frame (`docs/design/design-system.md` "Spacing and layout"): the navigation
 * rail, the top bar and the current screen, and the first-start notice until it has been
 * seen.
 */
import { useEffect, useLayoutEffect, useState } from "react";
import type { ApiClient, ApiResult } from "../api/client";
import type { Project, SettingsBody } from "../api/types";
import { CanvasScreen } from "../canvas/CanvasScreen";
import { ServiceProblem } from "../components/ServiceProblem";
import { DataScreen } from "../data/DataScreen";
import { ExperimentScreen } from "../experiment/ExperimentScreen";
import { newLearning, useLearning } from "../learn/LearnContext";
import { RunMonitor } from "../monitor/RunMonitor";
import { ResultsScreen } from "../results/ResultsScreen";
import { BuildForm } from "../screens/BuildForm";
import { FirstStartNotice } from "../screens/FirstStartNotice";
import { Home } from "../screens/Home";
import { useSettings } from "../settings/SettingsContext";
import { SettingsScreen } from "../settings/SettingsScreen";
import { NAV_ITEMS, NavRail } from "./NavRail";
import { cycleRegion } from "./regions";
import { HOME, type Route, useRoute } from "./router";

function screenTitle(route: Route): string {
  if (route.screen === "build") return "Build a model";
  return NAV_ITEMS.find((item) => item.screen === route.screen)?.label ?? "Home";
}

export function App({ client }: { client: ApiClient }) {
  const [route, go] = useRoute();
  const { settings, save } = useSettings();
  const { start: startLesson } = useLearning();
  const [noticeOpen, setNoticeOpen] = useState(!settings.interface.first_start_seen);
  const [saveProblem, setSaveProblem] = useState<ApiResult<SettingsBody> | null>(null);
  const [project, setProject] = useState<Project | null>(null);
  // The top bar's slot where a screen puts its own tools (the Canvas: save state, undo, Run).
  const [tools, setTools] = useState<HTMLDivElement | null>(null);

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

  // Before the first paint, so F6 works as soon as the frame is visible.
  useLayoutEffect(() => {
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

  /** A project the Build form made: the Data screen with data, else the Canvas (spec 4). */
  const built = (made: Project, data: boolean) => {
    setProject(made);
    go({ screen: data ? "data" : "canvas", projectId: made.id });
  };

  const continueFromNotice = async () => {
    setNoticeOpen(false);
    const result = await save({ interface: { ...settings.interface, first_start_seen: true } });
    setSaveProblem(result.kind === "ok" ? null : result);
  };

  const shownProject = route.projectId !== null && project?.id === route.projectId ? project : null;
  const title =
    route.screen === "home" || route.screen === "build" || route.screen === "settings"
      ? screenTitle(route)
      : (shownProject?.name ?? screenTitle(route));

  return (
    <div className="frame">
      <NavRail route={route} projectId={project?.id ?? null} onGo={go} />
      <header className="topbar" data-region="top" tabIndex={-1}>
        <p className="topbar-title">{title}</p>
        <div className="topbar-tools" ref={setTools} />
        <div className="topbar-notices">
          <ServiceProblem result={saveProblem} />
        </div>
      </header>
      <main
        className={route.screen === "canvas" ? "main main-canvas" : "main"}
        data-region="main"
        tabIndex={-1}
      >
        {route.screen === "home" ? (
          <Home
            client={client}
            onOpen={open}
            onBuild={() => go({ screen: "build", projectId: null })}
            onLesson={(made, template, lesson) => {
              startLesson(newLearning(made.id, template, lesson));
              open(made);
            }}
          />
        ) : null}
        {route.screen === "build" ? (
          <BuildForm client={client} onCreated={built} onBack={() => go(HOME)} />
        ) : null}
        {route.screen === "canvas" ? (
          <CanvasScreen client={client} project={shownProject} toolbar={tools} onGo={go} />
        ) : null}
        {route.screen === "data" ? (
          <DataScreen client={client} project={shownProject} toolbar={tools} onGo={go} />
        ) : null}
        {route.screen === "experiment" ? (
          <ExperimentScreen client={client} project={shownProject} toolbar={tools} onGo={go} />
        ) : null}
        {route.screen === "monitor" ? (
          <RunMonitor client={client} project={shownProject} runId={route.runId} onGo={go} />
        ) : null}
        {route.screen === "results" ? (
          <ResultsScreen client={client} project={shownProject} runId={route.runId} onGo={go} />
        ) : null}
        {route.screen === "settings" ? <SettingsScreen client={client} /> : null}
      </main>
      {noticeOpen ? <FirstStartNotice onContinue={() => void continueFromNotice()} /> : null}
    </div>
  );
}
