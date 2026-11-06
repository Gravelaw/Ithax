# Performance at M3: a 30-replication run of the three-machine line

Measured 2026-11-06 for AKS-104 under the Build guide's "Performance measurement protocol".
**Status: measured, not confirmed.** This container is not the owner's low-tier machine. The
owner confirms the target by running the same command on a machine capped to 4 cores and
8 GB and recording the result in `docs/DECISIONS.md` (tracked in AKS-82).

## Question

Spec 2 acceptance (M3 measured, owner confirms): "A 30-replication run of the three-machine
line finishes in under one minute (proposed target; measured per the Build guide protocol,
confirmed by the owner)". Does it, on four cores, and what does it cost in memory?

## Finding

The run takes about 1.6 s with 4 workers, 37 times inside the proposed one-minute target. It
takes 2.7 s with everything on one core. At its peak the whole process tree (the driving
process, the run's worker and its 4 pool processes) holds about 560 MiB resident.

| Measure | Python 3.13.18 (3 runs) | Python 3.11.18 (3 runs) | One core, 3.13.18 (1 run) |
| --- | --- | --- | --- |
| Wall time, `create` to the end of `execute` | 1.52, 1.64, 1.55 s | 1.68, 1.79, 1.58 s | 2.65 s |
| `workers` | 4 | 4 | 1 |
| Peak RSS of the driving process (`RUSAGE_SELF`) | 219.0, 219.0, 218.0 MiB | 221.8, 217.6, 219.7 MiB | 202.0 MiB |
| Peak RSS of the largest finished child (`RUSAGE_CHILDREN`) | 151.4, 151.5, 151.6 MiB | 153.8, 153.1, 153.0 MiB | 151.5 MiB |
| Peak RSS of the whole tree at once (sampled from `/proc` every 0.1 s) | 560.3, 559.9, 559.9 MiB | 551.1, 550.3, 549.0 MiB | 272.1 MiB |
| pytest session (`... passed in`) | 2.67, 2.60, 2.73 s | 3.06, 3.18, 2.90 s | 3.87 s |

- **Target:** under 60 s (spec 2, proposed). Met with a margin of about 58 s on every run.
- **The informal M2 figure** was 1.4 s with 4 workers for the adapter alone, not under the
  protocol (`docs/sessions/2026-11-06-M2.md`). The local target adds loading, validate,
  the run folder, a spawned worker, collect, the statistics and the Parquet files; the
  two figures differ by about 0.2 s, but they were not measured the same way.
- **How to read the memory.** `RUSAGE_SELF` is the pytest process, which also collected
  the other 1,692 tests before deselecting them; the service's own figure comes at M6.
  `RUSAGE_CHILDREN` is the largest single finished descendant (Linux reports the maximum,
  not a sum): here the run's worker, which imports the adapter. The tree figure is the one
  to compare with the low tier's 8 GB: 0.56 GiB, 7% of it. The default memory limit (spec 4
  "Limits", half of physical memory) would be 4 GiB on the low tier.

### Machine

| | |
| --- | --- |
| CPU | Intel Xeon Processor @ 2.10 GHz, 4 CPUs, 1 thread per core (`lscpu`) |
| `os.cpu_count()` | 4 |
| `len(os.sched_getaffinity(0))` | 4 under `taskset -c 0-3`; 1 under `taskset -c 0` |
| Memory | 15.71 GiB (`os.sysconf`; `MemTotal` 16,472,088 kB), no swap |
| System | Linux 6.18.44 x86_64, glibc 2.39, a cloud container |

### Library versions

| Library | Python 3.13.18 | Python 3.11.18 |
| --- | --- | --- |
| lcsim | 0.0.0 | 0.0.0 |
| numpy | 2.5.4 | 2.4.6 |
| scipy | 1.18.1 | 1.17.1 |
| pyarrow | 26.0.1 | 26.0.1 |
| simpy | 4.1.2 | 4.1.2 |
| pint | 0.26.2 | 0.25.3 |
| jsonschema | 4.26.0 | 4.26.0 |
| pytest | 9.2.0 | 9.2.0 |

## Sources

- Build guide, "Performance measurement protocol" and "Known gaps" ("Performance targets are
  proposals ... Measured at M3, M6, M9; confirmed by the owner before M11").
- Spec 2 "Acceptance tests" (the row above) and spec 3 "Run queue" (a run receives `workers`
  = the cores of the active tier) and "Hardware tiers".
- `tests/perf/test_three_machine_line.py`, which prints each measurement as one JSON line
  under "performance measurements" at the end of the pytest session (`tests/perf/conftest.py`).
- Python documentation for `resource.getrusage` (`ru_maxrss` is in kilobytes on Linux).

## Decision

- The target is **measured** at M3, which closes the milestone's perf gate for a session
  (guide protocol). It is not **confirmed** until the owner runs the same command on a
  machine capped to 4 cores and 8 GB (AKS-82).
- The check runs the shipped `examples/three_machine_line.json` unchanged (experiment
  `base`: 30 replications of 100 h after 20 h of warm-up, seed 12345) through
  `LocalTarget.create` and `execute`, and times both together, since the user waits for
  both. `workers` is the number of cores the process may use (`os.sched_getaffinity`), which
  is 4 under the protocol's `taskset -c 0-3`, the low tier's cores (simplest reading of
  "cores of the active tier" before the service detects tiers at M6; owner to confirm).
- No target changes: the margin is wide, and the guide reserves changing a target for the
  owner's confirmation.

## Tested

The command, run from the repository root:

```bash
source .venv/bin/activate && taskset -c 0-3 pytest -m perf
```

It selects only `tests/perf/` (the marker `perf` is registered in `pyproject.toml` and
excluded from `bash scripts/check.sh` by `addopts`). The Python 3.11.18 runs used a
separate virtual environment with `pip install -e ".[dev]"`, and the one-core run used
`taskset -c 0 pytest -m perf`. `taskset` is `/usr/bin/taskset`.

For the owner (AKS-82): on a machine or virtual machine capped to 4 cores and 8 GB, after
`pip install -e ".[dev]"`, run `taskset -c 0-3 pytest -m perf` (on Windows, where there is no
`taskset`, the cap comes from the virtual machine or WSL settings; run `pytest -m perf`) and
record the "performance measurements" line in `docs/DECISIONS.md`.
