/**
 * The app frame (`docs/design/design-system.md` "Spacing and layout"): the navigation
 * rail, the top bar and the current screen, and the first-start notice until it has been
 * seen.
 */
import { useEffect, useLayoutEffect, useRef, useState } from "react";
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
import type { ProjectActions } from "./projectActions";
import { cycleRegion } from "./regions";
import { HOME, type Route, useRoute } from "./router";

function screenTitle(route: Route): string {
  if (route.screen === "build") return "Build a model";
  return NAV_ITEMS.find((item) => item.screen === route.screen)?.label ?? "Home";
}

export function App({ client }: { client: ApiClient }) {
  const [route, go] = useRoute();
  const { settings, save } = useSettings();
  const { start: startLesson, exit: exitLesson, learning } = useLearning();
  const forgetLesson = useLessonStep(client, learning?.projectId ?? null, learning?.step ?? null);
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

  /**
   * Every way a project is opened goes through here or `built`, which note the time so
   * Recent projects lists it first (#97; review of pull request 201).
   */
  const open = (opened: Project) => {
    void client.changeProject(opened.id, { opened: true });
    setProject(opened);
    go({ screen: "canvas", projectId: opened.id });
  };

  /** A project the Build form made: the Data screen with data, else the Canvas (spec 4). */
  const built = (made: Project, data: boolean) => {
    void client.changeProject(made.id, { opened: true });
    setProject(made);
    go({ screen: data ? "data" : "canvas", projectId: made.id });
  };

  /**
   * Every change Home makes to a project, so the open project and its lesson follow it
   * (review of pull request 201): renaming the open project renames it here, removing it
   * closes it and its lesson.
   */
  const projects: ProjectActions = {
    open: (opened) => {
      // An ordinary open shows the model without a lesson (spec 4).
      exitLesson();
      open(opened);
    },
    lesson: (made, template, lesson, step) => {
      startLesson({ ...newLearning(made.id, template, lesson), step });
      open(made);
    },
    rename: async (target, name) => {
      const answer = await client.changeProject(target.id, { name });
      if (answer.kind === "ok") {
        setProject((current) => (current?.id === target.id ? answer.data : current));
      }
      return answer;
    },
    remove: async (target) => {
      const answer = await client.removeProject(target.id);
      if (answer.kind === "ok") {
        setProject((current) => (current?.id === target.id ? null : current));
        // Its lesson ends without a write to the project the service no longer lists.
        if (learning?.projectId === target.id) {
          forgetLesson(target.id);
          exitLesson();
        }
      }
      return answer;
    },
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
            projects={projects}
            onBuild={() => go({ screen: "build", projectId: null })}
          />
        ) : null}
        {route.screen === "build" ? (
          <BuildForm
            client={client}
            onCreated={(made, data) => {
              exitLesson();
              built(made, data);
            }}
            onBack={() => go(HOME)}
          />
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

/**
 * Keeps the step a lesson reached with its project (`lesson_step`, #97), so Home can resume
 * it after a reload; leaving the lesson clears it.
 */
function useLessonStep(
  client: ApiClient,
  projectId: string | null,
  step: number | null,
): (pid: string) => void {
  // The project whose step was last kept, and the write in flight: each write waits for the
  // one before, so the service keeps the latest step or the clearing on exit, never an
  // older step that arrived late (review of pull request 201).
  const last = useRef<string | null>(null);
  const queue = useRef<Promise<unknown>>(Promise.resolve());
  useEffect(() => {
    const send = (pid: string, value: number | null) => {
      queue.current = queue.current.then(() => client.changeProject(pid, { lesson_step: value }));
    };
    if (projectId !== null && step !== null) {
      send(projectId, step);
      last.current = projectId;
    } else if (last.current !== null) {
      send(last.current, null);
      last.current = null;
    }
  }, [client, projectId, step]);
  // A removed project's step is not cleared: the service no longer lists it.
  return (pid: string) => {
    if (last.current === pid) last.current = null;
  };
}
