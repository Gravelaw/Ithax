/**
 * The Build form (spec 4 "Build mode"; spec 3 "Screens" 1; `docs/design/flows.md` "Build
 * mode" steps B1 to B4b; `docs/design/wireframes/02b-build-form.svg`; AKS-124).
 *
 * A fixed form, not a conversation, on one page: step 1, "What do you want to find out?",
 * one of the six answers of spec 4, each showing the template it opens, the sixth asking
 * "Which of these?"; step 2, "Do you have data?", and the project's name, which starts as
 * the chosen template's title. Nothing is preselected and nothing is sent until Continue,
 * which creates the project from the template (`POST /v1/projects` `{name, template}`) and
 * opens it: on the Data screen for "Yes, import a file", on the Canvas with nothing
 * selected for "No, I will estimate". Build mode never requires a data file.
 */
import { useEffect, useId, useRef, useState } from "react";
import type { ApiClient, ApiResult } from "../api/client";
import type { Project, Template } from "../api/types";
import { ServiceProblem } from "../components/ServiceProblem";

export interface Answer {
  answer: string;
  /** The template it opens; absent for the answer that asks one more question. */
  template?: string;
  /** "Which of these?": the second question's answers. */
  second?: readonly Answer[];
}

/** Spec 4 "Build mode": the six answers and the template each opens, in its order. */
export const ANSWERS: readonly Answer[] = [
  { answer: "How long will people or items wait?", template: "coffee_shop" },
  { answer: "Where is the bottleneck?", template: "three_machine_line" },
  { answer: "How much does downtime cost?", template: "machine_breakdowns" },
  { answer: "How many staff or machines do I need?", template: "how_many_machines" },
  { answer: "How much stock should I hold?", template: "inventory_reorder_point" },
  {
    answer: "What mix, plan or rota is best?",
    second: [
      { answer: "A product mix", template: "product_mix" },
      { answer: "A transport plan", template: "transport_plan" },
      { answer: "A staff rota", template: "staff_rota" },
    ],
  },
];

/** Every template the form can open. */
export const BUILD_TEMPLATES: readonly string[] = ANSWERS.flatMap((item) =>
  item.template !== undefined ? [item.template] : (item.second ?? []).map((s) => s.template ?? ""),
);

export const NOT_INSTALLED = "Its template is not installed.";
export const NEED_ANSWER = "Choose what you want to find out.";
export const NEED_SECOND = "Choose which of these.";
export const NEED_DATA = "Say whether you have data.";
export const NEED_NAME = "Give the project a name.";

