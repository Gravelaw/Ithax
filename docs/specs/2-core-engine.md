# Spec 2: Core Engine for Process Simulation and Optimization

> Version 0.3 · working copy in the repository (source of truth, owner to confirm) · changes are listed under "Changes in this version".

Two engine adapters, both in Python: discrete-event simulation on SimPy, and optimization on HiGHS; Optuna is a search driver inside the experiment manager, not an adapter. Together with an experiment manager they make Phase 1 a complete product.

> **Warning: partly tested.** Five block types ran in a prototype. The other seven, the optimization layout in the model file, and simulation-based optimization have never run. Performance targets are proposals. Verify each at its milestone and update this spec. See "Known gaps" in the Build guide.

## Scope

- **In:** the process block library, probability distributions, the experiment manager, mathematical optimization, simulation-based optimization, benchmarks.
- **Out:** agent-based and system dynamics models (spec 5), any physics (spec 6).

## Process block library

| Block | Models |
| --- | --- |
| Source | Arrivals, by distribution or from a schedule |
| Queue | A waiting line with a discipline (first in first out, last in first out) and optional capacity |
| Server | A resource that processes items, with capacity and service time |
| Delay | A fixed or random wait with no resource, such as transport or drying |
| Branch | Routing by probability or shortest queue |
| Batch, Unbatch | Grouping items and splitting them again |
| Store | Inventory with a reorder rule |
| Resource pool | Shared staff or tools needed by several servers |
| Schedule | Shifts and breaks applied to a server or pool |
| Failure | Random breakdown and repair of a server |
| Sink | Departure, where statistics are recorded |

Distributions: exponential, normal, lognormal, triangular, uniform, Weibull, constant, and empirical from imported data.

## Outputs

Throughput, cycle time, waiting time and queue length per queue, utilization per server and pool, work in progress, stock level and stock-outs per store. Each comes as a mean, a confidence interval and a time series.

## Experiment manager

- **Replications:** every replication draws its random streams from the experiment seed as spec 1 defines; the seed is recorded in the manifest.
- **Warm-up:** an initial period is excluded from statistics.
- **Confidence intervals:** 95% by default, computed across replications.
- **Scenarios:** named sets of parameter values, compared as paired differences with their own confidence intervals.
- **Parallel runs:** replications use all available processor cores.

## Optimization

| Kind | Use | Engine |
| --- | --- | --- |
| Mathematical | Problems written as an objective and constraints: product mix, transport, assignment, blending, scheduling | HiGHS through Pyomo |
| Simulation-based | Finding the best parameter values of a simulation model, such as number of machines | Optuna, with a set replication budget per candidate |

Mathematical problems are entered in a table-style editor: decision variables, objective, constraints. Simulation-based optimization picks any entries from `parameters` as variables and any output as the objective.

## Benchmarks

| Case | Known answer | Milestone |
| --- | --- | --- |
| Single server queue with random arrivals and service (M/M/1) | Mean wait from queueing theory | M2 |
| Multi-server queue (M/M/c) | Erlang C formula | M2 |
| Two queues in series | Product-form result | M2 |
| Delay | Little's law | M2 |
| Branch by probability | Weighted split of arrivals | M2 |
| Queue with loss | M/M/1/K loss formula | M4 |
| Batch and unbatch | Mean batch wait (size − 1)/(2λ) | M4 |
| Store, deterministic | Cycle analysis | M4 |
| Resource pool | M/M/1 and M/M/2 through a pool | M4 |
| Schedule, deterministic | Event-by-event calculation | M4 |
| Failure | Availability MTTF/(MTTF + MTTR) | M4 |
| Four small linear and integer programs | Answers verified by enumeration, listed below | M5 |
| Transport plan | With the indexed layout | M10 |
| Machine count, simulation-based | Erlang C | M5 |

