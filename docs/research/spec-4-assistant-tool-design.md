# Assistant tool design: granularity, validation loops and error messages (spec 4, M7)

## Question

Spec 4 "Research before building", M7: "Assistant tool design. What the published
simulation-automation systems found about tool granularity, validation loops and error
messages." Done before any MCP server code (guide rule 3, AKS-115).

The M4 note `docs/research/spec-2-prior-art.md` (AKS-131) already reviewed the systems
that generate simulation models from text (DEVS Copilot, Schmitt et al., Krämer and
Heger, Chotaliya et al., Monks et al., Carreira-Munich et al., Chen et al., Lekshmi and
Karanjkar) and drew seven points for the MCP tools ("For the MCP tools"): a model file,
not code; errors as data and a validation loop; behaviour in the schema; edits, not
regeneration; streams kept out of the assistant's hands; checking mechanisms, not only
that a model runs; showing the model. This note does not repeat them. It adds what the
wider work on language-model agents and tool interfaces measured about the three
questions, and turns both notes into rules for the six read tools built now and the five
write and run tools of AKS-134:

1. **Granularity.** How many tools, and how much each should do.
2. **Validation loops.** What feedback after an action lets a model repair its own work.
3. **Error messages.** What an error should say, and how it should reach the model.

## Finding

### Granularity

- **Anthropic, "Writing effective tools for agents" (2025).** "More tools don't always
  lead to better outcomes. A common error we've observed is tools that merely wrap
  existing software functionality or API endpoints—whether or not the tools are
  appropriate for agents." Tools "can consolidate functionality, handling potentially
  multiple discrete operations (or API calls) under the hood" (their example: one
  `schedule_event` instead of separate list and create tools). Responses should be sized
  for a limited context: "some combination of pagination, range selection, filtering,
  and/or truncation"; low-level identifiers that mean nothing to the model are best left
  out; inputs "should be unambiguously named: instead of a parameter named `user`, try a
  parameter named `user_id`."
- **Gan and Sun, RAG-MCP (2025).** With many MCP tools in the prompt, tool selection
  degrades ("prompt bloat and selection complexity"); retrieving only the relevant tool
  descriptions "more than triples tool selection accuracy (43.13% vs 13.62% baseline)"
  and cuts prompt tokens by over half. The lesson for a small server is the converse: a
  short list of distinct tools needs no retrieval.
- **Yang et al., SWE-agent (2024).** An agent-computer interface (ACI) built for the model
  beat the plain Linux shell. Its design principles: "Actions should be simple and easy
  to understand for agents", "Actions should be compact and efficient", "Environment
  feedback should be informative but concise", "Guardrails mitigate error propagation and
  hasten recovery". Measured on SWE-bench Lite (GPT-4 Turbo, 18.0% resolved with the full
  interface): a search tool that summarised its results beat one that paged through them
  (12.0%), because agents stepped through every page; a file viewer of 100 lines beat 30
  lines (14.3%) and the whole file (12.7%); keeping only the last five observations in
  full beat keeping the whole history (15.0%).

### Validation loops

- **SWE-agent.** Its edit command ran a linter and refused an edit that introduced a
  syntax error, showing the error and the code before and after: removing that guardrail
  lowered the resolve rate from 18.0% to 15.0%, and removing the edit command (editing
  through the shell) to 10.3%. The paper ties this to "cascading errors" that begin with
  one bad edit.
- **Chen et al., "Teaching Large Language Models to Self-Debug" (2023).** Feeding the
  model the result of executing its program, with an explanation step, improved accuracy
  by up to 12% where unit tests exist and by 2 to 3% without them, and "by leveraging
  feedback messages and reusing failed predictions" matched baselines that sampled more
  than ten times as many candidates.
- **AhmadiTeshnizi et al., OptiMUS (2024).** An agent that formulates and solves (mixed
  integer) linear programs from text "can develop mathematical models, write and debug
  solver code, evaluate the generated solutions, and improve its model and code based on
  these evaluations", in a modular structure so that long problems need no long prompts;
  it improved on the previous best by more than 20% on easy and 30% on hard datasets.
  Feedback from the solver closes the loop for the optimization domain as validation does
  for the process domain.

### Error messages

- **Model Context Protocol, "Tools", "Error Handling" (2025-11-25).** Input validation
  errors and business logic errors are tool execution errors, "Reported in tool results
  with `isError: true`", which "contain actionable feedback that language models can use
  to self-correct and retry"; protocol errors (unknown tool, a malformed request) "are
  less likely" to be fixed by the model.
- **Anthropic (2025).** When a call fails, for example during input validation, "you can
  prompt-engineer your error responses to clearly communicate specific and actionable
  improvements, rather than opaque error codes or tracebacks"; error and truncation
  responses "can steer agents towards more token-efficient tool-use behaviors".
- **SWE-agent.** Feedback "informative but concise"; the linter's message named the
  problem and showed the code around it.

## Sources

