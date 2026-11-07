# Spec 2: Core Engine for Process Simulation and Optimization

> Version 0.6 · working copy in the repository (source of truth, owner to confirm) · changes are listed under "Changes in this version".

Two engine adapters, both in Python: discrete-event simulation on SimPy, and optimization on HiGHS; Optuna is a search driver inside the experiment manager, not an adapter. Together with an experiment manager they make Phase 1 a complete product.

> **Warning: partly tested.** Five block types ran in a prototype and, from M2, in the SimPy adapter and its benchmarks; from M4, `queue`, `batch` and `unbatch` run there too, with their benchmarks. The other four, the optimization layout in the model file, and simulation-based optimization have never run. Performance targets are proposals. Verify each at its milestone and update this spec. See "Known gaps" in the Build guide.

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
| `source` | `out` | `interarrival` (distribution), optional `first_arrival` (time quantity), `max_items` (integer) | Creates one item, waits one interarrival time, repeats. The first item is created at `first_arrival`, 0 s when absent; after `max_items` items the source stops (proposed default, owner to confirm) |
| `server` | `in`, `out` | `capacity` (integer), `service` (distribution), optional `queue_capacity` (integer), `discipline`, `pool` | Items wait in the server's own queue, then hold one unit of capacity for one service time |
| `delay` | `in`, `out` | `time` (distribution) | Holds each item for the sampled time; no queue, no capacity limit |
| `branch` | `in`, one output per route | `routes` (array of identifiers, required; one output port per entry, named by the entry), `rule` (`probability` or `shortest_queue`), `weights` (object keyed by route, required for `probability`) | Sends each item down one route |
| `queue` | `in`, `out` | `capacity` (integer), optional `discipline`, optional `on_full` (`block`, default, or `discard`: the item leaves and is counted in `<queue>.discarded`) | A standalone buffer, for use ahead of a batch or branch |
| `batch` | `in`, `out` | `size` (integer), optional `timeout` (time quantity) | Collects `size` items and releases them as one |
| `unbatch` | `in`, `out` | none | Splits a batch back into its items |
| `store` | `in`, `out` | `initial`, `reorder_point`, `order_quantity` (integers), `lead_time` (distribution) | Each item arriving at `in` takes one unit of stock and leaves by `out` at once. If stock is zero the item waits, first in first out, until a delivery; each such item counts as a stock-out. When stock on hand plus on order falls to `reorder_point`, an order of `order_quantity` is placed and arrives after `lead_time` (a distribution) |
| `resource_pool` | none | `capacity` (integer) | Shared staff or tools; servers name it in their `pool` setting |
| `schedule` | none | `target`, `shifts`, optional `period` (time quantity, default 24 h) | Changes the capacity of a server or pool over time |
| `failure` | none | `target`, `time_to_failure`, `time_to_repair` | Takes a server out of service at random and returns it after repair |
| `sink` | `in` | none | Removes the item and records its statistics |

Item attributes, the `attribute` rule and priority disciplines are deferred to Phase 2 (see spec 1).

Rules that apply across blocks:

