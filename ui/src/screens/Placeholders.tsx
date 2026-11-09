/**
 * The screens later M9 tickets build (Canvas AKS-136 and AKS-137, Data and Experiment
 * AKS-120, Run monitor, Results and Settings AKS-138). The Canvas placeholder already opens
 * the project's events socket, so the token message and the interface's `Origin` are
 * exercised end to end; Settings already holds About, which the first-start notice names.
 */
import { useEffect, useState } from "react";
import type { ApiClient } from "../api/client";
import type { Project, ProjectEvent } from "../api/types";
import { LOST_CONTACT } from "../components/ServiceProblem";

export const LATER = "This screen arrives in a later build.";

export function ScreenPlaceholder({ title }: { title: string }) {
  return (
    <section className="placeholder" aria-labelledby="screen-heading">
      <h1 id="screen-heading" className="title">
        {title}
      </h1>
      <p className="muted">{LATER}</p>
    </section>
  );
}

export function CanvasPlaceholder({
  client,
  project,
}: {
  client: ApiClient;
  project: Project | null;
}) {
  const projectId = project?.id ?? null;
  const [revision, setRevision] = useState<number | null>(null);
  const [closed, setClosed] = useState<string | null>(null);

  useEffect(() => {
    if (projectId === null) return;
    setRevision(null);
    setClosed(null);
    const socket = client.projectEvents(projectId, {
      onEvent: (event: ProjectEvent) => {
        if (event.type === "model") setRevision(event.revision);
      },
      onClose: (code, reason) => {
        if (code !== 1000) setClosed(reason || LOST_CONTACT);
      },
    });
    return () => socket.close();
  }, [client, projectId]);

  return (
    <section className="placeholder" aria-labelledby="screen-heading">
      <h1 id="screen-heading" className="title">
        Canvas
      </h1>
      <p className="muted">{LATER}</p>
      <p role="status">
        {revision === null ? "Connecting to the project…" : `Model saved at revision ${revision}.`}
      </p>
      {closed !== null ? <p role="alert">{closed}</p> : null}
    </section>
  );
}

export function SettingsPlaceholder() {
  return (
    <section className="placeholder" aria-labelledby="screen-heading">
      <h1 id="screen-heading" className="title">
        Settings
      </h1>
      <p className="muted">{LATER}</p>
      <h2 className="heading" id="about-heading">
        About
      </h2>
      <p>
        Build a model of a process, run it many times, and see where the waits and bottlenecks are.
        Results are estimates from a simulation. Use them to support your judgement, not to replace
        it.
      </p>
      <p>
        This is free software under the GNU AGPL version 3.{" "}
        <a href="./LICENSE.txt">Read the licence</a>.{" "}
        <a href="./THIRD-PARTY-NOTICES.txt">Notices of the software it includes</a>.
      </p>
    </section>
  );
}