- Anthropic, "Writing effective tools for agents — with agents", engineering blog, 2025-09-11, https://www.anthropic.com/engineering/writing-tools-for-agents (read 2026-11-08).
- T. Gan and Q. Sun, "RAG-MCP: Mitigating Prompt Bloat in LLM Tool Selection via Retrieval-Augmented Generation", arXiv:2505.03275, 2025, https://arxiv.org/abs/2505.03275 (abstract read 2026-11-08).
- J. Yang, C. E. Jimenez, A. Wettig, K. Lieret, S. Yao, K. Narasimhan and O. Press, "SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering", NeurIPS 2024, arXiv:2405.15793, https://arxiv.org/abs/2405.15793 (abstract, introduction and the ablation table of the HTML version read 2026-11-08).
- X. Chen, M. Lin, N. Schärli and D. Zhou, "Teaching Large Language Models to Self-Debug", arXiv:2304.05128, 2023, https://arxiv.org/abs/2304.05128 (abstract and introduction read 2026-11-08).
- A. AhmadiTeshnizi, W. Gao and M. Udell, "OptiMUS: Scalable Optimization Modeling with (MI)LP Solvers and Large Language Models", arXiv:2402.10172, 2024, https://arxiv.org/abs/2402.10172 (abstract and introduction read 2026-11-08).
- Model Context Protocol, specification 2025-11-25, "Tools", https://modelcontextprotocol.io/specification/2025-11-25/server/tools (read 2026-11-08).
- `docs/research/spec-2-prior-art.md` (AKS-131), "For the MCP tools".

## Decision

Spec 4's eleven tools stand; nothing found contradicts them. The rules below shape how
they are built (AKS-115 for the six read tools, AKS-134 for the rest) and what the
real-assistant trial (AKS-116) should watch.

1. **Few, distinct tools around the workflow, not one per block or endpoint.** Eleven
   tools follow the user's steps (find a template, read the format, create, edit,
   validate, run, poll, read results); there is no tool per block type and no tool for
   the data endpoints, which need a file the assistant does not have. `get_results`
   already consolidates the summary and the tables. `POST /v1/projects/open` stays out
   (spec 3), as does any WebSocket.
2. **Narrow before wide.** `get_schema` without `component_type` returns the whole
   composed schema (about 11,000 characters measured below); with one it returns one
   type's settings, ports and metrics (about 800). Its description tells the assistant
   to ask for one type at a time, as SWE-agent's 100-line window beat the whole file.
3. **Unambiguous inputs.** Inputs are named for what they hold (`project_id`,
   `component_type`, `run_id`, `experiment_id`), as spec 4 has them; each is declared in
   the input schema with `additionalProperties: false`.
4. **Every action answers with its consequence.** A write returns the model, its
   revision and its validation issues (spec 3 "Model edits"), and an edit that cannot be
   applied is refused with E180 and nothing saved: the guardrail SWE-agent measured.
   `validate_model` gives the full check, the adapter's included, before a run.
5. **Errors are tool results, worded for the model.** Every failure the model could fix
   (a service refusal with its spec 1 issues, a missing or mistyped input) is a result
   with `isError` true, carrying codes, `path`, `message` and `hint` written by lcsim,
   never a traceback. An input problem is an E184 issue whose `path` points at the input
   (`/project_id`), as the service points E184 into a request body. A service that
   cannot be reached or started is one issue too (a new spec 1 code, E193), with a hint
   that says what the user can do. Only an unknown tool name is a protocol error.
6. **Descriptions teach the format** (spec 4): each says which endpoint it calls, what
   comes back and when to use it, with one worked example of arguments and an abridged
   result. `get_schema`'s also states the behaviour defaults the AKS-131 note asked for
   (server queue unlimited and first in first out, a source that discards when blocked,
   a queue that blocks when full, failure as preempt-resume, capacity 0 outside listed
   shifts, a pooled server taking its own unit first), taken from spec 2's "Block
   reference" and its rules.
7. **Measure in the trial.** AKS-116's real-assistant trial records, per attempt, the
   tool calls, the tool errors and which issue codes the assistant could repair from the
   hint alone, as the Anthropic article recommends tracking tool errors; tool changes it
   causes go in DECISIONS (spec 4 "Assistant acceptance case").

For AKS-134, from the AKS-131 note and the rules above: `create_model`'s and
`edit_model`'s worked examples should include a pool shared by two servers, a weekly
`schedule` and a night shift split at the end of the period; edits stay small and return
the whole model and revision.

## Tested

On 2026-11-08, at `main` `a4c4551`, Python 3.13.18, from a script in a scratch directory
outside the repository; no product code was written or changed. The script built the
M6 application with `lcsim.service.app.create_app` on temporary folders and called it
with Starlette's `TestClient`:

- Sizes are of the parsed body written again with `json.dumps` (the wire body, compact,
  is about 8% smaller). `GET /v1/schema` returned 11,261 characters of JSON (keys `$schema`, `title`,
  `description`, `type`, `required`, `additionalProperties`, `properties`, `allOf`,
  `$defs`, `x-component-types`); `GET /v1/schema/components/server` returned one object
  of 834 characters with its settings (`capacity`, `service`, `queue_capacity`,
  `discipline` with default `fifo`, `pool`) and metrics. So narrowing by type saves more
  than 90% of the answer.
- `GET /v1/schema/components/queue` lists `on_full` with default `block` and
  `discipline` with `fifo`; `failure`, `schedule` and `resource_pool` list no behaviour
  default beyond `period` `86400 s`, and their one-sentence descriptions do not state
  preempt-resume or the shift rules, which is why rule 6 puts them in the tool
  description.
- After an `add_component` of a `server` with empty `params`, `POST .../validate`
  returned two E122 issues, each with `component` `till`, a `path`
  (`/components/0/params/capacity`), a message naming the component and the setting, and
  a hint ("Add 'capacity' to the 'params' of 'till'."): the information rule 5 relies on
  is in the service's answer already.
- `GET /v1/schema/components/nope` returned 404 with `{"error": {"code": "E185",
  "message": "No installed engine has the component type 'nope'."}, "issues": []}`: the
  code and message reach the model even where `issues` is empty.
