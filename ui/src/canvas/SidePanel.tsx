/**
 * The side panel follows the selection (`docs/design/canvas-interactions.md` "Selecting"):
 * one block shows its issues, id, label, position, settings and connections; one connection
 * its ends and Disconnect; several items their count and Delete; nothing, the model's
 * parameters and a table of every block, which is the text alternative to the drawing
 * (`docs/design/accessibility.md` "Screen readers").
 */
import { TrashIcon } from "@phosphor-icons/react";
import { useEffect, useState } from "react";
import type { ApiClient, ApiResult } from "../api/client";
import type { Component, ComponentType, Connection, Issue, Model } from "../api/types";
import { IssueList, ServiceProblem } from "../components/ServiceProblem";
import { lock, useBusy } from "./busy";
import {
  components,
  connections,
  issueComponent,
  issueSetting,
  portsOf,
  readNumber,
  splitEnd,
} from "./model";
import { Parameters } from "./Parameters";
import { componentIn, type EditPlan } from "./plans";
import { CommitInput, type FieldActions, type FieldContext, SettingField } from "./SettingFields";

export interface PanelActions extends FieldActions {
  /** Sends one batch and gives the service's answer. */
  send(label: string, edits: EditPlan): Promise<ApiResult<unknown> | null>;
  select(blocks: string[]): void;
  remove(): void;
  connect(from: string, to: string): void;
}

export interface Selection {
  blocks: string[];
  /** Selected connections, by their index in `connections`. */
  connections: number[];
}

const cache = new WeakMap<ApiClient, Map<string, ApiResult<ComponentType>>>();

/** `GET /v1/schema/components/{type}`, once per type for each client. */
export function useComponentType(client: ApiClient, type: string): ApiResult<ComponentType> | null {
  const known = cache.get(client)?.get(type) ?? null;
  const [result, setResult] = useState(known);
  useEffect(() => {
    const stored = cache.get(client)?.get(type);
    if (stored) {
      setResult(stored);
      return;
    }
    setResult(null);
    let live = true;
    void client.getComponentType(type).then((answer) => {
      if (answer.kind === "ok") {
        const forClient = cache.get(client) ?? new Map();
        forClient.set(type, answer);
        cache.set(client, forClient);
      }
      if (live) setResult(answer);
    });
    return () => {
      live = false;
    };
  }, [client, type]);
  return result;
}

function inputPorts(model: Model, types: Record<string, ComponentType>): string[] {
  const ends: string[] = [];
  for (const component of components(model)) {
    for (const port of portsOf(component, types[component.type]).inputs) {
      ends.push(`${component.id}.${port}`);
    }
  }
  return ends;
}

