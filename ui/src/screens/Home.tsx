/**
 * Home (spec 3 "Screens" 1; `docs/design/flows.md` "Shared start" step 4;
 * `docs/design/wireframes/02-home.svg` and `02c-new-project.svg`): the Learn and Build
 * entries, the template gallery (`GET /v1/templates`, served since AKS-122), recent projects
 * (`GET /v1/projects`), "New empty project" and "Open a project folder".
 *
 * Readings (AKS-119, `docs/DECISIONS.md`): recent projects are listed newest registered
 * first, since the service keeps no last-edited time; Learn moves to the gallery, ordered
 * students first. Since AKS-124 each card starts its lesson ("Start the lesson": the
 * template with `GET /v1/templates/{tid}`, then `POST /v1/projects` with `template`), and
 * Build opens the Build form, unavailable with its reason when none of its templates is
 * served (spec 3 "Screens", spec 4 "Learn and Build modes").
 */
import { FolderOpenIcon, GraduationCapIcon, HammerIcon, PlusIcon } from "@phosphor-icons/react";
import { useCallback, useEffect, useRef, useState } from "react";
import type { ApiClient, ApiResult } from "../api/client";
import type { Project, Template } from "../api/types";
import type { ProjectActions } from "../app/projectActions";
import { ServiceProblem } from "../components/ServiceProblem";
import { useMounted } from "../components/useMounted";
import { parseLesson } from "../learn/lesson";
import { BUILD_TEMPLATES } from "./BuildForm";
import { NewProjectDialog } from "./NewProjectDialog";
import { OpenProjectDialog } from "./OpenProjectDialog";
import { RecentProjects, recentOrder } from "./RecentProjects";

export const EMPTY_GALLERY = "No templates are installed yet.";
export { REMOVED_KEEPS_FILES } from "./RecentProjects";
export const NO_PROJECTS = "No projects yet. Create one, or open a project folder.";
export const BUILD_UNAVAILABLE = "The Build form needs the templates, and none are installed yet.";
/** Said while a project action is pending; the actions that conflict wait (review of pull request 201). */
export const PROJECTS_BUSY =
  "Saving your projects… Opening, renaming and removing wait until it is done.";

/** Said when a served template's lesson does not read (the service serves only those that do). */
export const LESSON_UNREADABLE = "This template's lesson cannot be read.";

const AUDIENCE_ORDER = ["Students", "Both", "Business"];

function audienceRank(template: Template): number {
  const at = AUDIENCE_ORDER.indexOf(String(template.audience ?? ""));
  return at < 0 ? AUDIENCE_ORDER.length : at;
}

type Loaded<T> = ApiResult<T> | null;

/** The newest available project made from `template`, whose lesson is resumed (#97). */
function lessonProjectIn(projects: readonly Project[], template: Template): Project | undefined {
  return recentOrder(projects).find(
    (project) => project.available && project.template === template.id,
  );
}