export function BuildForm({
  client,
  onCreated,
  onBack,
}: {
  client: ApiClient;
  /** The project made; `data` when the user chose "Yes, import a file". */
  onCreated: (project: Project, data: boolean) => void;
  onBack: () => void;
}) {
  const [templates, setTemplates] = useState<ApiResult<Template[]> | null>(null);
  const [first, setFirst] = useState<number | null>(null);
  const [second, setSecond] = useState<number | null>(null);
  const [data, setData] = useState<boolean | null>(null);
  const [name, setName] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [refusal, setRefusal] = useState<ApiResult<Project> | null>(null);
  const ids = { first: useId(), second: useId(), data: useId() };
  const heading = useRef<HTMLHeadingElement>(null);

  // The focus starts on the form's heading, so Tab goes to its first question.
  useEffect(() => {
    heading.current?.focus();
  }, []);

  useEffect(() => {
    let live = true;
    void client.listTemplates().then((result) => {
      if (live) setTemplates(result);
    });
    return () => {
      live = false;
    };
  }, [client]);

  const served = templates?.kind === "ok" ? templates.data : [];
  const titleOf = (id: string | undefined) => served.find((item) => item.id === id)?.title;
  const chosenFirst = first === null ? undefined : ANSWERS[first];
  const chosen = chosenFirst?.second
    ? second === null
      ? undefined
      : chosenFirst.second[second]
    : chosenFirst;
  const template = chosen?.template;
  // The name starts as the chosen template's title until the user types one.
  const shownName = name ?? titleOf(template) ?? "";

  const missing =
    chosenFirst === undefined
      ? NEED_ANSWER
      : chosen === undefined
        ? NEED_SECOND
        : data === null
          ? NEED_DATA
          : shownName.trim() === ""
            ? NEED_NAME
            : null;

  const go = async () => {
    if (missing !== null || sending || template === undefined) return;
    setSending(true);
    setRefusal(null);
    const result = await client.createProject({ name: shownName, template });
    setSending(false);
    if (result.kind === "ok") onCreated(result.data, data === true);
    else setRefusal(result);
  };

  const option = (item: Answer, group: string, checked: boolean, pick: () => void) => {
    const title = item.template !== undefined ? titleOf(item.template) : undefined;
    // Unavailable only once the service has listed its templates without this one.
    const unavailable =
      templates?.kind === "ok" && item.template !== undefined && title === undefined;
    return (
      <label key={item.answer} className="choice">
        <input type="radio" name={group} checked={checked} disabled={unavailable} onChange={pick} />
        <span>
          <span>{item.answer}</span>
          <span className="small muted">
            {item.second
              ? "Asks one more question"
              : unavailable
                ? NOT_INSTALLED
                : title !== undefined
                  ? `Opens: ${title}`
                  : null}
          </span>
        </span>
      </label>
    );
  };

  return (
    <section className="build-form" aria-labelledby="build-heading">
      <h1 id="build-heading" className="title" ref={heading} tabIndex={-1}>
        Build a model
      </h1>
      <p className="muted">Two questions pick the closest template; your data is optional.</p>
      {templates !== null && templates.kind !== "ok" ? <ServiceProblem result={templates} /> : null}
      <fieldset className="choices">
        <legend>Step 1 of 2: What do you want to find out?</legend>
        {ANSWERS.map((item, index) =>
          option(item, ids.first, first === index, () => {
            setFirst(index);
            setSecond(null);
          }),
        )}
      </fieldset>
      {chosenFirst?.second ? (
        <fieldset className="choices build-second">
          <legend>Which of these?</legend>
          {chosenFirst.second.map((item, index) =>
            option(item, ids.second, second === index, () => setSecond(index)),
          )}
        </fieldset>
      ) : null}
      <fieldset className="choices">
        <legend>Step 2 of 2: Do you have data?</legend>
        <label className="choice">
          <input
            type="radio"
            name={ids.data}
            checked={data === true}
            onChange={() => setData(true)}
          />
          <span>
            <span>Yes, import a file</span>
            <span className="small muted">Opens the Data screen (CSV or Excel)</span>
          </span>
        </label>
        <label className="choice">
          <input
            type="radio"
            name={ids.data}
            checked={data === false}
            onChange={() => setData(false)}
          />
          <span>
            <span>No, I will estimate</span>
            <span className="small muted">Opens the canvas with the parameters</span>
          </span>
        </label>
      </fieldset>
      <label className="field">
        <span>Project name</span>
        <input type="text" value={shownName} onChange={(event) => setName(event.target.value)} />
      </label>
      <ServiceProblem result={refusal} />
      <div className="button-row build-buttons">
        <button type="button" className="secondary" onClick={onBack}>
          Back
        </button>
        <button
          type="button"
          className="primary"
          aria-disabled={missing !== null || sending || undefined}
          aria-describedby={missing !== null ? "build-missing" : undefined}
          onClick={() => void go()}
        >
          {sending ? "Creating…" : "Continue"}
        </button>
        {missing !== null ? (
          <span id="build-missing" className="small muted">
            {missing}
          </span>
        ) : null}
      </div>
      <p className="small muted">Build mode never requires a data file.</p>
    </section>
  );
}