function BlockPanel({
  client,
  model,
  component,
  types,
  issues,
  readOnly,
  actions,
}: {
  client: ApiClient;
  model: Model;
  component: Component;
  types: Record<string, ComponentType>;
  issues: Issue[];
  readOnly: boolean;
  actions: PanelActions;
}) {
  const busy = useBusy();
  const type = useComponentType(client, component.type);
  const [idProblem, setIdProblem] = useState<ApiResult<unknown> | null>(null);
  const [labelProblem, setLabelProblem] = useState<ApiResult<unknown> | null>(null);
  // The panel stays mounted across a rename, so a field's draft (committed once a write in
  // flight has answered) reaches the block under its new id; another block clears the
  // problems shown.
  const [problemsFor, setProblemsFor] = useState(component.id);
  if (problemsFor !== component.id) {
    setProblemsFor(component.id);
    setIdProblem(null);
    setLabelProblem(null);
  }

  const byField = new Map<string, Issue[]>();
  for (const issue of issues) {
    const setting = issueSetting(issue);
    if (setting !== null) byField.set(setting, [...(byField.get(setting) ?? []), issue]);
  }
  const ctx: FieldContext = { model, component, issues: byField, readOnly, actions };
  const ports = portsOf(component, types[component.type]);
  const targets = inputPorts(model, types);
  const ui = component.ui ?? {};

  const rename = async (text: string) => {
    const result = await actions.send(`rename ${component.id} to ${text}`, [
      { edit: "rename_component", id: component.id, new_id: text },
    ]);
    setIdProblem(result !== null && result.kind !== "ok" ? result : null);
    if (result?.kind === "ok") actions.select([text]);
  };
  const relabel = async (text: string) => {
    const result = await actions.send(`label ${component.id}`, [
      { edit: "set_label", id: component.id, label: text === "" ? null : text },
    ]);
    setLabelProblem(result !== null && result.kind !== "ok" ? result : null);
  };
  const move = (axis: "x" | "y", text: string) => {
    const value = readNumber(text);
    const id = component.id;
    actions.edit(`move ${id}`, (current) => {
      const now = componentIn(current, id);
      return now ? [{ edit: "set_ui", id, ui: { ...(now.ui ?? {}), [axis]: value } }] : null;
    });
  };

  return (
    <section className="panel-section" aria-labelledby="block-heading">
      <h2 className="heading" id="block-heading">
        {component.label ?? component.id} <span className="muted small">{component.type}</span>
      </h2>
      {issues.length > 0 ? <IssueList issues={issues} /> : null}
      <div className="panel-pair">
        <div className="panel-field">
          <label htmlFor="block-id" className="field-label">
            Id
          </label>
          <CommitInput
            id="block-id"
            value={component.id}
            mono
            readOnly={readOnly}
            describedBy="block-id-hint"
            onCommit={(text) => void rename(text.trim())}
          />
          <p className="hint" id="block-id-hint">
            A lower-case letter, then lower-case letters, digits or _.
          </p>
          <ServiceProblem result={idProblem} />
        </div>
        <div className="panel-field">
          <label htmlFor="block-label" className="field-label">
            Label (optional)
          </label>
          <CommitInput
            id="block-label"
            value={component.label ?? ""}
            readOnly={readOnly}
            onCommit={(text) => void relabel(text.trim())}
          />
          <ServiceProblem result={labelProblem} />
        </div>
      </div>
      <fieldset className="group">
        <legend className="field-label">Position</legend>
        <div className="panel-pair">
          {(["x", "y"] as const).map((axis) => (
            <div className="panel-field" key={axis}>
              <label htmlFor={`block-${axis}`} className="field-label">
                {axis}
              </label>
              <CommitInput
                id={`block-${axis}`}
                value={typeof ui[axis] === "number" ? String(ui[axis]) : ""}
                readOnly={readOnly}
                onCommit={(text) => move(axis, text)}
              />
            </div>
          ))}
        </div>
      </fieldset>
      <h3 className="subheading">Settings</h3>
      {type === null ? <p className="muted">Loading the settings…</p> : null}
      {type !== null && type.kind !== "ok" ? <ServiceProblem result={type} /> : null}
      {type?.kind === "ok" ? (
        type.data.settings.length === 0 ? (
          <p className="muted">This block has no settings.</p>
        ) : (
          type.data.settings.map((setting) => (
            <SettingField
              key={setting.name}
              ctx={ctx}
              setting={setting}
              segments={[setting.name]}
            />
          ))
        )
      ) : null}
      {ports.outputs.length > 0 ? (
        <>
          <h3 className="subheading">Connections</h3>
          {ports.outputs.map((port) => {
            const from = `${component.id}.${port}`;
            const current = connections(model).find((item) => item.from === from)?.to ?? "";
            return (
              <div className="panel-field" key={port}>
                <label htmlFor={`connect-${port}`} className="field-label">
                  <span className="mono">{port}</span> goes to
                </label>
                <select
                  id={`connect-${port}`}
                  className="mono"
                  value={current}
                  {...lock(readOnly, busy)}
                  onChange={(event) => {
                    const to = event.target.value;
                    if (to === "")
                      actions.edit(`disconnect ${from}`, [{ edit: "disconnect", from }]);
                    else actions.connect(from, to);
                  }}
                >
                  <option value="">Not connected</option>
                  {current !== "" && !targets.includes(current) ? (
                    <option value={current}>{current}</option>
                  ) : null}
                  {targets.map((end) => (
                    <option key={end} value={end}>
                      {end}
                    </option>
                  ))}
                </select>
              </div>
            );
          })}
        </>
      ) : null}
      <button
        type="button"
        className="danger"
        {...lock(readOnly, busy)}
        onClick={() => actions.remove()}
      >
        <TrashIcon aria-hidden="true" size={16} />
        Delete
      </button>
    </section>
  );
}