- **Server queue.** Unlimited and first in, first out unless `queue_capacity` or `discipline` says otherwise.
- **Discipline.** `discipline` values are `fifo` (default) or `lifo`.
- **Blocking.** If the next block cannot accept an item, the item stays where it is and keeps holding its capacity. In M2 only a server with `queue_capacity` can refuse: it accepts an item while a unit is free or fewer than `queue_capacity` items wait (so `queue_capacity` 0 accepts only into a free unit). A server whose finished item is refused keeps it on its unit, which stays busy (and counts as busy in `utilization`) until the item moves; a delay always accepts and holds a refused item past its sampled time; a branch always accepts and keeps a refused item itself, so the unit upstream of a branch is freed. A blocked item moves as soon as space frees at the block that refused it, at that same instant and before any other event due then, blocked items going in the order they were refused (first in, first out). A source never blocks (see "Source when blocked"); since a branch always accepts, a source feeding a branch never discards. Proposed default (AKS-99), owner to confirm. From M4 (AKS-105, owner to confirm) a full `queue` with `on_full` `block` also refuses, so a server feeding it stays blocked and a source feeding it discards; a `queue` with `discard`, a `batch` and an `unbatch` always accept, so a source feeding one of them never discards.
- **Branch rules.** `probability` draws from the branch's own stream and picks a route with probability weight/sum of weights. `shortest_queue` picks the route whose next block has the fewest waiting items (0 for a block without a queue); ties go to the earliest route in `routes`. The route is chosen when the item reaches the branch. `probability` draws one number per item, even when only one weight is above 0: a uniform u in [0, 1), and the first route whose running sum of weights, in `routes` order, exceeds u × sum of weights; a route of weight 0 is never chosen. `shortest_queue` draws nothing and ignores `weights`. A server's waiting items are its queue, not the items on its units; a delay, a branch and a sink count 0. Proposed default (AKS-99), owner to confirm. A `queue`'s waiting items are every item it holds; a `batch` and an `unbatch` count 0, having no queue (AKS-105, owner to confirm).
- **Simultaneous events.** Events at the same time run in the order they were scheduled, with SimPy's one exception: the first step of a process started at that instant, and an interrupt, run before the other events due then (SimPy orders events by time, then urgent before normal priority, then scheduling order). An event due exactly at the end of the run does not run.
- **Queue.** A `queue` passes an item to `out` as soon as the next block accepts it, so an item that passes straight through waits 0 s and is never counted as waiting, even for no time; the others wait, and `discipline` picks the one that moves when space frees at the next block (`lifo`: the latest to arrive at that moment). An item held by the queue counts against `capacity` until it moves. Items arriving together (the items of one batch from an `unbatch`) can find the queue full only because its offer of an earlier item to the next block is still due at that instant. A blocking queue then refuses them, and they move in at that same instant as the offer frees space, in the order they were refused ("Blocking"). A discarding queue holds them until that offer has been tried: each then enters while there is room, and is discarded only if the queue is still full with its offer refused. So items arriving together are neither discarded nor delayed while they can move on. With `on_full` `discard`, an item arriving at a full queue whose offer has been refused leaves the model at once: it is counted in `<queue>.discarded` and leaves work in progress, and it has no wait. Proposed default (AKS-105), owner to confirm.
- **Batch and unbatch.** A batch is one unit holding the units it collected, in arrival order; it moves through blocks as one unit (one place in a `capacity`, one service). Its creation time is the creation time of the first unit to arrive at the batch. The `timeout` of "Batch timeout" is started per batch when its first unit arrives, and a batch filled before its timeout is not released again by it. When the next block refuses a formed batch, the batch waits at the `batch` block for space there, while the next batch collects; a `batch` holds any number of formed batches and always accepts. An `unbatch` sends on, at once and in order, the units of what it receives, one level of batching (a batch of batches gives batches), and passes a single item on unchanged; units the next block refuses wait at the unbatch, in order. A sink that receives a batch counts it once in `count` and `throughput`, with one cycle time from the batch's creation time; items passed on by an unbatch keep their own creation times. Work in progress counts items: a batch reaching a sink, or discarded by a `queue`, removes every item it holds. Proposed default (AKS-105), owner to confirm.
- **Ranges.** A server's, queue's or pool's `capacity`, a batch's `size`, a store's `order_quantity` and a source's `max_items` are at least 1, since a smaller value never passes an item; a `queue_capacity`, a store's `initial` and `reorder_point`, and a shift's `capacity` are at least 0; each weight is at least 0 and at least one is above 0; `first_arrival` and a shift's `start` are at least 0 s; `timeout` and `period` are above 0 s; a branch has at least one route; a shift's `end` is after its `start` and no later than `period`. A value outside these is E123 (spec 1). Proposed defaults (AKS-90), owner to confirm.

Proposed defaults chosen by the review council, owner to confirm; M4 may correct them with a DECISIONS entry:

- **Source when blocked.** A source whose next block cannot accept the item discards it and counts it in `<source>.discarded`; arrivals are never delayed.
- **Failure.** `time_to_failure` is sampled from the failure block's stream and runs on calendar time while the unit is not failed, busy and idle alike. A failure takes one unit; an item in service on it is suspended and resumes with its remaining service time after repair (preempt-resume). `time_to_repair` runs from the moment of failure.
- **Schedule.** `shifts` is a list of `{start, end, capacity}` with `start` and `end` time quantities within `period` and `capacity` an integer; the list repeats every `period`, and outside every listed shift the capacity is 0. A unit busy when scheduled capacity falls finishes its current item, then stops.
- **Batch timeout.** When `timeout` elapses after a batch's first item arrived, the partial batch is released; an `unbatch` splits whatever it receives. A batch's cycle time is its first item's. Built at M4 as "Batch and unbatch" above says (AKS-105).
- **Pool.** A server with `pool` seizes its own capacity first, then one pool unit; service, and therefore the end of the item's wait, begins only when both are held, and both are released after service; pool units are granted first come, first served across servers.
- **Targets.** A server may be the target of at most one `schedule` and one `failure` (E125).