A simulation benchmark checks every known answer in its row. A check passes when |estimate − known answer| ≤ 3 × standard error, the standard error being the sample standard deviation of the replication means divided by √n (a correct engine fails about 3 in 1,000 rerolls rather than 1 in 20). Deterministic cases must match exactly to four significant figures. Optimization benchmarks pass when the objective matches to four significant figures. Benchmark seeds are fixed in the benchmark files and queue cases use 100 replications so that a 5% bias in a mean wait is detected. A failure after a change that alters random-number use is investigated and recorded in `docs/DECISIONS.md`; a seed is changed only when the coverage run (20 consecutive seeds, `pytest -m benchmark_coverage`, run by hand) shows the case passing at least 19 of 20 times, proving a reroll, and the entry cites that run.

## Detailed specification

The sections below are binding. Where they differ from the summary above, these win.

### Block reference

| Type | Ports | Settings | Behaviour |
| --- | --- | --- | --- |
| `source` | `out` | `interarrival` (distribution), optional `first_arrival`, `max_items` | Creates one item, waits one interarrival time, repeats |
| `server` | `in`, `out` | `capacity` (integer), `service` (distribution), optional `queue_capacity`, `discipline`, `pool` | Items wait in the server's own queue, then hold one unit of capacity for one service time |
| `delay` | `in`, `out` | `time` (distribution) | Holds each item for the sampled time; no queue, no capacity limit |
| `branch` | `in`, one output per route | `routes` (array of identifiers, required; one `out` port per entry), `rule` (`probability` or `shortest_queue`), `weights` (object keyed by route, required for `probability`) | Sends each item down one route |
| `queue` | `in`, `out` | `capacity`, `discipline`, optional `on_full` (`block`, default, or `discard`: the item leaves and is counted in `<queue>.discarded`) | A standalone buffer, for use ahead of a batch or branch |
| `batch` | `in`, `out` | `size`, optional `timeout` | Collects `size` items and releases them as one |
| `unbatch` | `in`, `out` | none | Splits a batch back into its items |
| `store` | `in`, `out` | `initial`, `reorder_point`, `order_quantity`, `lead_time` | Each item arriving at `in` takes one unit of stock and leaves by `out` at once. If stock is zero the item waits, first in first out, until a delivery; each such item counts as a stock-out. When stock on hand plus on order falls to `reorder_point`, an order of `order_quantity` is placed and arrives after `lead_time` (a distribution) |
| `resource_pool` | none | `capacity` | Shared staff or tools; servers name it in their `pool` setting |
| `schedule` | none | `target`, `shifts`, optional `period` (time quantity, default 24 h) | Changes the capacity of a server or pool over time |
| `failure` | none | `target`, `time_to_failure`, `time_to_repair` | Takes a server out of service at random and returns it after repair |
| `sink` | `in` | none | Removes the item and records its statistics |

Item attributes, the `attribute` rule and priority disciplines are deferred to Phase 2 (see spec 1).

Rules that apply across blocks:

- **Server queue.** Unlimited and first in, first out unless `queue_capacity` or `discipline` says otherwise.
- **Discipline.** `discipline` values are `fifo` (default) or `lifo`.
- **Blocking.** If the next block cannot accept an item, the item stays where it is and keeps holding its capacity.
- **Branch rules.** `probability` draws from the branch's own stream and picks a route with probability weight/sum of weights. `shortest_queue` picks the route whose next block has the fewest waiting items (0 for a block without a queue); ties go to the earliest route in `routes`.
- **Simultaneous events.** Events at the same time run in the order they were scheduled.

Proposed defaults chosen by the review council, owner to confirm; M4 may correct them with a DECISIONS entry:

- **Source when blocked.** A source whose next block cannot accept the item discards it and counts it in `<source>.discarded`; arrivals are never delayed.
- **Failure.** `time_to_failure` is sampled from the failure block's stream and runs on calendar time while the unit is not failed, busy and idle alike. A failure takes one unit; an item in service on it is suspended and resumes with its remaining service time after repair (preempt-resume). `time_to_repair` runs from the moment of failure.
- **Schedule.** `shifts` is a list of `{start, end, capacity}` with `start` and `end` time quantities within `period`; the list repeats every `period`, and outside every listed shift the capacity is 0. A unit busy when scheduled capacity falls finishes its current item, then stops.
- **Batch timeout.** When `timeout` elapses after a batch's first item arrived, the partial batch is released; an `unbatch` splits whatever it receives. A batch's cycle time is its first item's.
- **Pool.** A server with `pool` seizes its own capacity first, then one pool unit; service, and therefore the end of the item's wait, begins only when both are held, and both are released after service; pool units are granted first come, first served across servers.
- **Targets.** A server may be the target of at most one `schedule` and one `failure` (E125).