function ConnectionPanel({
  connection,
  readOnly,
  actions,
}: {
  connection: Connection;
  readOnly: boolean;
  actions: PanelActions;
}) {
  const busy = useBusy();
  return (
    <section className="panel-section" aria-labelledby="connection-heading">
      <h2 className="heading" id="connection-heading">
        Connection
      </h2>
      <p>
        From <span className="mono">{connection.from}</span> to{" "}
        <span className="mono">{connection.to}</span>
      </p>
      <button
        type="button"
        className="secondary"
        {...lock(readOnly, busy)}
        onClick={() =>
          actions.edit(`disconnect ${connection.from}`, [
            { edit: "disconnect", from: connection.from },
          ])
        }
      >
        Disconnect
      </button>
    </section>
  );
}

function BlocksTable({
  model,
  types,
  issues,
  actions,
}: {
  model: Model;
  types: Record<string, ComponentType>;
  issues: Issue[];
  actions: PanelActions;
}) {
  const all = components(model);
  if (all.length === 0) {
    return (
      <section className="panel-section" aria-labelledby="blocks-heading">
        <h2 className="heading" id="blocks-heading">
          Blocks
        </h2>
        <p className="muted">No blocks yet. Add one from the palette.</p>
      </section>
    );
  }
  return (
    <section className="panel-section" aria-labelledby="blocks-heading">
      <h2 className="heading" id="blocks-heading">
        Blocks
      </h2>
      <table className="blocks-table">
        <thead>
          <tr>
            <th scope="col">Block</th>
            <th scope="col">Type</th>
            <th scope="col">Goes to</th>
            <th scope="col">Problems</th>
            <th scope="col">
              <span className="visually-hidden">Select</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {all.map((component) => {
            const goes = connections(model)
              .filter((item) => splitEnd(item.from)?.[0] === component.id)
              .map((item) => item.to);
            const count = issues.filter(
              (issue) => issueComponent(issue, model) === component.id,
            ).length;
            return (
              <tr key={component.id}>
                <td className="mono">{component.id}</td>
                <td>{component.type}</td>
                <td className="mono">
                  {goes.join(", ") ||
                    (portsOf(component, types[component.type]).outputs.length ? "—" : "")}
                </td>
                <td>{count}</td>
                <td>
                  <button
                    type="button"
                    className="link"
                    onClick={() => actions.select([component.id])}
                    aria-label={`Select ${component.id}`}
                  >
                    Select
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}

export function SidePanel({
  client,
  model,
  selection,
  types,
  issues,
  readOnly,
  actions,
}: {
  client: ApiClient;
  model: Model;
  selection: Selection;
  types: Record<string, ComponentType>;
  issues: Issue[];
  readOnly: boolean;
  actions: PanelActions;
}) {
  const busy = useBusy();
  const count = selection.blocks.length + selection.connections.length;
  let body: React.ReactNode;
  if (count === 0) {
    body = (
      <>
        <Parameters
          model={model}
          issues={issues.filter((issue) => issue.path.startsWith("/parameters"))}
          readOnly={readOnly}
          actions={actions}
        />
        <BlocksTable model={model} types={types} issues={issues} actions={actions} />
      </>
    );
  } else if (count > 1) {
    body = (
      <section className="panel-section" aria-labelledby="selection-heading">
        <h2 className="heading" id="selection-heading">
          {count} items selected
        </h2>
        <button
          type="button"
          className="danger"
          {...lock(readOnly, busy)}
          onClick={() => actions.remove()}
        >
          <TrashIcon aria-hidden="true" size={16} />
          Delete
        </button>
      </section>
    );
  } else if (selection.blocks.length === 1) {
    const component = components(model).find((item) => item.id === selection.blocks[0]);
    body = component ? (
      <BlockPanel
        client={client}
        model={model}
        component={component}
        types={types}
        issues={issues.filter((issue) => issueComponent(issue, model) === component.id)}
        readOnly={readOnly}
        actions={actions}
      />
    ) : null;
  } else {
    const connection = connections(model)[selection.connections[0] ?? -1];
    body = connection ? (
      <ConnectionPanel connection={connection} readOnly={readOnly} actions={actions} />
    ) : null;
  }
  return (
    <aside className="side-panel" data-region="side" aria-label="Block settings" tabIndex={-1}>
      {body}
    </aside>
  );
}