The prototype exercised `source`, `server`, `delay`, `branch` with the `probability` rule, and `sink`. M2 built these five, with `shortest_queue` and `queue_capacity` (AKS-98, AKS-99), and runs them in the M2 benchmarks. M4 built `queue`, `batch` and `unbatch` (AKS-105), which run in the queue, loss and batch and unbatch benchmarks. The other blocks are specified but untested.

### Statistic definitions

| Statistic | Definition |
| --- | --- |
| `<server>.wait.mean` | Mean time from arrival at the server to start of service, over items whose service starts after warm-up |
| `<server>.utilization` | Busy time in the observed period divided by the integral over the period of available capacity (scheduled capacity minus failed units); without schedule or failure this equals busy time over capacity times the period. Busy time counts at each instant at most the available capacity: a unit finishing its item after scheduled capacity falls (see "Schedule") adds nothing, so utilization never exceeds 1. A unit holding an item its next block refused is busy (see "Blocking"; AKS-99, owner to confirm) |
| `<sink>.throughput` | Items reaching the sink after warm-up, divided by the observed period |
| `<sink>.cycle_time.mean` | Mean time from creation to sink, over items reaching the sink after warm-up |
| `<server>.availability` | Time at least one unit is not failed, over the period; 1 without a failure (proposed; confirmed at M4) |
| `<server>.scheduled_fraction` | Integral of scheduled capacity over nominal capacity times the period; 1 without a schedule (proposed; confirmed at M4) |
| `<server\|queue>.queue_length.mean` | Time-weighted average number waiting, not in service; for a queue, the items it holds, an item passing straight through not counted (see "Queue"; AKS-105, owner to confirm) |
| `<server\|queue>.queue_length.max` | Largest number waiting at any instant in the observed period |
| `<queue>.wait.mean` | Mean time an item spends in the queue, from its arrival to the moment it moves to the next block, over items moving on after warm-up; an item passing straight through counts 0 s, and a discarded item is not counted (confirmed at M4, AKS-105; owner to confirm) |
| `<batch>.wait.mean` | Mean time from an item's arrival at the batch to its release, the moment its batch moves on to the next block (later than forming when that block refuses it), over the items of batches moving on after warm-up, whenever each item arrived; a unit counts once, a batch of batches as its batches (confirmed at M4, AKS-105; owner to confirm) |
| `<pool>.utilization` | As a server, over the pool's units (proposed; confirmed at M4) |
| `<store>.stock.mean` | Time-weighted stock on hand (proposed; confirmed at M4) |
| `<store>.stockouts` | Items that found stock at zero, after warm-up (proposed; confirmed at M4) |
| `<store>.orders` | Orders placed after warm-up, divided by the period (proposed; confirmed at M4) |
| `<source>.created` | Items created after warm-up |
| `<sink>.count` | Items reaching the sink after warm-up |
| `<source>.discarded`, `<queue>.discarded` | Items discarded after warm-up, divided by the period: a rate, like throughput. A source discards an item its next block refuses; a `queue` with `on_full` `discard` an item arriving when it is full; a batch discarded counts once (confirmed at M4, AKS-105; owner to confirm) |
| `model.wip.mean` | Time-weighted number of items in the system: created and not yet at a sink or discarded |

