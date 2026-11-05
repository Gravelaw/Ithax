# Spec 2: Core Engine for Process Simulation and Optimization

Two engine adapters, both in Python: discrete-event simulation on SimPy, and optimization on HiGHS. Together with an experiment manager they make Phase 1 a complete product.

> **Warning: partly tested.** Five block types ran in a prototype. The other seven, the optimization layout in the model file, and simulation-based optimization have never run. Performance targets are proposals. Verify each at its milestone and update this spec. See "Known gaps" in the Build guide.

## Scope

- **In:** the process block library, probability distributions, the experiment manager, mathematical optimization, simulation-based optimization, benchmarks.
- **Out:** agent-based and system dynamics models (spec 5), any physics (spec 6).

## Process block library

| Block | Models |
| --- | --- |
| Source | Arrivals, by distribution or from a schedule |
| Queue | A waiting line with a discipline (first in first out, priority) and optional capacity |
| Server | A resource that processes items, with capacity and service time |
| Delay | A fixed or random wait with no resource, such as transport or drying |
| Branch | Routing by probability, attribute or shortest queue |
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

- **Replications:** each run uses an independent, recorded random seed.
- **Warm-up:** an initial period is excluded from statistics.
- **Confidence intervals:** 95% by default, computed across replications.
- **Scenarios:** named sets of parameter values, compared side by side.
- **Parallel runs:** replications use all available processor cores.

## Optimization

| Kind | Use | Engine |
| --- | --- | --- |
| Mathematical | Problems written as an objective and constraints: product mix, transport, assignment, blending, scheduling | HiGHS through Pyomo |
| Simulation-based | Finding the best parameter values of a simulation model, such as number of machines | Optuna, with a set replication budget per candidate |

Mathematical problems are entered in a table-style editor: decision variables, objective, constraints. Simulation-based optimization picks any entries from `parameters` as variables and any output as the objective.

## Benchmarks

| Case | Known answer |
| --- | --- |
| Single server queue with random arrivals and service (M/M/1) | Mean wait from queueing theory |
| Multi-server queue (M/M/c) | Erlang C formula |
| Two queues in series | Product-form result |
| Inventory with one order per period (newsvendor) | Critical ratio formula |
| Five textbook linear and integer programs | Published optimal values |

Simulation benchmarks pass when the known answer lies inside the 95% confidence interval. Optimization benchmarks pass when the objective matches to four significant figures.

## Detailed specification

The sections below are binding. Where they differ from the summary above, these win.

### Block reference

| Type | Ports | Settings | Behaviour |
| --- | --- | --- | --- |
| `source` | `out` | `interarrival` (distribution), optional `first_arrival`, `max_items` | Creates one item, waits one interarrival time, repeats |
| `server` | `in`, `out` | `capacity` (integer), `service` (distribution), optional `queue_capacity`, `discipline`, `pool` | Items wait in the server's own queue, then hold one unit of capacity for one service time |
| `delay` | `in`, `out` | `time` (distribution) | Holds each item for the sampled time; no queue, no capacity limit |
| `branch` | `in`, one output per route | `rule`, `weights` | Sends each item down one route |
| `queue` | `in`, `out` | `capacity`, `discipline` | A standalone buffer, for use ahead of a batch or branch |
| `batch` | `in`, `out` | `size`, optional `timeout` | Collects `size` items and releases them as one |
| `unbatch` | `in`, `out` | none | Splits a batch back into its items |
| `store` | `in`, `out` | `initial`, `reorder_point`, `order_quantity`, `lead_time` | Holds stock; reorders when stock falls to the reorder point |
| `resource_pool` | none | `capacity` | Shared staff or tools; servers name it in their `pool` setting |
| `schedule` | none | `target`, `shifts` | Changes the capacity of a server or pool over time |
| `failure` | none | `target`, `time_to_failure`, `time_to_repair` | Takes a server out of service at random and returns it after repair |
| `sink` | `in` | none | Removes the item and records its statistics |

Rules that apply across blocks:

- **Server queue.** Unlimited and first in, first out unless `queue_capacity` or `discipline` says otherwise.
- **Blocking.** If the next block cannot accept an item, the item stays where it is and keeps holding its capacity.
- **Branch rules.** `probability` uses `weights`, an object mapping route name to weight. `shortest_queue` picks the route with the fewest waiting items. `attribute` routes on a named item attribute.
- **Simultaneous events.** Events at the same time run in the order they were scheduled.

The prototype exercised `source`, `server`, `delay`, `branch` with the `probability` rule, and `sink`. The other blocks are specified but untested.

### Statistic definitions

| Statistic | Definition |
| --- | --- |
| `<server>.wait.mean` | Mean time from arrival at the server to start of service, over items whose service starts after warm-up |
| `<server>.utilization` | Busy time inside the observed period, divided by capacity times the observed period |
| `<sink>.throughput` | Items reaching the sink after warm-up, divided by the observed period |
| `<sink>.cycle_time.mean` | Mean time from creation to sink, over items reaching the sink after warm-up |

- The observed period runs from the end of warm-up to the end of the run.
- Items still in the system at the end are not counted in waits or cycle times.
- Across replications: the reported mean is the mean of replication means. The half-width is the t value for the chosen confidence and n minus 1 degrees of freedom, times the standard deviation, divided by the square root of n.

### Benchmark definitions

| Case | Settings | Known answer |
| --- | --- | --- |
| M/M/1 | Exponential arrivals, mean 2 min; one server, exponential service, mean 1.5 min | Mean wait 4.500 min |
| M/M/2 | Exponential arrivals, mean 1 min; two servers, exponential service, mean 1.5 min | Mean wait 1.929 min |
| Product mix | Maximize 45 chairs + 80 tables; wood 5 and 20 per unit, 400 available; labour 10 and 15 per unit, 450 available | 24 chairs, 14 tables, profit 2,200 |

Both queue cases use 30 replications of 200 hours with 10 hours of warm-up.

### Prototype results

A throwaway translator from the model file to SimPy produced these. They show the format and statistic definitions work. The prototype is a reference only: it must not be copied or extended into the product, and it is deleted at the end of milestone M3. See the Build guide.

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

### Simulation-based optimization

- **Variables** are entries in `parameters` that have `min` and `max`.
- **Budget** is a number of candidate settings, default 50.
- **Each candidate** runs the experiment's replications with the same seed, so candidates face the same random events.
- **Result** is the best candidate, its metrics with confidence intervals, and the full list of candidates tried.

## Research before building

Complete these and record the findings, with sources, in a short note in the repository before writing code. If a finding contradicts this spec, update the spec first.

- **Simulation library.** Compare SimPy, salabim and Ciw on features, speed, upkeep and licence.
- **Output analysis methods.** Published methods for choosing warm-up length and number of replications.
- **Simulation-based optimization.** Ranking-and-selection and Bayesian methods from the simulation literature.
- **Solver layer.** Current versions and licences of HiGHS, Pyomo, OR-Tools and Optuna.
- **Benchmark sources.** Textbook problems with published answers that may be reused freely.
- **Prior art.** Papers on generating process simulation models from text, for the block design.

## Acceptance tests

- [ ] Every block has a unit test and appears in at least one benchmark or template.
- [ ] All benchmarks pass on every build.
- [ ] The three example models from spec 1 run end to end.
- [ ] A 30-replication run of the three-machine line finishes in under one minute on the low hardware tier (proposed target).
- [ ] Simulation-based optimization finds the known best machine count on a test model.
