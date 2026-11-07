# Prior art on generating process models from text (spec 2, M4)

## Question

Spec 2 "Research before building", M4: "Prior art. Papers on generating process simulation
models from text, for the block design." M4 builds the seven blocks that have never run:
`queue`, `batch`, `unbatch`, `store`, `resource_pool`, `schedule` and `failure`. Before
they are built, does published work on turning text into process simulation models point
to a change in their entries in spec 2 "Block reference" (ports, settings, behaviour)?
Three kinds of work bear on it:

- LLMs that write discrete-event models (SimPy and others) from a description, and
  conversational model-building assistants;
- process mining and BPMN-to-simulation pipelines, which find out from data which
  constructs a process model needs;
- studies that report which constructs such generators get wrong.

Two limits apply. The block behaviour defaults in spec 2 (the list under "Proposed
defaults chosen by the review council") are owner decision AKS-76, unanswered: this note
does not decide them and only says where prior art supports or questions one. And the MCP
tools (spec 4) are built at M7: what the findings mean for them is recorded here for that
milestone, not built.

## Finding

### What the generators are and where they fail

Eight studies that generate process models from text were read (details under Sources).
They split into two designs:

| Design | Studies | What the language model writes |
| --- | --- | --- |
| Free code | Jackson, Sáenz and Ivanov (2024); Monks, Harper and Heather (2025); Chen et al. (2026); Krämer and Heger (2026) | A whole SimPy or plain Python program |
| Code from a fixed structure | Schmitt et al. (2026) (a SimPy "blueprint" adapted one-shot); Carreira-Munich, Paz-Marcolla and Castro (2024) (a DEVS specification in a small grammar, parsed to code); Chotaliya et al. (2025) (a structured dictionary fed to a fixed engine); Lekshmi and Karanjkar (2025) (an interconnection of pre-built FactorySimPy components) | A structured description that existing code turns into a model |

The free-code studies report the same kind of failure: code that runs but implements the
wrong mechanism. Chen et al. make it their measure ("instruction-mechanism consistency")
and break it down by mechanism. After their fine-tuning, a 7-billion-parameter model
implemented the mechanism correctly in 97.5% of finite-capacity tasks and 95.4% of
two-resource tasks, but only 72.5% of batch arrivals, 62.9% of piecewise (time-varying)
arrivals, 57.5% of balking and reneging, 52.5% of feedback networks, 33.3% of open
networks and 32.5% of breakdown with repair (their Table 4). Their error analysis names
two patterns: in a network the model "may generate a new and unrelated arrival at the
downstream node" instead of moving the customer on, and after a breakdown it "does not
always maintain a correct record of the remaining service time", so "a customer [may]
redo portions of service that were already completed before the breakdown". Schmitt et
al. report, over 21 generated models of two production lines, a run that crashed in its
second week from the way the model "had defined the production hours", a break applied
to the wrong day, an "invented parallel operation", routing errors in a splitter built
from helper buffers, and helper stores confused with real buffers, which gave wrong
work-in-process values. Chotaliya et al. found that GPT-4 without fine-tuning "Improperly
handled: lead time, data logging, inventory update and warm-up period" in inventory
models. Monks, Harper and Heather needed extra prompts because the model struggled "to
assign streams across model activities", and found that the published text of a model
had to be rewritten to "Precisely define which resources are used ... and if these are
shared with other types of patients". Jackson, Sáenz and Ivanov could not get a valid
single-server queue from a description alone; it took a detailed description, the
variables to use and an example of how to handle an arrival.

The structured designs report fewer such errors and place the remaining ones elsewhere.
Lekshmi and Karanjkar argue that if generation "is framed as the composition of pre-built,
configurable components ... using well-defined interconnection rules, the resulting
models can be more easily validated and are often correct-by-construction", and note that
deadlocks "are still possible with certain system descriptions, but easier to spot".
Carreira-Munich et al. split a semantic stage from a syntactic one so that "a field
ordering problem in a specification is not conceptually equivalent to the model behaving
incorrectly"; every case reached a correct model, after up to three refinements, and the
variant with no conversation history repeated mistakes it had been corrected on. Krämer
and Heger found that "purely technical errors are easy to identify and correct" and that
the hard part is domain knowledge; their elicitation agent asks about "initial and final
states as well as any control logic" before any code is written.

### Which constructs the sources need

| Construct | Who needs it | Spec 2 block |
| --- | --- | --- |
| Finite buffer with blocking or loss | Chen et al. ("Limited queue length K", "Blocking and system loss constraints"); Monks et al. (elective patients cancelled when every bed is in use); Schmitt et al. and Krämer and Heger (buffers between machines) | `queue` (`capacity`, `on_full`), server `queue_capacity` |
| Batching and splitting | van der Aalst (2015) risk 15, "Ignoring that people work in batches"; Martin et al. (2015), three types: simultaneous, sequential, concurrent; Schmitt et al. (batch processing as a high-complexity change); simmer `batch(n, timeout)` and `separate()` | `batch`, `unbatch` |
| Inventory with replenishment | Jackson et al. (a single-product model whose replenishment adds "the order quantity"); Chotaliya et al. (orders when stock falls below a threshold, "refilled to a predefined maximum level"; also demand-driven and periodic supply) | `store` |
| Shared resources | Chen et al. ("Joint resource coordination", "Parallel processing or shared-resource synchronization"); Monks et al. (beds shared by patient classes); van der Aalst risk 13, "Ignoring that people are involved in multiple processes" | `resource_pool` |
| Shifts, calendars, breaks | van der Aalst risk 15 ("calendars and shifts are typically ignored in simulation tools"); López-Pintado and Dumas (2025): mainstream tools, the BPSim standard included, give each resource a calendar such as "Monday-Friday, 9:00-18:00"; Schmitt et al. (weekly breaks); simmer `schedule(timetable, values, period)` | `schedule` |
| Breakdown and repair | Chen et al. (`breakdown_maintenance`); Schmitt et al. (exponential failures and MTTR in the blueprint) | `failure` |
| Several entity classes, priority | Chen et al. (`multi_class_customers`); Monks et al. (six patient classes; emergencies take priority) | Deferred to Phase 2 (spec 2 "Block reference", spec 1) |
| Balking and reneging | Chen et al.; Monks et al. (balking only) | Balking as loss at a full block; no reneging |
| Time-varying arrivals | Chen et al. (`piecewise_arrival`, "Time-varying or piecewise arrival rate") | None in "Block reference" (below) |
| Assembly of different parts | Chotaliya et al. ("Every finished product must require at least one type of raw material") | None |
| Partial or intermittent availability, multitasking | van der Aalst risks 13 and 15; López-Pintado and Dumas | None |

Each of the seven M4 blocks matches a construct in this table that at least two sources
need (`unbatch` as the partner of `batch`). The constructs with no block are either
already deferred (classes, priority) or go beyond Phase 1 (reneging, assembly,
probabilistic calendars, multitasking).

### The seven blocks against the sources

- **`queue`.** The sources need a buffer separate from the machine, with a capacity and a
  rule for a full buffer (block or lose the item). Schmitt et al.'s confusion of helper
  stores with real buffers, and the wrong WIP it caused, is the failure a single explicit
  `queue` type avoids. Spec 2's settings (`capacity`, `discipline`, `on_full` with `block`
  or `discard` counted in `<queue>.discarded`) cover each case read.