- The observed period runs from the end of warm-up to the end of the run.
- An event at exactly the end of warm-up belongs to the observed period: counts and observations take events at or after warm-up (an item reaching a sink at that instant counts, and so does a wait whose service starts then). Time-weighted statistics integrate only over the period, so an item in service across the end of warm-up adds only the part of its service after it. `queue_length.max` is the largest of the value held at the end of warm-up and every value taken during the period, including one held for no time. Proposed default (AKS-98), owner to confirm.
- A mean over no items (`wait.mean` or `cycle_time.mean` in a replication where no item qualifies) is undefined, and the replication's value is NaN (spec 1 "Tables for the `process` domain"). Proposed default (AKS-98), owner to confirm.
- Items still in the system at the end are not counted in waits or cycle times.
- Across replications: the reported mean is the mean of replication means. The half-width is t(1 − (1 − confidence)/2, n − 1) times the sample standard deviation of the replication means (n − 1 denominator), divided by √n. The t quantile comes from `scipy.stats.t.ppf`; no table is hard-coded. Per-replication statistics are the adapter's; this across-replication line is computed by the experiment manager for every adapter.
- A replication value that is NaN (a mean over no items, above) is left out: the mean and half-width are over the n values that remain, with t at n − 1 degrees of freedom, and `summary.json` reports n with each metric (spec 1 "Run folder and results"). With n = 1 the half-width is undefined, and with n = 0 the mean too; an undefined value is written `null`. Proposed default (AKS-102), owner to confirm.
- Between scenarios: for each metric and each pair of scenarios the difference is computed per replication (same replication number, same streams) and reported as a mean with a half-width from the paired differences; an interval excluding zero is reported as separated. Precisely (AKS-102, proposed default, owner to confirm): each pair is taken in the experiment's scenario order and the difference is the later scenario's value minus the earlier's; a replication is paired only when both values are not NaN, and n is the number of pairs; the mean and half-width follow the across-replication rule at the experiment's `confidence`; separated means n ≥ 2 and |mean| > half-width (strict, so a difference of exactly 0 with no spread is not separated).
- Time series are recorded every `record_interval` for every time-persistent statistic, in the `timeseries` table of spec 1. In M2 these are, per server, `<server>.queue_length` (items waiting) and `<server>.utilization` (busy units, blocked ones included, over `capacity`), and `model.wip` (items in the system); each is its summary metric without `.mean`, so its time average is that metric. From M4 each `queue` adds `<queue>.queue_length`, for its `queue_length.mean`; a `batch` and an `unbatch` add none, since `<batch>.wait.mean` is not time-persistent (AKS-105, owner to confirm). Samples are taken at k × `record_interval` for k = 0, 1, 2, … while the time is before the end of the run, from the run start and through warm-up, so there is a sample at 0 s and none at the end. A time short of the end by less than a billionth of `record_interval` counts as the end, so the rounding of `length` / 200 (for example 200 × (29 s / 200) is just below 29 s) never adds a 201st sample. A sample is the value after every event due at that instant. Sampling adds no event and draws no random number, so it changes no other result. Proposed default (AKS-99), owner to confirm.
- Warm-up check (kept over MSER-5 and Welch's method by the M3 research note `docs/research/spec-2-output-analysis.md`; the 99% level and the 5% threshold are proposed defaults, owner to confirm): for each time-persistent statistic the means over the first and second halves of the observed period are compared across replications as a paired difference; if the 99% interval excludes zero and the difference exceeds 5% of the mean, `summary.json` carries W210. The 99% level is chosen because a 95% interval would flag about one correct steady-state run in twenty per statistic. Precisely (AKS-129):
  - **Input.** Every metric of the run's `timeseries` table (in M2 `<server>.queue_length`, `<server>.utilization` and `model.wip`), for each scenario of the experiment. A replication's observed samples are its samples with `time_s` at or after `warmup` (the same boundary as every other statistic), in time order; J is their number, the same in every replication. The check uses the samples as they are, not a time-weighted integral.
  - **Halves.** With h = ⌊J/2⌋, the first half is the first h observed samples and the second half the last h; when J is odd the middle sample is in neither. A metric with J < 2 is not checked.
  - **Statistic.** For replication r of n: d_r = (mean of the second half) − (mean of the first half), and m_r = the mean of all J observed samples. d̄ and m̄ are the means of the d_r and the m_r over the n replications; s is the sample standard deviation of the d_r (n − 1 denominator), and the half-width is t(0.995, n − 1) × s / √n, with t from `scipy.stats.t.ppf`. The level is 99% whatever the experiment's `confidence`. n is at least 2 (E170), so the quantile is always defined; when s is 0 the half-width is 0.
  - **Changed.** A metric has changed in a scenario when |d̄| > half-width and |d̄| > 0.05 × |m̄| (both strict). A constant series has d̄ = 0 and never changes. A metric with m̄ = 0 is not reported as changed, since a change as a percentage of its mean is undefined; every Phase 1 series is at least 0, so its m̄ is 0 only when every sample is (AKS-102, owner to confirm).
  - **Warning.** When at least one metric has changed in at least one scenario, `summary.json` `warnings` carries exactly one W210 issue for the run, not one per metric: `component` null; `path` `/experiments/<index>/warmup`, the experiment's position in the model file's `experiments` array (where the key belongs when `warmup` is absent); `message` "Results were still changing after warm-up: " followed by, for each changed metric in scenario order and then `timeseries` row order, "<metric> in scenario <scenario> changed by <p>% of its mean between the first and second halves of the observed period", joined by "; " and ending with a full stop, where p is 100 × |d̄| / |m̄| rounded to the nearest whole number (a half rounds up; AKS-102); `hint` "Lengthen 'warmup' and run again.". The W210 issue follows the adapter's warnings in `warnings` (spec 1 "Run folder and results"). The check computes nothing else and changes no other result.
  - **Scope.** A plain experiment. Whether and how a search (spec 2 "Simulation-based optimization") checks its candidates is decided at M5.
  - Simplest readings of the proposal (AKS-129), owner to confirm: the samples rather than a time-weighted integral, the halves by sample count, one warning per run, its path, message and hint, and the scope.

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

How the M2 benchmark files read the table above (AKS-100, proposed default, owner to confirm):

- **Distributions.** Every arrival and service time in the M2 cases is exponential, and so is the delay's time; "Arrivals 30/h" is an exponential interarrival time of mean 2 min. Burke's theorem needs Poisson arrivals and exponential service at A for the tandem answers; the delay (Little) and branch (split) answers hold for any distribution but use the same arrivals.
- **Branch case.** One source feeds a branch with `rule` `probability`, routes `a` and `b` and weights 0.3 and 0.7; route `a` goes to sink `sink_a` and `b` to `sink_b`.
- **Metric names.** Each known answer is one metric the process adapter reports for one replication (spec 1 "Metric names"): a server's `wait.mean`, `queue_length.mean` and `utilization`, a sink's `cycle_time.mean` and `throughput`, and `model.wip.mean`. "Throughput" is the sink's; "cycle time" is the sink's, from creation, so the tandem's 8.000 min covers both stations.
- **Values.** `value` in `expected.json` is in the units the adapter reports: seconds for times, items per second for rates, and plain numbers otherwise (4.500 min is 270 s; 30.0/h is 1/120 per second). It is the exact closed-form value, not the rounding shown above (1.929 min is 810/7 s).
- **Estimate and standard error.** The estimate is the mean of the 100 replication values of the metric; the standard error is their sample standard deviation (n − 1 denominator) divided by √n. A missing metric or a NaN replication value fails the check.
- **Exact.** An `exact` check passes when the estimate and the known answer, each rounded to four significant figures, are equal.
- **Coverage run.** For each case, `pytest -m benchmark_coverage` runs the model with 20 consecutive seeds, starting at the seed in `model.json`; a seed passes when every check of the case passes, and the case passes the coverage run at 19 of 20 or better.

How the M4 benchmark files read the table (AKS-105, proposed default, owner to confirm), with the M2 rules above otherwise:

- **Queue, loss.** `benchmarks/queue_loss` (seed 1006): source `arrivals` with exponential interarrival times of mean 2 min ("Arrivals 30/h"), a `queue` `line` of `capacity` 2 with the default `on_full` `block`, a server `server` of capacity 1 with `queue_capacity` 0 and exponential service of mean 1.5 min, and sink `exit`. The line holds at most 3 items, so it is M/M/1/3: throughput is `exit.throughput`, λ(1 − P₃) = 37/5250 per second, and `source.discarded` is `arrivals.discarded`, λP₃ = 9/7000 per second, with P₃ = 27/175.
- **Batch and unbatch.** `benchmarks/batch_unbatch` (seed 1007): source `arrivals` with exponential interarrival times of mean 1 min, a `batch` `batch` of `size` 5 with no `timeout`, an `unbatch` `unbatch` and sink `exit`. `batch.wait.mean` is 120 s and throughput is `exit.throughput`, 1/60 per second: items, not batches, reach the sink.

Every number above was recomputed by the council on 2026-11-05 and re-derived independently by the council's skeptic (queueing formulas, enumeration, and event-by-event simulation of the two deterministic cases).

### Reference values from the prototype (script and two model files not retained)

A throwaway translator produced these. Only `coffee_shop.json` survives verbatim; the three-machine line and warehouse files and the script were not retained, so their rows are indicative and unverified. At M1 both models are written fresh with M2 blocks only, to these targets (proposed default, owner to confirm): three-machine line, weld utilization 0.85 to 0.92 and the other stations below 0.70; warehouse, throughput within 1% of 60 per hour and pack utilization 0.75 to 0.85. The exact parameters are the M1 session's choice; note that with exponential arrivals and service a station at utilization 0.90 has a mean wait of nine service times (ρ/(1 − ρ)), so the prototype's 17.3 minutes would need a weld service time near 2 minutes or a lower-variance service distribution; reproducing it is not required. M2 re-measures both and replaces the rows. Written at M1 (AKS-93, proposed default, owner to confirm): `examples/three_machine_line.json` has arrivals 30 per hour into cut, weld and paint, single exponential servers with means 1.2, 1.8 and 1 min (utilizations 0.60, 0.90 and 0.50), and a constant 2 min transfer before paint; `examples/warehouse.json` has arrivals 60 per hour into pick (three exponential servers, mean 2 min, utilization 0.667), a probability branch sending one order in five through a constant 5 min inspection, and pack (one exponential server, mean 0.8 min, utilization 0.80). No block in either loses items, so each throughput equals its arrival rate; "within 1% of 60 per hour" is the tolerance for the estimate M2 measures. Each file's `meta.description` gives the queueing arithmetic.

M2 re-measured both (AKS-101): the three-machine line and warehouse rows below are the process adapter's, not the prototype's. Each is the mean of the 30 replication means at the file's own experiment (seed 12345, 30 replications; the line 100 h with 20 h of warm-up, the warehouse 200 h with 10 h), plus or minus the 95% half-width t(0.975, 29) × sd / √30 of "Statistic definitions" (t from `scipy.stats.t.ppf`, 2.0452). `tests/engines/process/test_example_models.py` reproduces every value. The M/M/1 and M/M/2 rows keep the prototype's numbers, with the M2 benchmark's result beside them (100 replications at the benchmark seed; the deviation is in standard errors, as in "Benchmarks").

| Check | Result |
| --- | --- |
| M/M/1 mean wait | Prototype: 4.555 min, plus or minus 0.217; theory 4.500 lies inside. M2 benchmark `mm1` (seed 1001): 4.449 min, plus or minus 0.112, −0.90 standard errors from 4.500 |
| M/M/2 mean wait | Prototype: 1.946 min, plus or minus 0.087; theory 1.929 lies inside. M2 benchmark `mm2` (seed 1002): 1.937 min, plus or minus 0.039, +0.42 standard errors from 1.929 |
| Three-machine line | Measured at M2: weld utilization 0.901 plus or minus 0.011 (target 0.85 to 0.92); cut 0.600 plus or minus 0.007 and paint 0.495 plus or minus 0.006 (target below 0.70); weld mean wait 15.69 min plus or minus 2.09 (13.3% of the mean; theory 16.2); paint mean wait 0.951 min plus or minus 0.030 (theory 1.0, 3.3 standard errors below; seeds 1, 2 and 7 give +0.9, −0.4 and +0.7, so a reroll, not a bias); cycle time 24.48 min plus or minus 2.11 (theory 25.0); throughput 30.01 per hour plus or minus 0.25 (theory 30). The prototype's row was weld 0.90, wait 17.3 min, the other two stations below 0.67 |
| Small warehouse | Measured at M2: throughput 59.99 per hour plus or minus 0.20, 0.02% below 60 (target within 1%); pack utilization 0.799 plus or minus 0.004 (target 0.75 to 0.85); pick utilization 0.666 plus or minus 0.003 (theory 2/3); pack mean wait 3.17 min plus or minus 0.15 (theory 3.2); pick mean wait 0.875 min plus or minus 0.026 (theory 0.889); cycle time 7.84 min plus or minus 0.16 (theory 7.889). The prototype's row was throughput 59.9 per hour, pack 0.83 |
| Repeat run with the same seed | Identical results |
| Run time | Under 14 seconds for everything above, on one core of a cloud machine |

The weld station's wait has a wide interval: 15.69 plus or minus 2.09 min at M2, a half-width of 13.3% of the mean (the prototype's was 17.3 plus or minus 4.4 min). That is above spec 4's 10%, so it is still a real case for the "not enough runs" finding; M8 checks the finding on this file.

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