export function Home({
  client,
  projects: actions,
  onBuild = () => undefined,
}: {
  client: ApiClient;
  /** Every change to a project goes through the application (review of pull request 201). */
  projects: ProjectActions;
  /** Opens the Build form. */
  onBuild?: () => void;
}) {
  const [projects, setProjects] = useState<Loaded<Project[]>>(null);
  // The lesson being started (one at a time), and why the last one did not start.
  const [starting, setStarting] = useState<string | null>(null);
  const [startProblem, setStartProblem] = useState<ApiResult<unknown> | null>(null);
  const [unreadable, setUnreadable] = useState(false);
  // An answer that arrives after Home was left neither navigates nor sets state.
  const mounted = useMounted();
  const [templates, setTemplates] = useState<Loaded<Template[]>>(null);
  const [dialog, setDialog] = useState<"new" | "open" | null>(null);
  const [lessonsFirst, setLessonsFirst] = useState(false);
  const gallery = useRef<HTMLHeadingElement>(null);

  const load = useCallback(async () => {
    // The list is read in App's queue, after any action already queued (reviews of pull
    // request 201: a list read during a removal or a step's write showed an older one). The
    // gallery holds no project state and is shown as soon as it arrives.
    await Promise.all([
      client.listTemplates().then((gallery) => {
        if (mounted.current) setTemplates(gallery);
      }),
      actions
        .run((api) => api.list())
        .then((listed) => {
          if (mounted.current) setProjects(listed);
        }),
    ]);
  }, [client, actions.run, mounted]);

  useEffect(() => {
    void load();
  }, [load]);

  const shown = templates?.kind === "ok" ? [...templates.data] : [];
  if (lessonsFirst) shown.sort((a, b) => audienceRank(a) - audienceRank(b));
  const buildable = shown.some((template) => BUILD_TEMPLATES.includes(template.id));

  /** The newest available project made from `template` as listed now, if any. */
  const lessonProject = (template: Template): Project | undefined =>
    projects?.kind === "ok" ? lessonProjectIn(projects.data, template) : undefined;

  /**
   * Reads the template and its lesson, then resumes it in the project already made from
   * the template, at its step, or makes the project (#97: one project per lesson, not a new
   * one at each start); one at a time.
   */
  const startLesson = async (template: Template) => {
    // Not while another project action is pending, which it would conflict with.
    if (starting !== null || actions.busy) return;
    setStarting(template.id);
    setStartProblem(null);
    setUnreadable(false);
    // One action of App's queue, from the template's read to the project opened: no removal,
    // rename or step's write runs in between, and the project and its step are read as they
    // are when it starts (reviews of pull request 201).
    await actions.run(async (api) => {
      const read = await api.template(template.id);
      if (!mounted.current) return;
      if (read.kind !== "ok") {
        setStartProblem(read);
        return;
      }
      const lesson = parseLesson(read.data.lesson);
      if (lesson === null) {
        setUnreadable(true);
        return;
      }
      const listed = await api.list();
      if (!mounted.current) return;
      // A project is made only once the list shows none for this lesson: a list that cannot
      // be read is shown, never taken as empty (review of pull request 201).
      if (listed.kind !== "ok") {
        setStartProblem(listed);
        return;
      }
      setProjects(listed);
      const earlier = lessonProjectIn(listed.data, template);
      if (earlier !== undefined) {
        const step = Math.min(earlier.lesson_step ?? 0, lesson.steps.length);
        await actions.lesson(api, earlier, read.data.template, lesson, step);
        return;
      }
      const made = await api.create({ name: read.data.template.title, template: template.id });
      if (!mounted.current) return;
      if (made.kind !== "ok") {
        setStartProblem(made);
        return;
      }
      await actions.lesson(api, made.data, read.data.template, lesson, 0);
    });
    if (mounted.current) setStarting(null);
  };

  return (
    <div className="home">
      <section className="home-main" aria-labelledby="home-heading">
        <h1 id="home-heading" className="title">
          What would you like to do?
        </h1>
        <div className="entries">
          <button
            type="button"
            className="entry"
            onClick={() => {
              setLessonsFirst(true);
              gallery.current?.focus();
            }}
          >
            <GraduationCapIcon aria-hidden="true" size={32} weight="duotone" />
            <span className="heading">Learn</span>
            <span className="muted">Start from a worked example</span>
            <span>
              A guided lesson explains each block, then asks you to change something and predict.
            </span>
          </button>
          <div className="entry-wrap">
            <button
              type="button"
              className="entry"
              aria-disabled={buildable ? undefined : "true"}
              aria-describedby={buildable ? undefined : "build-reason"}
              onClick={() => {
                if (buildable) onBuild();
              }}
            >
              <HammerIcon aria-hidden="true" size={32} weight="duotone" />
              <span className="heading">Build</span>
              <span className="muted">Answer a question of your own</span>
              <span>Two questions pick the closest template; your data is optional.</span>
            </button>
            {buildable ? null : (
              <p id="build-reason" className="reason">
                {BUILD_UNAVAILABLE}
              </p>
            )}
          </div>
        </div>

        <h2 ref={gallery} tabIndex={-1} className="heading" id="templates-heading">
          Templates
        </h2>
        {templates === null ? (
          <p className="muted">Loading…</p>
        ) : templates.kind !== "ok" ? (
          <ServiceProblem result={templates} />
        ) : shown.length === 0 ? (
          <p className="empty">{EMPTY_GALLERY}</p>
        ) : (
          <ul className="gallery" aria-labelledby="templates-heading">
            {shown.map((template) => (
              <li key={template.id} className="card">
                <p className="subheading">{template.title}</p>
                {template.summary ? <p className="small">{template.summary}</p> : null}
                <p className="muted small">
                  {[
                    template.audience,
                    template.minutes !== undefined ? `${template.minutes} min` : null,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
                <button
                  type="button"
                  className="secondary"
                  aria-label={`${lessonProject(template) ? "Resume" : "Start"} the lesson ${template.title}`}
                  aria-disabled={starting !== null || actions.busy || undefined}
                  onClick={() => void startLesson(template)}
                >
                  {lessonProject(template) ? "Resume the lesson" : "Start the lesson"}
                </button>
                {starting === template.id ? (
                  <p className="muted small" role="status">
                    Starting the lesson…
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        )}
        {unreadable ? <p role="alert">{LESSON_UNREADABLE}</p> : null}
        <ServiceProblem result={startProblem} />
      </section>

      <section className="recent" aria-labelledby="recent-heading">
        <h2 id="recent-heading" className="heading">
          Recent projects
        </h2>
        {actions.busy && projects !== null ? (
          <p className="muted small" role="status">
            {PROJECTS_BUSY}
          </p>
        ) : null}
        {projects === null ? (
          <p className="muted">Loading…</p>
        ) : projects.kind !== "ok" ? (
          <>
            <ServiceProblem result={projects} />
            <button type="button" className="secondary" onClick={() => void load()}>
              Try again
            </button>
          </>
        ) : projects.data.length === 0 ? (
          <p className="empty">{NO_PROJECTS}</p>
        ) : (
          <RecentProjects
            projects={projects.data}
            actions={actions}
            onChanged={() => void load()}
          />
        )}
        <div className="links">
          <button type="button" className="link" onClick={() => setDialog("new")}>
            <PlusIcon aria-hidden="true" size={18} />
            New empty project
          </button>
          <button type="button" className="link" onClick={() => setDialog("open")}>
            <FolderOpenIcon aria-hidden="true" size={18} />
            Open a project folder
          </button>
        </div>
      </section>

      {dialog === "new" ? (
        <NewProjectDialog
          projects={actions.run}
          onCreated={actions.open}
          onCancel={() => setDialog(null)}
        />
      ) : null}
      {dialog === "open" ? (
        <OpenProjectDialog
          projects={actions.run}
          onOpened={actions.open}
          onCancel={() => setDialog(null)}
        />
      ) : null}
    </div>
  );
}