- **`batch` and `unbatch`.** simmer has the same pair (`batch` with a size `n` and an
  optional `timeout`; `separate`), which confirms the settings. Spec 2's `batch` is
  Martin et al.'s simultaneous type (the batch moves as one item). Their sequential type
  (one person letting work pile up, then doing it item by item) can be approximated by a
  `batch`, a server whose one service time stands for the whole batch, and an `unbatch`;
  the sources read give no case that needs item-by-item service inside a batch. simmer's
  documentation does not say when its timer starts ("triggers batches every `timeout` time
  units even if the batch size has not been fulfilled"), so it neither supports nor
  questions spec 2's proposed "after a batch's first item arrived" (AKS-76).
- **`store`.** Spec 2's store is a continuous-review reorder point with a fixed order
  quantity and a random lead time: an order of `order_quantity` when stock on hand plus on
  order falls to `reorder_point`. Chotaliya et al.'s main scheme orders up to a maximum
  level instead, and they also use periodic and demand-driven supply; Jackson et al.'s
  generated model adds "the order quantity" at each replenishment, as spec 2's store adds
  `order_quantity`. Lead time and stock updates are what an unaided model got wrong in
  Chotaliya et al., which a block with these four settings fixes once. An order-up-to
  level is a different policy, not a defect of this one; it is listed under "Left for the
  owner".
- **`resource_pool`.** Chen et al. and Monks et al. need one pool of units shared by
  several activities, which is spec 2's `resource_pool` named in each server's `pool`. The reliability figure for this mechanism (95.4%) is among the highest
  in Chen et al., and Monks et al.'s fix was to name the shared resource exactly, which a
  pool's identifier does. Van der Aalst's point that five people at 20% are not one person
  at 100% needs partial availability, which no Phase 1 block has.
- **`schedule`.** A capacity that changes over a repeating period is the standard form
  (López-Pintado and Dumas; simmer's `schedule` takes change points, values and a
  `period`). Schmitt et al.'s two calendar errors (a crash in the second week, a break on
  the wrong day) both came from hand-written calendar code, which a declarative `shifts`
  list with a `period` removes. The calendars in the sources are weekly (Monday to
  Friday; Friday 17:00 to Saturday 07:00), so a model of them sets `period` to 7 d; the
  24 h default stays. A night shift that crosses the end of the period is written as two
  shifts, since spec 2 "Ranges" requires `end` after `start` and no later than `period`. None
  of the sources read says what happens to an item in service when a shift ends, so they
  neither support nor question the proposed "finishes its current item, then stops"
  (AKS-76). López-Pintado and Dumas show that on-or-off calendars miss intermittent
  availability; that is an extension, not a change to `schedule`.