The prototype exercised `source`, `server`, `delay`, `branch` with the `probability` rule, and `sink`. The other blocks are specified but untested.

### Statistic definitions

| Statistic | Definition |
| --- | --- |
| `<server>.wait.mean` | Mean time from arrival at the server to start of service, over items whose service starts after warm-up |
| `<server>.utilization` | Busy time in the observed period divided by the integral over the period of available capacity (scheduled capacity minus failed units); without schedule or failure this equals busy time over capacity times the period |
| `<sink>.throughput` | Items reaching the sink after warm-up, divided by the observed period |
| `<sink>.cycle_time.mean` | Mean time from creation to sink, over items reaching the sink after warm-up |
| `<server>.availability` | Time at least one unit is not failed, over the period; 1 without a failure (proposed; confirmed at M4) |
| `<server>.scheduled_fraction` | Integral of scheduled capacity over nominal capacity times the period; 1 without a schedule (proposed; confirmed at M4) |
| `<server\|queue>.queue_length.mean` | Time-weighted average number waiting, not in service |
| `<server\|queue>.queue_length.max` | Largest number waiting at any instant in the observed period |
| `<queue>.wait.mean` | Mean time an item spends in the queue, over items leaving it after warm-up (proposed; confirmed at M4) |
| `<batch>.wait.mean` | Arrival at the batch to its release (proposed; confirmed at M4) |
| `<pool>.utilization` | As a server, over the pool's units (proposed; confirmed at M4) |
| `<store>.stock.mean` | Time-weighted stock on hand (proposed; confirmed at M4) |
| `<store>.stockouts` | Items that found stock at zero, after warm-up (proposed; confirmed at M4) |
| `<store>.orders` | Orders placed after warm-up, divided by the period (proposed; confirmed at M4) |
| `<source>.created` | Items created after warm-up |
| `<sink>.count` | Items reaching the sink after warm-up |
| `<source>.discarded`, `<queue>.discarded` | Items discarded after warm-up, divided by the period: a rate, like throughput (proposed; confirmed at M4) |
| `model.wip.mean` | Time-weighted items created and not yet at a sink |

- The observed period runs from the end of warm-up to the end of the run.
- Items still in the system at the end are not counted in waits or cycle times.
- Across replications: the reported mean is the mean of replication means. The half-width is t(1 − (1 − confidence)/2, n − 1) times the sample standard deviation of the replication means (n − 1 denominator), divided by √n. The t quantile comes from `scipy.stats.t.ppf`; no table is hard-coded. Per-replication statistics are the adapter's; this across-replication line is computed by the experiment manager for every adapter.
- Between scenarios: for each metric and each pair of scenarios the difference is computed per replication (same replication number, same streams) and reported as a mean with a half-width from the paired differences; an interval excluding zero is reported as separated.
- Time series are recorded every `record_interval` for every time-persistent statistic, in the `timeseries` table of spec 1.
- Warm-up check (proposed; the spec 2 research note may replace it with MSER-5 or Welch and must say why): for each time-persistent statistic the means over the first and second halves of the observed period are compared across replications as a paired difference; if the 99% interval excludes zero and the difference exceeds 5% of the mean, `summary.json` carries W210. The 99% level is chosen because a 95% interval would flag about one correct steady-state run in twenty per statistic.

### Benchmark definitions

Each benchmark is a folder `benchmarks/<case>/` holding `model.json` (fixed `seed`) and `expected.json`: a list of `{metric, value, method, source, milestone}` where method is `three_se` (stochastic simulation), `exact` (deterministic, four significant figures) or `sig_figs_4` (optimization). `tests/benchmarks/test_benchmarks.py` is parametrized over these folders, carries marker `benchmark`, and runs in `bash scripts/check.sh`; cases whose milestone is later than the current one are skipped.

