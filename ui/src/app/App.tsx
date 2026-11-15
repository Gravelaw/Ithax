/**
 * The app frame (`docs/design/design-system.md` "Spacing and layout"): the navigation
 * rail, the top bar and the current screen, and the first-start notice until it has been
 * seen.
 */
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import type { ApiClient, ApiResult } from "../api/client";
import type { Project, SettingsBody } from "../api/types";
import { CanvasScreen } from "../canvas/CanvasScreen";
import { ServiceProblem } from "../components/ServiceProblem";
import { useCurrent } from "../components/useCurrent";
import { DataScreen } from "../data/DataScreen";
import { ExperimentScreen } from "../experiment/ExperimentScreen";
import { newLearning, useLearning } from "../learn/LearnContext";
import { RunMonitor } from "../monitor/RunMonitor";
import { ResultsScreen } from "../results/ResultsScreen";
import { BuildForm } from "../screens/BuildForm";
import { FirstStartNotice } from "../screens/FirstStartNotice";
import { Home } from "../screens/Home";
import { HelpScreen } from "../settings/HelpScreen";
import { useSettings } from "../settings/SettingsContext";
import { SettingsScreen } from "../settings/SettingsScreen";
import { NAV_ITEMS, NavRail } from "./NavRail";
import type { ProjectActions, ProjectApi, RunProjects } from "./projectActions";
import { cycleRegion } from "./regions";
import { HOME, type Route, useRoute } from "./router";
import { type KeepWrite, UnsavedWrites, useUnsaved } from "./unsaved";
import { useProjectQueue } from "./useProjectQueue";

/** Said when the place reached in a lesson could not be saved. */
export const STEP_UNSAVED = "Your place in the lesson was not saved.";
/** Said when the time a project was opened could not be saved. */
export const OPENED_UNSAVED = "The time this project was opened was not saved.";

function screenTitle(route: Route): string {
  if (route.screen === "build") return "Build a model";
  if (route.screen === "help") return "Help";
  return NAV_ITEMS.find((item) => item.screen === route.screen)?.label ?? "Home";
}

export function App({ client }: { client: ApiClient }) {
  const [route, go] = useRoute();
  const { settings, save } = useSettings();
  const { start: startLesson, exit: exitLesson, learning } = useLearning();
  // A completion after an await reads the lesson as it is then (review of pull request 201).
  const currentLearning = useCurrent(learning);
  // Every read and write of project state, one action at a time (review of pull request 201).
  const { run, busy } = useProjectQueue(client);
  // Background writes that were not saved, shown with "Try again" (review of pull request 201).
  const [unsaved, keep, forgetWrites] = useUnsaved();
  // Projects removed in this session: a background write or retry queued before a removal
  // checks this when it runs, so nothing is sent to a removed project (review of pull
  // request 201). Opening a project, as from its folder again, takes it off.
  const removed = useRef(new Set<string>());
  const forgetLesson = useLessonStep(
    run,
    keep,
    learning?.projectId ?? null,
    learning?.step ?? null,
  );
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
    void run((api) => api.list()).then((listed) => {
      if (!current) return;
      const found = listed.kind === "ok" ? listed.data.find((item) => item.id === wanted) : null;
      if (found) setProject(found);
      else go(HOME);
    });
    return () => {
      current = false;
    };
  }, [run, route.projectId, project, go]);

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
  const open = async (api: ProjectApi, opened: Project, screen: "canvas" | "data" = "canvas") => {
    removed.current.delete(opened.id);
    setProject(opened);
    go({ screen, projectId: opened.id });
    await noteOpened(api, opened.id);
  };

  /** Notes the time a project was opened, so Recent projects lists it first. */
  const noteOpened = async (api: ProjectApi, pid: string) => {
    if (removed.current.has(pid)) return;
    const answer = await api.change(pid, { opened: true });
    keep(pid, "opened", OPENED_UNSAVED, answer, () => {
      void run((again) => noteOpened(again, pid));
    });
  };

  /**
   * Every change Home makes to a project, so the open project and its lesson follow it
   * (review of pull request 201): renaming the open project renames it here, removing it
   * closes it and its lesson.
   */
  const projects: ProjectActions = {
    run,
    busy,
    open: (api, opened) => {
      // An ordinary open shows the model without a lesson (spec 4).
      exitLesson();
      return open(api, opened);
    },
    lesson: (api, made, template, lesson, step) => {
      startLesson({ ...newLearning(made.id, template, lesson), step });
      return open(api, made);
    },
    rename: async (api, target, name) => {
      const answer = await api.change(target.id, { name });
      if (answer.kind === "ok") {
        setProject((current) => (current?.id === target.id ? answer.data : current));
      }
      return answer;
    },
    remove: async (api, target) => {
      const answer = await api.remove(target.id);
      if (answer.kind === "ok") {
        removed.current.add(target.id);
        setProject((current) => (current?.id === target.id ? null : current));
        // Nothing more is written to, or tried again for, the project the service no longer
        // lists, whichever lesson is open (review of pull request 201).
        forgetLesson(target.id);
        forgetWrites(target.id);
        if (currentLearning()?.projectId === target.id) exitLesson();
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
    route.screen === "home" ||
    route.screen === "build" ||
    route.screen === "settings" ||
    route.screen === "help"
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
          <UnsavedWrites unsaved={unsaved} />
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
            run={run}
            onCreated={(api, made, data) => {
              // A project the Build form made: the Data screen with data, else the Canvas.
              exitLesson();
              return open(api, made, data ? "data" : "canvas");
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
        {route.screen === "help" ? <HelpScreen client={client} /> : null}
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
  run: RunProjects,
  keep: KeepWrite,
  projectId: string | null,
  step: number | null,
): (pid: string) => void {
  // The project whose step was last kept, and the step wanted for each project. Each write
  // is an action of App's queue and sends the step wanted when it runs, not when it was
  // queued, so a write queued earlier, or "Try again" on one that failed, never saves an
  // older step or undoes Exit's clearing (reviews of pull request 201).
  const last = useRef<string | null>(null);
  const wanted = useRef<Record<string, number | null>>({});
  const write = useCallback(
    (pid: string) =>
      void run(async (api) => {
        if (!(pid in wanted.current)) return;
        const answer = await api.change(pid, { lesson_step: wanted.current[pid] ?? null });
        // A refused write is shown with "Try again", never taken as saved.
        keep(pid, "step", STEP_UNSAVED, answer, () => write(pid));
      }),
    [run, keep],
  );
  useEffect(() => {
    const send = (pid: string, value: number | null) => {
      wanted.current[pid] = value;
      write(pid);
    };
    if (projectId !== null && step !== null) {
      send(projectId, step);
      last.current = projectId;
    } else if (last.current !== null) {
      send(last.current, null);
      last.current = null;
    }
  }, [write, projectId, step]);
  // A removed project's step is not cleared, nor tried again: the service no longer lists it.
  return (pid: string) => {
    if (last.current === pid) last.current = null;
    delete wanted.current[pid];
  };
}