- **`failure`.** Breakdown with repair is the mechanism generated code got wrong most
  often (32.5% correct in Chen et al.), and the error they show is exactly the
  remaining-time bookkeeping of preempt-resume. That argues for a block with one stated
  rule over leaving it to the model author. It supports spec 2 stating preempt-resume
  explicitly; it does not say that preempt-resume is the right default rather than, say,
  restarting the service (that choice is AKS-76). No source read addresses whether the time
  to failure runs while the unit is idle.

### Time-varying arrivals

Spec 2's summary table says a source makes "Arrivals, by distribution or from a schedule",
but its binding "Block reference" gives a source only `interarrival`, `first_arrival` and
`max_items`, and a `schedule` targets a server or a pool (the catalogue's `target`
reference allows `server` and `resource_pool` only). Under "The sections below are
binding. Where they differ from the summary above, these win", Phase 1 has no
time-varying arrivals. Chen et al. treat them as a common mechanism
(`piecewise_arrival`), so this is a real gap for the owner, not an M4 change: no M4
acceptance row or benchmark needs it.

## Sources

Bibliographic details were checked against Crossref (api.crossref.org) on 2026-11-07.
"Read" means the text was opened and the statements above taken from it; "record only"
means only the bibliographic record was seen.

LLM generation of process models:

