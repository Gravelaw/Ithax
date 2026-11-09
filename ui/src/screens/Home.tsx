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
import { ServiceProblem } from "../components/ServiceProblem";
import { type Lesson, parseLesson } from "../learn/lesson";
import { BUILD_TEMPLATES } from "./BuildForm";
import { NewProjectDialog } from "./NewProjectDialog";
import { OpenProjectDialog } from "./OpenProjectDialog";

export const EMPTY_GALLERY = "No templates are installed yet.";
export const NO_PROJECTS = "No projects yet. Create one, or open a project folder.";
export const BUILD_UNAVAILABLE = "The Build form needs the templates, and none are installed yet.";
/** Said when a served template's lesson does not read (the service serves only those that do). */
export const LESSON_UNREADABLE = "This template's lesson cannot be read.";

const AUDIENCE_ORDER = ["Students", "Both", "Business"];

function audienceRank(template: Template): number {
  const at = AUDIENCE_ORDER.indexOf(String(template.audience ?? ""));
  return at < 0 ? AUDIENCE_ORDER.length : at;
}

function created(project: Project): string {
  if (project.created === null) return "";
  const date = new Date(project.created);
  if (Number.isNaN(date.getTime())) return "";
  return `Created ${date.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}`;
}

type Loaded<T> = ApiResult<T> | null;

export function Home({
  client,
  onOpen,
  onBuild = () => undefined,
  onLesson = () => undefined,
}: {
  client: ApiClient;
  onOpen: (project: Project) => void;
  /** Opens the Build form. */
  onBuild?: () => void;
  /** A project made from `template`, to open with its lesson. */
  onLesson?: (project: Project, template: Template, lesson: Lesson) => void;
}) {
  const [projects, setProjects] = useState<Loaded<Project[]>>(null);
  // The lesson being started (one at a time), and why the last one did not start.
  const [starting, setStarting] = useState<string | null>(null);
  const [startProblem, setStartProblem] = useState<ApiResult<unknown> | null>(null);
  const [unreadable, setUnreadable] = useState(false);
  const [templates, setTemplates] = useState<Loaded<Template[]>>(null);
  const [dialog, setDialog] = useState<"new" | "open" | null>(null);
  const [lessonsFirst, setLessonsFirst] = useState(false);
  const gallery = useRef<HTMLHeadingElement>(null);

  const load = useCallback(async () => {
    const [listed, gallery] = await Promise.all([client.listProjects(), client.listTemplates()]);
    setProjects(listed);
    setTemplates(gallery);
  }, [client]);

  useEffect(() => {
    void load();
  }, [load]);

  const shown = templates?.kind === "ok" ? [...templates.data] : [];
  if (lessonsFirst) shown.sort((a, b) => audienceRank(a) - audienceRank(b));
  const buildable = shown.some((template) => BUILD_TEMPLATES.includes(template.id));

  /** Reads the template and its lesson, then makes the project; one at a time. */
  const startLesson = async (template: Template) => {
    if (starting !== null) return;
    setStarting(template.id);
    setStartProblem(null);
    setUnreadable(false);
    const read = await client.getTemplate(template.id);
    if (read.kind !== "ok") {
      setStarting(null);
      setStartProblem(read);
      return;
    }
    const lesson = parseLesson(read.data.lesson);
    if (lesson === null) {
      setStarting(null);
      setUnreadable(true);
      return;
    }
    const made = await client.createProject({
      name: read.data.template.title,
      template: template.id,
    });
    setStarting(null);
    if (made.kind !== "ok") {
      setStartProblem(made);
      return;
    }
    onLesson(made.data, read.data.template, lesson);
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
                  aria-label={`Start the lesson ${template.title}`}
                  aria-disabled={starting !== null || undefined}
                  onClick={() => void startLesson(template)}
                >
                  Start the lesson
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
          <ul className="projects">
            {[...projects.data].reverse().map((project) => (
              <li key={project.id}>
                <button
                  type="button"
                  className="project"
                  aria-disabled={project.available ? undefined : "true"}
                  onClick={() => {
                    if (project.available) onOpen(project);
                  }}
                >
                  <span className="subheading">{project.name ?? project.path}</span>
                  <span className="muted small">
                    {project.available ? created(project) : "Not available"}
                  </span>
                  <span className="mono small muted">{project.path}</span>
                </button>
              </li>
            ))}
          </ul>
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
        <NewProjectDialog client={client} onCreated={onOpen} onCancel={() => setDialog(null)} />
      ) : null}
      {dialog === "open" ? (
        <OpenProjectDialog client={client} onOpened={onOpen} onCancel={() => setDialog(null)} />
      ) : null}
    </div>
  );
}