| Case | Settings | Known answer | Milestone |
| --- | --- | --- | --- |
| M/M/1 | Exponential arrivals, mean 2 min; one server, exponential service, mean 1.5 min | Mean wait 4.500 min; `queue_length.mean` 2.250; utilization 0.750; `cycle_time.mean` 6.000 min; throughput 30.0/h | M2 |
| M/M/2 | Exponential arrivals, mean 1 min; two servers, exponential service, mean 1.5 min | Mean wait 1.929 min; queue length 1.929; utilization 0.750; cycle time 3.429 min; throughput 60.0/h | M2 |
| Tandem | Arrivals mean 2 min; server A exponential mean 1.5 min; server B exponential mean 1 min; unlimited queues | A wait 4.500 min, B wait 1.000 min, utilizations 0.750 and 0.500, cycle time 8.000 min (Burke's theorem) | M2 |
| Delay | Arrivals mean 2 min → delay exponential mean 10 min → sink | `cycle_time.mean` 10.00 min; `model.wip.mean` 5.00 (Little) | M2 |
| Branch | Arrivals 30/h, weights a 0.3, b 0.7 | `sink_a` 9.00/h, `sink_b` 21.00/h | M2 |
| Batch and unbatch | Arrivals mean 1 min → batch size 5 → unbatch → sink | `batch.wait.mean` 2.000 min ((size − 1)/(2λ)); throughput 60/h | M4 |
| Resource pool | The M/M/1 model with server capacity 2 and `pool` naming a pool of capacity 1 | Wait 4.500 min; with pool capacity 2 and the M/M/2 arrivals, 1.929 min | M4 |
| Failure | The M/M/1 server with `time_to_failure` exponential mean 100 min, `time_to_repair` exponential mean 25 min | Availability 0.800 | M4 |
| Schedule, deterministic | Arrivals constant every 8 h, first at 1 h; service constant 1 h; shift capacity 1 from 0 h to 8 h each day, 0 otherwise; 2 replications of 204 h with 12 h warm-up, so that the observed period is exactly eight whole days | `wait.mean` 8.000 h exactly (steady-state waits 15, 8, 1 h); utilization 0.3750 (24 h busy over 64 h available); `scheduled_fraction` 0.3333 (64 h over 192 h) | M4 |
| Queue, loss | Arrivals 30/h → queue capacity 2 → server capacity 1, `queue_capacity` 0, exponential mean 1.5 min | Throughput 25.37/h (M/M/1/3 loss 0.1543); `source.discarded` 4.63/h | M4 |
| Store, deterministic | Arrivals constant every 6 min → store initial 100, `reorder_point` 30, `order_quantity` 100, `lead_time` constant 123 min (chosen so a delivery never coincides with a demand) → sink; 2 replications of 1,000 h, warm-up 100 h | `stock.mean` 60.0; orders 0.100/h; stockouts 0 | M4 |
| Product mix | Maximize 45 chairs + 80 tables; wood 5 and 20 per unit, 400 available; labour 10 and 15 per unit, 450 available | 24 chairs, 14 tables, profit 2,200 (unique: dual values 1 and 4 both positive) | M5 |
| Knapsack (binary) | Maximize 10a + 13b + 8c + 7d, 5a + 6b + 4c + 3d ≤ 10 | 21 with b = c = 1 | M5 |
| Assignment (binary) | 3×3 costs [[9, 2, 7], [6, 4, 3], [5, 8, 1]], each row and column once | 9 | M5 |
| Diet (continuous) | Minimize 0.6x + y; 2x + 4y ≥ 8; 5x + y ≥ 10; x, y ≥ 0 | 2.178 at x = 1.778, y = 1.111 | M5 |
| Transport | Defined with the indexed layout when the transport template is built |  | M10 |
| Machine count (simulation-based) | The coffee shop with parameter `tills` integer 1 to 5, objective minimize `till.wait.mean`, constraint `till.utilization >= 0.35` (feasibility judged on the mean), search budget 10, fixed seed | Best `tills` = 2 (theory: 1 till 4.500 min; 2 tills 0.245 min at utilization 0.375; 3 or more break the constraint); the test also enumerates all five and asserts the search's best equals the enumerated best. Because five candidates fit the budget this run takes the exhaustive path, so the same test repeats the search with budget 3 to exercise the Optuna path and asserts only that the reported best is feasible and that a second run with the same seed returns the same candidates and result | M5 |

Stochastic cases use 100 replications of 200 hours with 10 hours of warm-up unless stated.

Every number above was recomputed by the council on 2026-11-05 and re-derived independently by the council's skeptic (queueing formulas, enumeration, and event-by-event simulation of the two deterministic cases).

### Reference values from the prototype (script and two model files not retained)

A throwaway translator produced these. Only `coffee_shop.json` survives verbatim; the three-machine line and warehouse files and the script were not retained, so their rows are indicative and unverified. At M1 both models are written fresh with M2 blocks only, to these targets (proposed default, owner to confirm): three-machine line, weld utilization 0.85 to 0.92 and the other stations below 0.70; warehouse, throughput within 1% of 60 per hour and pack utilization 0.75 to 0.85. The exact parameters are the M1 session's choice; note that with exponential arrivals and service a station at utilization 0.90 has a mean wait of nine service times (ρ/(1 − ρ)), so the prototype's 17.3 minutes would need a weld service time near 2 minutes or a lower-variance service distribution; reproducing it is not required. M2 re-measures both and replaces the rows.

| Check | Result |
| --- | --- |
| M/M/1 mean wait | 4.555 min, plus or minus 0.217; theory 4.500 lies inside |
| M/M/2 mean wait | 1.946 min, plus or minus 0.087; theory 1.929 lies inside |
| Three-machine line | Weld station utilization 0.90, mean wait 17.3 min; the other two stations below 0.67 |
| Small warehouse | Throughput 59.9 per hour against 60 arriving; pack station utilization 0.83 |
| Repeat run with the same seed | Identical results |
| Run time | Under 14 seconds for everything above, on one core of a cloud machine |

The weld station's wait has a wide interval, 17.3 plus or minus 4.4 min. That is a real case for the "not enough runs" finding in spec 4.

### Mathematical optimization in the model file

A model with `"domain": "optimization"` uses `variables`, `objective` and `constraints` in place of components. This layout has not been run.

```json
{
  "format_version": "0.1",
  "meta": {"name": "Product mix"},
  "domain": "optimization",
  "variables": [
    {"id": "chairs", "type": "continuous", "lower": 0},
    {"id": "tables", "type": "continuous", "lower": 0}
  ],
  "objective": {"sense": "maximize", "linear": {"chairs": 45, "tables": 80}},
  "constraints": [
    {"id": "wood",   "linear": {"chairs": 5,  "tables": 20}, "op": "<=", "rhs": 400},
    {"id": "labour", "linear": {"chairs": 10, "tables": 15}, "op": "<=", "rhs": 450}
  ]
}
```

- Variable types: `continuous`, `integer`, `binary`.
- Phase 1 supports linear objectives and constraints only.
- Results report each variable's value, the objective value, and for each constraint whether it is tight.
- Indexed problems, such as a transport plan over many routes, need sets and tables. That extension is designed when the transport template is built.

`summary.json` for `optimization` is:

```json
{"model": "Product mix", "status": "optimal", "objective": 2200,
 "variables": {"chairs": 24, "tables": 14},
 "constraints": {"wood": {"tight": true, "slack": 0},
                 "labour": {"tight": true, "slack": 0}}}
```

`status` is `optimal`, `infeasible` or `unbounded`; `experiments` is absent and `run` still applies.

### Simulation-based optimization

- **Where.** An experiment with a `search` object (spec 1).
- **Variables** are the parameters it names.
- **Baseline.** The model's current values are always the first candidate.
- **Search.** If the number of distinct integer combinations is at most the budget, every combination is run; otherwise Optuna's TPE sampler proposes candidates, seeded from the spec 1 stream key `<seed>:0:optimizer` (`optimizer` is a reserved identifier), so a search repeats exactly.
- **Budget** is a number of candidates, default 50; each runs `search.replications` with the experiment seed (common random numbers).
- **Confirmation.** The baseline and the best three candidates by search-stage mean objective among those whose search-stage means satisfy the constraints are re-run with the experiment's full `replications`; constraints are re-judged on the confirmed means, and the reported best is the best confirmed feasible candidate. If none of the three is feasible on confirmation, the next three feasible-at-search candidates are confirmed, until one is feasible or none remain, in which case `status` is `infeasible` and the baseline's confirmed metrics are reported. The result states whether the best is separated from the confirmed runner-up (paired difference interval excluding zero).
- **Constraints** on simulated metrics are judged on the confirmed mean.
- **Result.** `summary.json` gains `search: {best: {set}, objective: {metric, before, after}, separated: bool, candidates: [{set, metrics, feasible, confirmed}]}`, where `before` is the baseline's confirmed objective.

Proposed; verified at M5.

### Fidelity for process models

Phase 1 accepts `standard` only; `summary.json` carries `fidelity_label`. A `sketch` preview level is an owner question.

## Research before building

Complete these and record the findings, with sources, in a short note in the repository before writing code. If a finding contradicts this spec, update the spec first.

- **M2 · Simulation library.** Compare SimPy, salabim and Ciw on features, speed, upkeep and licence.
- **M3 · Output analysis methods.** Published methods for choosing warm-up length and number of replications.
- **M5 · Simulation-based optimization.** Ranking-and-selection and Bayesian methods from the simulation literature. Record which ranking-and-selection procedure, if any, replaces the fixed top-three confirmation.
- **M5 · Solver layer.** Current versions and licences of HiGHS, Pyomo, OR-Tools and Optuna.
- **M2 and M5 · Benchmark sources.** Textbook problems with published answers that may be reused freely.
- **M4 · Prior art.** Papers on generating process simulation models from text, for the block design.

## Acceptance tests

| Test | Milestone | Checked by | Evidence |
| --- | --- | --- | --- |
| Every block has a unit test and appears in a benchmark | M2 for the five prototype blocks, M4 for the rest | agent |  |
| All benchmarks tagged at or before the current milestone pass on every build | M2 onward | agent | `tests/benchmarks` |
| The three example models run end to end | M2 | agent |  |
| A 30-replication run of the three-machine line finishes in under one minute (proposed target; measured per the Build guide protocol, confirmed by the owner) | M3 measured, owner confirms | agent + owner | `docs/research/perf-M3.md` |
| Mathematical optimization benchmarks pass | M5 | agent |  |
| The machine-count test finds `tills` = 2 and equals the enumerated best | M5 | agent | `tests/runs/test_search.py` |

## Changes in this version

2026-11-05, version 0.3, spec review council:

- C11 (ARCH-19, SIM-8, SIM-13, ARCH-16, TEST-5, SIM-5, SIM-2): summary aligned with binding text; benchmark milestones; 3 × standard error pass rule with fixed seeds and 100 replications.
- C12 (SIM-13, SIM-14, SIM-4, TEST-6, ARCH-10): `routes`, `on_full`, `period`, `lifo`, store behaviour; branch rules; proposed block behaviour defaults.
- C13 (SIM-10, SIM-11, ARCH-11, SIM-16, SIM-8, SIM-17, ARCH-3, TEST-6): time-weighted statistics, availability, scheduled fraction, discard rates, `model.wip.mean`; t quantile from scipy; paired scenario differences; time series; warm-up check.
- C14 (SIM-3, SIM-4, SIM-5, TEST-5, TEST-6, TEST-7, SIM-2): benchmark folders and `expected.json`; one known-answer case per block and four optimization cases; machine-count case.
- C15 (SIM-19, ARCH-15, TEST-2, PRD-1): prototype rows marked reference only; targets for the two example files written at M1.
- C16 (ARCH-1, ARCH-2, SIM-7, TEST-7, ARCH-18, PRD-8): optimization `summary.json`; search procedure with baseline, exhaustive path, confirmation stage and result layout; fidelity for process models.
- C17 (TEST-1, TEST-8, TEST-12, TEST-6): version line, research items tagged, acceptance table.
- 2026-11-06, sync to Claude Docs: the `<server|queue>` rows of "Statistic definitions" escape the pipe (`\|`) so the table keeps two columns.