- Ilya Jackson, Maria Jesus Saenz and Dmitry Ivanov, "From natural language to
  simulations: applying AI to automate simulation modelling of logistics systems",
  International Journal of Production Research 62(4), 1434–1457, 2024 (online 2 November
  2023), doi:10.1080/00207543.2023.2276811. Read (the publisher's full text): section 4.2
  (the framework, human validation) and 4.3 (inventory model from a description; the
  queue needed a detailed description, variables and an example); section 5.1 ("toy-like
  problems").
- Thomas Monks, Alison Harper and Amy Heather, "Unlocking the potential of past research:
  using generative AI to reconstruct healthcare simulation models", Journal of the
  Operational Research Society 77(7), 1819–1842, 2026 (online 10 September 2025),
  doi:10.1080/01605682.2025.2554751. Read (the publisher's full text): the two case
  study descriptions, the random number streams, sections 6.1 and 6.2 (Box 1 on shared
  resources, common tokens), the results with their prompt counts and the
  stream-assignment difficulty, and section 9 (lost code in long contexts, time-consuming
  prompt engineering, the caution against an all-in-one prompt).
- Jun-Qi Chen, Kun Zhang, Rui Zheng and Ying Zhong, "Mechanism-Faithful Queueing
  Simulation Model Translation with Large Language Model Support", arXiv:2601.06543v2,
  5 May 2026 (version 1 was titled "SimLLM: Fine-Tuning Code LLMs for SimPy-Based Queueing
  System Simulation"), https://arxiv.org/abs/2601.06543. Read (the HTML full text):
  sections 1 to 3, Table 2 (the twelve mechanism categories), Table 4 and section 6.1
  (per-category results), section 7.1 (error analysis). A preprint, not peer reviewed.
- Roman Krämer and Jens Heger, "Automated Generation of Simulation Models for Production
  and Logistics Processes Using LLM-Based Multi-Agent Systems", SNE Simulation Notes
  Europe 36(1), 9–14, 2026, doi:10.11128/sne.36.tn.10762,
  https://www.sne-journal.org/fileadmin/user_upload_sne/SNE_Issues_OA/SNE_36_1/articles/sne.36.1.10762.tn.OA.pdf.
  Read: the five agents, the case study and the summary.
- Thomas Schmitt, Nils Gegenmantel, Matías Urenda Moris, Pär Mårtensson and Kaveh
  Amouzgar, "LLM-driven discrete-event simulation: A generative AI framework for automated
  model generation, adaptation, and evaluation in manufacturing", Journal of Manufacturing
  Systems 85, 642–661, 2026, doi:10.1016/j.jmsy.2026.02.015. Read (a full-text copy
  through the DOI): section 4 (agents, blueprint, inspector), section 5 (the blueprint,
  Cases A and B and their errors).
- Tobias Carreira-Munich, Valentín Paz-Marcolla and Rodrigo Castro, "DEVS Copilot:
  Towards Generative AI-Assisted Formal Simulation Modelling based on Large Language
  Models", Proceedings of the 2024 Winter Simulation Conference, 2785–2796,
  doi:10.1109/WSC63780.2024.10838994, https://informs-sim.org/wsc24papers/satwcon104.pdf.
  Read: section 3 (the two stages), section 4 (acceptability criteria, Table 1) and
  section 5.1.
- Surdeep Chotaliya, John Fowler, Giulia Pedrielli, David Bayba, Mikayla Norton, Priyanka
  Sain and Kaixu Yu, "A Foundational Framework for Generative Simulation Models: Pathway to
  Generative Digital Twins for Supply Chain", Proceedings of the 2025 Winter Simulation
  Conference, 1700–1711, doi:10.1109/WSC68292.2025.11339118,
  https://www.informs-sim.org/wsc25papers/inv188.pdf. Read: section 3.1 (procurement
  schemes, feasibility checks), section 4 (Table 2).
- P. Lekshmi and Neha Karanjkar, "Bridging Expertise and Automation: A Hybrid Approach to
  Automated Model Generation for Digital Twins of Manufacturing Systems", Proceedings of
  the 2025 Winter Simulation Conference, 2800–2811, doi:10.1109/WSC68292.2025.11339109,
  https://nehakaranjkar.github.io/publications/WSC2025_LekshmiP_Karanjkar.pdf. Read:
  sections 1 to 4 and the conclusion (FactorySimPy, correct-by-construction composition,
  Table 1).

Process mining and business process simulation:

- Wil M. P. van der Aalst, "Business Process Simulation Survival Guide", in Handbook on
  Business Process Management 1, Springer, 337–370, 2015 (Crossref dates the chapter
  2014), doi:10.1007/978-3-642-45100-3_15, https://www.vdaalst.com/publications/p808.pdf.
  Read: section 5.2, risks 11 to 15.
- Orlenys López-Pintado and Marlon Dumas, "Business process simulation: Probabilistic
  modeling of intermittent resource availability and multitasking behavior", Information
  Systems 127, 102471, 2025, doi:10.1016/j.is.2024.102471. Read: the abstract and
  introduction of the preprint, https://arxiv.org/abs/2410.16941.
- Niels Martin, Marijke Swennen, Benoît Depaire, Mieke Jans, An Caris and Koen Vanhoof,
  "Batch Processing: Definition and Event Log Identification", in Data-driven Process
  Discovery and Analysis (SIMPDA 2015), CEUR Workshop Proceedings 1527, paper 11, 2015,
  https://ceur-ws.org/Vol-1527/paper11.pdf. Read: sections 1 to 3 (the three batch types).

A block-based library for comparison:

- simmer reference pages for `batch`/`separate` and `schedule`,
  https://rdrr.io/cran/simmer/man/batch.html and
  https://rdrr.io/cran/simmer/man/schedule.html (opened 2026-11-07). Read. The package is
  described in Iñaki Ucar, Bart Smeets and Arturo Azcorra, "simmer: Discrete-Event
  Simulation for R", Journal of Statistical Software 90(2), 2019,
  doi:10.18637/jss.v090.i02 (record only).

## Decision

**The spec 2 "Block reference" entries of all seven M4 blocks stand unchanged.** No
finding shows a setting, port or behaviour that is wrong or missing for the M4 benchmarks
and acceptance rows. Spec 2 is not edited. Block by block:

| Block | Verdict | Why |
| --- | --- | --- |
| `queue` | Stands | Finite buffers with blocking or loss are needed by four of the sources, and its settings cover each case. A separate buffer type avoids the helper-buffer confusion Schmitt et al. report. |
| `batch` | Stands | Same shape as simmer's `batch(n, timeout)`; it is the simultaneous batch type. simmer's documentation does not say when its timer starts, so the AKS-76 timeout default is neither supported nor questioned. |
| `unbatch` | Stands | Same as simmer's `separate()`; no source needs settings on it. |
| `store` | Stands | A reorder point with a fixed quantity and a random lead time is one of the policies the sources use, and lead time and stock updates are what generated code got wrong. Order-up-to and periodic review are other policies, left for the owner. |
| `resource_pool` | Stands | A pool shared by several servers, named exactly, is what Chen et al. and Monks et al. needed. The AKS-76 seizing order (own unit, then pool unit) is not addressed by any source read. |
| `schedule` | Stands | A shifts list repeating over a `period` is the standard calendar form; it replaces the hand-written calendar code that failed in Schmitt et al. Weekly calendars set `period` to 7 d. The AKS-76 shift-end default is not addressed by any source read. |
| `failure` | Stands | The construct generated code most often gets wrong, with the preempt-resume bookkeeping as the shown error, so a block with a stated rule is supported. Whether preempt-resume is the right default stays AKS-76. |

Where prior art bears on AKS-76 (for the owner, not decided here): it supports
**stating** a preempt-resume rule for `failure` (the one default with direct evidence
that an unstated rule goes wrong), and neither supports nor questions the source, schedule,
batch timeout, pool and targets defaults.

**Left for the owner** (no spec change; each listed under "Awaiting owner"):

1. Time-varying arrivals. Spec 2's summary promises a source "from a schedule"; the binding
   block reference has none, so Phase 1 has none. Chen et al. treat piecewise arrivals as a
   common mechanism. Either the summary is corrected or a later version adds a source
   schedule.
2. Constructs with no Phase 1 block: reneging, assembly of different parts, an order-up-to
   or periodic `store` policy, partial or probabilistic availability and multitasking.
   Classes and priority are already deferred to Phase 2.

**For the MCP tools (spec 4, M7; recorded, not built now):**

- **A model file, not code.** The structured designs (a fixed engine fed a structure, a
  grammar, a component library) avoided the mechanism errors of free code. This supports
  spec 4's "Model files only" rule; M7 keeps it.
- **Errors as data and a validation loop.** Every structured design checks the structure
  and feeds problems back (DEVS Copilot's refinements, Schmitt et al.'s inspector,
  Krämer and Heger's validator, Chotaliya et al.'s feasibility checks). Spec 4's "Errors
  are data" and `validate_model` match; M7 should test that the issue hints are enough for
  an assistant to correct a model without other help.
- **Behaviour in the schema.** The ambiguity Monks et al. had to remove by hand (which
  resource is shared) and the questions Krämer and Heger's agent asks (start state,
  control logic) suggest that `get_schema` for a component type should state its behaviour
  defaults (`on_full`, preempt-resume, what happens at a shift end), so an assistant can
  tell the user what it assumed. Worked examples in the tool descriptions should include a
  pool shared by two servers, a weekly `schedule` and a night shift split at the end of the
  period.
- **Edits, not regeneration.** Long contexts lost code (Monks et al.) and a stage with no
  history repeated corrected mistakes (Carreira-Munich et al.). `edit_model` returning the
  whole model and its revision keeps the current state in front of the assistant; M7 keeps
  edits small and incremental.
- **Streams stay out of the assistant's hands.** Assigning streams was hard for the model
  (Monks et al.); spec 1 assigns one stream per component automatically, so no tool should
  expose per-component seeds.
- **Check mechanisms, not only that a model runs.** Chen et al. separate "runs" from
  "implements the mechanism". Spec 4's assistant acceptance case already checks results
  against theory; M7 may add a case with a `failure` or a `resource_pool`, the mechanisms
  the sources find hardest, with the M4 benchmark answers as the known values.
- **Show the model.** Lekshmi and Karanjkar generate a block diagram and Schmitt et al. a
  flow chart for visual checking; spec 4's "Visible to the user" (models open on the
  canvas) matches.

## Tested

On 2026-11-07, at `main` `8feb02e`, Python 3.13.18, from a script in a scratch directory
outside the repository; no product code was written or changed. The script reads the
"Block reference" table of `docs/specs/2-core-engine.md` and compares it with the
`process` type catalogue, `PROCESS_TYPES` in `src/lcsim/model/catalogue.py`, and with the
adapter's `ProcessAdapter().capabilities().component_types`:

```python
import re
import sys
from pathlib import Path

from lcsim.engines.process.adapter import ProcessAdapter
from lcsim.model.catalogue import PROCESS_TYPES

spec = Path(sys.argv[1]).read_text().splitlines()
rows = {}
for line in spec[spec.index("### Block reference") :]:
    if line.startswith("### Statistic"):
        break
    m = re.match(r"\| `(\w+)` \| ([^|]*) \| ([^|]*) \|", line)
    if m:
        rows[m.group(1)] = (m.group(2), m.group(3))
print("same set:", set(rows) == set(PROCESS_TYPES))
for name in ["queue", "batch", "unbatch", "store", "resource_pool", "schedule", "failure"]:
    ports, settings = rows[name]
    named = [w for w in re.findall(r"`(\w+)`", settings) if w not in {"block", "discard"}]
    block = PROCESS_TYPES[name]
    print(
        name,
        ports.strip(),
        block.inputs,
        block.outputs,
        named,
        [(s.name, s.kind.value, s.required, s.default, s.refers_to) for s in block.settings],
    )
print("adapter equals catalogue:", ProcessAdapter().capabilities().component_types == PROCESS_TYPES)
```

Result: the table and the catalogue name the same twelve types, and for each of the seven
M4 blocks the same settings in the same order with the same ports:

| Block | Ports (spec, catalogue) | Settings: spec 2 | Catalogue |
| --- | --- | --- | --- |
| `queue` | `in`, `out` | `capacity` (integer), optional `discipline`, optional `on_full` | `capacity` number, required, minimum 1; `discipline` optional, default `fifo`; `on_full` optional, default `block` |
| `batch` | `in`, `out` | `size` (integer), optional `timeout` (time quantity) | `size` number, required, minimum 1; `timeout` time quantity, optional, above 0 s |
| `unbatch` | `in`, `out` | none | none |
| `store` | `in`, `out` | `initial`, `reorder_point`, `order_quantity` (integers), `lead_time` (distribution) | three numbers, required (`order_quantity` minimum 1); `lead_time` a time distribution |
| `resource_pool` | none | `capacity` (integer) | `capacity` number, required, minimum 1 |
| `schedule` | none | `target`, `shifts`, optional `period` (time quantity, default 24 h) | `target` a reference to a `server` or `resource_pool`; `shifts` a list of `{start, end, capacity}`; `period` optional, default 86,400 s |
| `failure` | none | `target`, `time_to_failure`, `time_to_repair` | `target` a reference to a `server`; both times time distributions |

The minimums, integer flags and the `shifts` fields in the last column were read from
`catalogue.py` itself; they match spec 2 "Ranges". The adapter's capabilities equal the catalogue (`True`), as
`tests/engines/test_registry.py` also asserts. The table does not name the kinds of the
`schedule` and `failure` settings; the catalogue's readings agree with the rest of the
binding text: a `schedule` "Changes the capacity of a server or pool", a `failure` "Takes a
server out of service", spec 2's Failure default says `time_to_failure` "is sampled",
the M4 failure benchmark gives both times as exponential distributions, and spec 1
"Random streams" names them as a component with two distributions. E125 (spec 1) limits a
server to one `schedule` and one `failure`, matching the Targets default. So the block
names and settings in spec 2 and the code agree, and nothing in this note asks the M4
tickets to change either.

Also checked: spec 4 "MCP server" and "MCP tools" (the tool list, "Model files only",
"Errors are data", "Tool descriptions teach the format") for the M7 notes above, and the
M4 benchmark rows of spec 2 "Benchmark definitions", none of which needs a source schedule
or a construct from "Left for the owner".