- Variable types: `continuous`, `integer`, `binary`. `lower` and `upper` are plain numbers; a bound left out means no bound on that side (write `"lower": 0` for a non-negative variable).
- `objective.sense` is `minimize` or `maximize`; a constraint's `op` is `<=`, `>=` or `==`; coefficients and `rhs` are plain numbers.
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
- **Confirmation.** The baseline and the best three candidates by search-stage mean objective among those whose search-stage means satisfy the constraints are re-run with the experiment's full `replications`; constraints are re-judged on the confirmed means, and the reported best is the best confirmed feasible candidate, the baseline included (it is always confirmed, whatever its search-stage result). If none of the three is feasible on confirmation, the next three feasible-at-search candidates are confirmed, until one is feasible or none remain. If no other candidate is confirmed feasible and the baseline is, the baseline is the best and `after` equals `before`. Only when no confirmed candidate, baseline included, is feasible is `status` `infeasible`, with the baseline's confirmed metrics reported. The result states whether the best is separated from the confirmed runner-up (paired difference interval excluding zero).
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
| Every block has a unit test and appears in a benchmark | M2 for the five prototype blocks, M4 for the rest | agent | M2: `tests/engines/process/test_source.py`, `test_server.py`, `test_delay.py`, `test_branch.py`, `test_sink.py`; `benchmarks/mm1` (source, server, sink), `delay`, `branch`; `test_every_m2_block_appears_in_an_m2_benchmark` in `tests/benchmarks/test_benchmarks.py`. M4 so far: `test_queue.py`, `test_batch.py`, `test_unbatch.py`; `benchmarks/queue_loss` (queue), `batch_unbatch` (batch, unbatch) |
| All benchmarks tagged at or before the current milestone pass on every build | M2 onward | agent | `tests/benchmarks` |
| The three example models run end to end | M2 | agent | `tests/engines/process/test_example_models.py` |
| A 30-replication run of the three-machine line finishes in under one minute (proposed target; measured per the Build guide protocol, confirmed by the owner) | M3 measured, owner confirms | agent + owner | M3 measured: `tests/perf/test_three_machine_line.py` and `docs/research/perf-M3.md` (1.5 to 1.8 s with 4 workers, not on the low tier); owner confirmation pending (AKS-82) |
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

