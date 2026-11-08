# Performance at M6: the engine service, a search and the distribution fit

Measured 2026-11-07 for AKS-114 under the Build guide's "Performance measurement protocol".
**Status: measured, owner to confirm on the low tier.** This container is not the owner's
low-tier machine. The owner confirms each target by running the same command on a machine
capped to 4 cores and 8 GB and recording the result in `docs/DECISIONS.md` (AKS-82).

## Question

Spec 3 "Performance targets" (proposed, measured on the low tier): is the service ready
within 5 seconds of start, does it validate a 200-component model within 200 milliseconds,
and does it use under 300 MB of memory when idle? And, for the M6 close: what does a search
cost (M5 "Left", "Search cost"), and what does the slowest distribution fit cost on columns
up to the import's record limit (AKS-113)?

## Finding

All three service targets are met on 4 cores, on both Python versions. Idle memory after a
run is the closest to its target: 87% of it on 3.13 and 90% on 3.11. A search costs about
0.07 to 0.10 s per replication, so the default budget of 50 takes under a minute for the
coffee shop. Fitting a column at the record limit takes about 21 s, almost all of it the
triangular fit.

| Target (spec 3, proposed) | Python 3.13.18 | Python 3.11.18 | Met |
| --- | --- | --- | --- |
| Ready within 5 s of start (three starts) | 1.377, 1.327, 1.347 s | 1.448, 1.394, 1.395 s | yes, by 3.5 s |
| Validation of a 200-component model within 200 ms (20 calls) | median 0.076 s, max 0.160 s, min 0.072 s | median 0.080 s, max 0.156 s, min 0.080 s | yes |
| Under 300 MB idle, just after the start (each of the three starts) | 178.3, 178.3, 178.4 MiB (187 MB) | 185.2, 185.4, 185.3 MiB (194 MB) | yes |
| Under 300 MB idle, after the coffee shop's 30-replication run | 248.6 MiB (261 MB) | 256.6 MiB (269 MB) | yes, by 39 and 31 MB |

- **Ready** is the first `200` from `GET /v1/system`, timed from just before
  `python -m lcsim.service` is started, polled every 5 ms. The first of the three starts
  detects the hardware and stores the tier in `settings.json`; it is within 0.05 s of the
  others.
- **Validation** is `POST .../validate` over loopback HTTP from request to response: the
  schema pass, the meaning pass and the SimPy adapter's `validate` on a source, 198 servers
  in a line and a sink (30,439 bytes, no issues), after one untimed call. The largest call
  is about twice the median, so the target's margin is the largest call's 40 ms.
- **Idle memory** is the resident memory of the service and every process it started
  (`/proc`, the code of `lcsim.runs.limits.process_tree_memory`), read after 5 s with no
  request; 300 MB is read as 300,000,000 bytes (286.1 MiB; rule 5, owner to confirm). After
  a run the worker has ended, so the figure is the service alone: running the coffee shop
  imports the experiment manager, SimPy and the statistics into the service's process and
  adds about 70 MiB, which stays. The run itself (1.39 s on 3.13, 1.54 s on 3.11, 4
  workers) peaked at 789 MiB (3.13) and 814 MiB (3.11) for the whole tree.
- **Peak RSS by `resource.getrusage`.** `RUSAGE_CHILDREN` after the three starts is the
  largest finished service process: 220.3 MiB (3.13), 232.9 MiB (3.11). Later checks in the
  same session report the largest child so far, so their `RUSAGE_CHILDREN` and
  `RUSAGE_SELF` figures (375.7 MiB and 382.7 MiB at the end) are the pytest process and its
  children over the whole session, not one check.

### A search's cost (M5 "Left")

The machine-count search, `benchmarks/machine_count/model.json` (the coffee shop with `tills`
1 to 5, 200 h after 10 h of warm-up, `search.replications` 10, 30 replications for each
confirmation), through `LocalTarget.create` and `execute` with 4 workers, as perf-M3 runs
the three-machine line. "Default budget" removes `budget` (default 50) and widens `tills`
to 1 to 50, so that the exhaustive path searches 50 candidates; a narrower range would stop
at its number of combinations.

| Search | Candidates | Confirmed | Replications | Wall time 3.13 | Wall time 3.11 | Peak tree memory 3.13 |
| --- | --- | --- | --- | --- | --- | --- |
| As shipped, budget 10 (five combinations) | 5 | 2 | 110 | 7.59 s (0.069 s each) | 7.92 s | 673 MiB |
| Default budget 50, `tills` 1 to 50 | 50 | 2 | 560 | 51.9 s (0.093 s each) | 54.3 s | 692 MiB |