2026-11-06, version 0.4, M1 closed (AKS-94); the lines below were added after version 0.3, during the review of PR #1 and the M1 build:

- 2026-11-06, sync to Claude Docs: the `<server|queue>` rows of "Statistic definitions" escape the pipe (`\|`) so the table keeps two columns.
- 2026-11-06, review of PR #1: `model.wip.mean` stops counting an item when it is discarded (by a source or a `queue` with `on_full: discard`) as well as when it reaches a sink, so WIP stays bounded in a stable loss system.
- 2026-11-06, review of PR #1: `<server>.utilization` caps busy time at available capacity at each instant, so off-shift completion of an item cannot push utilization above 1. M4 adds a schedule test with a service that crosses a shift end.
- 2026-11-06, review of PR #1: the search's confirmation stage counts the always-confirmed baseline as a feasible candidate, so a search is `infeasible` only when no confirmed candidate, baseline included, meets the constraints.
- 2026-11-06, model loading (AKS-88), found while building the `process` type catalogue (`src/lcsim/model/catalogue.py`): "Block reference" states the kind of the settings it left open (`first_arrival` and `timeout` are time quantities; `max_items`, `queue_capacity`, queue `capacity`, `size`, the store's stock levels, the pool's `capacity` and a shift's `capacity` are integers), makes a queue's `discipline` optional to match its stated default (`fifo`), and names a branch's output ports by their routes. "Mathematical optimization in the model file" lists `sense` and `op` words (`==` for equality, which the assignment benchmark needs), says bounds are plain numbers and that a missing bound means none.
- 2026-11-06, meaning pass B (AKS-90): "Rules that apply across blocks" gains "Ranges", the smallest value of each number and time setting and the order of a shift's `start`, `end` and `period`, which the meaning pass checks with E123. These were left open by the block table.
- 2026-11-06, example models (AKS-93): "Reference values from the prototype" records the parameters of the two example files written fresh at M1 and reads the warehouse throughput target as the tolerance for the M2 estimate, since a stable model with no loss has a long-run throughput equal to its arrival rate.

2026-11-06, version 0.5, M2 closed (AKS-101); the lines below were added after version 0.4, during the M2 research notes and the M2 build:

- 2026-11-06, M2 research note `docs/research/spec-2-simulation-library.md`: SimPy confirmed as the process engine over salabim and Ciw; "Simultaneous events" now states SimPy's tested ordering (a process start or an interrupt runs first at its instant; nothing runs at the end time). The M2 benchmark answers were recomputed from closed-form formulas in `docs/research/spec-2-benchmark-sources.md` and all match.
- 2026-11-06, SimPy adapter core (AKS-98), found while building `src/lcsim/engines/process/`: "Block reference" says a source's first item is created at `first_arrival`, 0 s when absent, and that it stops after `max_items` items (owner to confirm); "Statistic definitions" says an event at exactly the end of warm-up belongs to the observed period, that time-weighted statistics count only the part of the period after warm-up, what `queue_length.max` takes, and that a mean over no items is NaN (owner to confirm).
- 2026-11-06, SimPy adapter delay, branch, blocking and time series (AKS-99), found while building `src/lcsim/engines/process/`: "Rules that apply across blocks" says which M2 block can refuse an item (a server with `queue_capacity`, when no unit is free and `queue_capacity` items wait), that a blocked server unit stays busy and counts in `utilization`, that a delay holds and a branch keeps a refused item, that blocked items move as soon as space frees in the order they were refused, and that a source feeding a branch never discards; "Branch rules" says when the route is chosen, how `probability` maps its one draw per item to a route, and that `shortest_queue` draws nothing and ignores `weights`; "Statistic definitions" names the time-series metrics (`<server>.queue_length`, `<server>.utilization`, `model.wip`), when samples are taken (from 0 s, through warm-up, none at the end) and that a sample is the value after the events of its instant (owner to confirm).
- 2026-11-06, benchmark harness (AKS-100), found while writing `benchmarks/` and `tests/benchmarks/test_benchmarks.py`: "Benchmark definitions" says how the M2 benchmark files read the table: every M2 arrival, service and delay time is exponential (the tandem, delay and branch rows gave only means or a rate), the branch case's routes and sinks, the metric each known answer names, that `value` is the exact closed form in the adapter's SI units, how the estimate and its standard error come from the replication values (a missing metric or NaN fails), when an `exact` check passes, and what the coverage run counts as a pass (owner to confirm).
- 2026-11-06, M2 close (AKS-101), measured with `tests/engines/process/test_example_models.py`: "Reference values from the prototype" replaces the three-machine line and warehouse rows with the adapter's values at each file's own seed and replication count (mean plus or minus the 95% t half-width); both files meet their targets, so no parameter changed. The weld wait half-width is 13.3% of its mean (the prototype's 17.3 plus or minus 4.4 min is superseded). The M/M/1 and M/M/2 rows keep the prototype's numbers with the M2 benchmark results beside them. The acceptance table names its M2 evidence, and the warning line and "Block reference" say that the five prototype blocks now run in the adapter.

2026-11-06, version 0.6, M3 closed (AKS-104); the lines below were added after version 0.5, during the M3 research note and the M3 build:

- 2026-11-06, M3 research note `docs/research/spec-2-output-analysis.md` (AKS-129): the paired-halves warm-up check is kept over MSER-5 and Welch's method, with its 99% level and 5% threshold; "Statistic definitions" now states it precisely: which series and samples it reads, the halves, the statistic and its t quantile, when a metric has changed, one W210 per run with its `path`, `message` and `hint`, and that a search's candidates are decided at M5 (owner to confirm).
- 2026-11-06, experiment manager (AKS-102), found while building `src/lcsim/runs/`: "Statistic definitions" states the NaN rule (a NaN replication value is left out, n is reported, an undefined mean or half-width is `null`), makes the paired scenario differences precise (pairs in scenario order, later minus earlier, NaN pairs left out, separated when n ≥ 2 and |mean| > half-width), and adds to the warm-up check that a metric with m̄ = 0 is not reported as changed, that p rounds a half up and that W210 follows the adapter's warnings (owner to confirm). `scipy` is now a runtime dependency: the manager computes `scipy.stats.t.ppf` for every run.
- 2026-11-06, M3 performance (AKS-104): the acceptance row for the 30-replication run of the three-machine line names its M3 evidence, `tests/perf/test_three_machine_line.py` and `docs/research/perf-M3.md`: 1.52 to 1.79 s with 4 workers under `taskset -c 0-3 pytest -m perf` in a 4-core cloud container, so the target is measured, not confirmed. The run gets as many workers as the cores the process may use, 4 under the protocol (the simplest reading of spec 3's "cores of the active tier" before tiers exist; owner to confirm).

Since version 0.6, during M4; the lines below were added after version 0.6:

- 2026-11-07, `queue`, `batch` and `unbatch` blocks (AKS-105), found while building them in `src/lcsim/engines/process/blocks.py`: "Rules that apply across blocks" adds "Queue" (an item passing straight through waits 0 s and is never counted waiting; `discipline` picks when space frees; an item counts against `capacity` until it moves; a discarded item leaves work in progress and has no wait) and "Batch and unbatch" (a batch is one unit, created when its first unit was; a timeout per batch; a refused batch waits at the `batch` block while the next collects; an unbatch splits one level and passes a single item on; a sink counts a batch once, with one cycle time; work in progress counts items), and says that a full blocking `queue` refuses while a discarding `queue`, a `batch` and an `unbatch` always accept; "Branch rules" says a `queue` counts every item it holds and a `batch` and an `unbatch` count 0. "Statistic definitions" confirms the `<queue>.wait.mean`, `<batch>.wait.mean` and `<source>.discarded`, `<queue>.discarded` rows with their precise readings (a batch's wait ends when it moves on, later than forming when refused), says what a queue's `queue_length` counts, and adds `<queue>.queue_length` to the time series. "Benchmark definitions" says how the two M4 benchmark files read the table (components, distributions, metrics, exact values, seeds 1006 and 1007). The warning line, the paragraph after the defaults and the acceptance table name the three blocks as built. All owner to confirm.
- 2026-11-07, review of PR #27 (AKS-105): "Queue" says that before a queue counts as full, the items the next block takes at that instant move on first, so the items of one batch reaching a discarding queue of 1 through an `unbatch` are not discarded while the next block takes them (owner to confirm).
- 2026-11-07, third review of PR #27 (AKS-105): "Queue" restates the same-instant rule. A blocking queue that is full only because its own offer is still due refuses an arriving item, which moves in at that same instant by the Blocking rule. A discarding queue decides about such an item only after that offer, discarding it only if the queue is still full with its offer refused. The earlier line's wording (the items the next block takes move on first) described the way it was built rather than the rule (owner to confirm).