Both find `tills` = 2. The cost scales with the replications run: candidates times
`search.replications`, plus the confirmed candidates times the experiment's replications.
M5's estimate of 620 replications assumed four confirmations; here only `tills` 1 and 2 are
feasible, so two are confirmed. Each evaluation runs in a spawned worker of its own
(spec 1 "Division of labour"). Memory does not grow with the budget (the driving process keeps only each candidate's metrics, review of PR #32). No
target names a search; at about 0.1 s per replication of this model, a budget of 50 with
long runs could take tens of minutes, which the run time limit (`run_time_limit_s`, default
600 s) would stop: an owner question below.

### The distribution fit's cost (AKS-113)

`lcsim.model.fit.fit_column` on a triangular column (`scipy.stats.triang.ppf` at the
evenly spaced quantiles (i + 0.5)/n, c 0.3, from 1 to 5 minutes; deterministic, no random
numbers), with the unit `min`, in the pytest process. Each family is then timed alone
(the fit and its Kolmogorov–Smirnov score). The best candidate is `triangular` at every size.

| Values | Whole fit 3.13 | Triangular alone 3.13 | Weibull alone 3.13 | Whole fit 3.11 |
| --- | --- | --- | --- | --- |
| 1,000 | 0.049 s | 0.032 s | 0.006 s | 0.060 s |
| 10,000 | 0.146 s | 0.091 s | 0.022 s | 0.161 s |
| 100,000 | 1.17 s | 0.89 s | 0.18 s | 1.86 s |
| 1,048,576 (the record limit) | 20.9 s | 18.5 s | 2.22 s | 23.0 s |

The other four families take under 0.1 s each at every size. The triangular fit is
scipy's numerical maximum likelihood over three parameters and grows faster than the column
(18 times the time for 10.5 times the values from 100,000 to the limit); the process's peak
resident memory rose to 376 MiB (3.13) at the limit. The fit endpoint answers within one
request, so a client waits about 21 s for a column at the record limit, and the service
thread is busy for as long: no target names it, an owner question below.

### Machine

| | |
| --- | --- |
| CPU | Intel Xeon Processor @ 2.30 GHz, 4 CPUs (`/proc/cpuinfo`); perf-M3 ran on a 2.10 GHz container |
| `os.cpu_count()` | 4 |
| `len(os.sched_getaffinity(0))` | 4 under `taskset -c 0-3` |
| Memory | 15.71 GiB (`os.sysconf`; `MemTotal` 16,472,400 kB) |
| System | Linux 6.18.44 x86_64, glibc 2.39, a cloud container |
| `GET /v1/system` | `workers` 4 (tier `low`: 4 cores) |

### Library versions

| Library | Python 3.13.18 | Python 3.11.18 |
| --- | --- | --- |
| numpy | 2.5.4 | 2.4.6 |
| scipy | 1.18.1 | 1.17.1 |
| pyarrow | 26.0.1 | 26.0.1 |
| simpy | 4.1.2 | 4.1.2 |
| pint | 0.26.2 | 0.25.3 |
| fastapi | 0.162.1 | 0.162.2 |
| optuna | 5.0.0 | 5.0.0 |
| pytest | 9.2.0 | 9.2.0 |

The same session also reran the M3 check: the three-machine line took 1.59 s (3.13) and
1.74 s (3.11) against its 60 s target, as at M3.

## Sources

- Build guide, "Performance measurement protocol" and "Known gaps" ("Performance targets are
  proposals ... Measured at M3, M6, M9; confirmed by the owner before M11").
- Spec 3 "Performance targets", "Run queue" (`workers`) and "Hardware tiers"; spec 2
  "Simulation-based optimization"; spec 1 "Experiments" (`search.budget` default 50,
  `search.replications` default 10).
- `docs/sessions/2026-11-07-M5.md`, "Left", "Search cost"; the AKS-113 note on the fit's
  cost near the record limit (`docs/research/spec-3-distribution-fit.md`).
- `tests/perf/test_service.py` (new) and `tests/perf/test_three_machine_line.py`, which print
  each measurement as one JSON line under "performance measurements"
  (`tests/perf/conftest.py`).
- Python documentation for `resource.getrusage` (`ru_maxrss` in kilobytes on Linux).

## Decision

- The three service targets are **measured** at M6, which closes the milestone's perf gate
  for a session (guide protocol). None is **confirmed** until the owner runs the same command
  on a machine capped to 4 cores and 8 GB (AKS-82). No target changes.
- Readings taken for the measurement (rule 5, owner to confirm; spec 3 "Performance
  targets" says so): ready is the first `200` from `GET /v1/system` after the process is
  started; validation is the whole request's round trip, the largest of 20 calls; idle
  memory is the service with the processes it started, after 5 s without a request, both
  after the start and after a run; 300 MB is 300,000,000 bytes.
- For the owner: idle memory after a run (261 to 269 MB) is the nearest to its target;
  on the low tier, with a different Python build, it may cross 300 MB. A search has no
  target, and its time grows with budget × replications; the fit at the record limit takes
  about 21 s within one request.

## Tested

The command, run from the repository root on each Python:

```bash
source .venv/bin/activate && taskset -c 0-3 pytest -m perf
```

On 2026-11-07, on branch `akshayjain00/aks-114-m6-route-table-test-offline-test-perf` at
9915f24 (the code of the M6 close; later commits change documents only): 10 passed on
Python 3.13.18 in 143.95 s and on Python 3.11.18 (a separate virtual environment with
`pip install -e ".[dev]"`) in 153.28 s. `taskset` is `/usr/bin/taskset`. Perf checks carry
the marker `perf` and are excluded from `bash scripts/check.sh` by `addopts`.

For the owner (AKS-82): on a machine or virtual machine capped to 4 cores and 8 GB, after
`pip install -e ".[dev]"`, run `taskset -c 0-3 pytest -m perf` (on Windows, where there is no
`taskset`, the cap comes from the virtual machine or WSL settings; run `pytest -m perf`) and
record the "performance measurements" lines in `docs/DECISIONS.md`.
