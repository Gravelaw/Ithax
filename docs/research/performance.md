# Performance at M10: the ten templates on the low tier

Measured 2026-11-09 for AKS-125 under the Build guide's "Performance measurement protocol".
**Status: measured on a container capped to the low tier, owner to confirm.** The owner
confirms by running the same command on a machine capped to 4 cores and 8 GB and recording
the result in `docs/DECISIONS.md` (AKS-82).

## Question

Spec 0 "Success measures", low-tier performance (M10): "All Phase 1 templates run to
completion on the low-tier laptop", measured by a "timed run of the ten templates on a
machine capped to the low tier, recorded in `docs/research/performance.md`". Spec 3
acceptance (M10, agent on a capped container, owner confirms): "All Phase 1 templates run on
a machine or virtual machine capped to the low tier". The low tier is 4 processor cores and
8 GB of memory (spec 0 "Platform and hardware").

## Finding

All ten templates, and each one's exercise, run to completion on 4 cores within an 8 GiB
memory cap: 20 runs, every one `done`, 37.2 s in all (18.0 s for the ten templates alone).
Every run but the two searches of "How many machines?" takes 0.8 to 2.4 s; those take 6.8
and 8.1 s, since each runs five candidates and confirms the best. The control group's peak
memory over the whole session, the interface check with Chromium included, was 967 MiB of
the 8,192 MiB allowed, and it never reached its limit (`memory.failcnt` 0). The M3, M6 and
M9 targets were met again in the same capped session.

| Template | Template run (s) | Exercise run (s) | Experiment |
| --- | --- | --- | --- |
| Coffee shop queue (`coffee_shop`) | 1.22 | 1.19 | 30 × 200 h |
| Three-machine production line (`three_machine_line`) | 1.51 | 1.57 | 30 × 100 h |
| Machine breakdowns (`machine_breakdowns`) | 1.15 | 1.05 | 30 × 200 h |
| Clinic patient flow (`clinic_patient_flow`) | 1.12 | 1.10 | 30 × 200 h |
| Warehouse pick and pack (`warehouse_pick_pack`) | 2.32 | 2.24 | 30 × 216 h, hourly samples |
| Inventory reorder point (`inventory_reorder_point`) | 0.84 | 0.88 | 30 × 1,000 d |
| Transport plan (`transport_plan`) | 0.92 | 1.11 | one solve (HiGHS) |
| Product mix (`product_mix`) | 1.05 | 1.05 | one solve |
| Staff rota (`staff_rota`) | 1.07 | 0.86 | one solve (integer) |
| How many machines? (`how_many_machines`) | 6.84 | 8.09 | search over 1 to 5 tills, 30 × 200 h each, best confirmed |

Each run is timed from `LocalTarget.create` to the end of `execute`: loading, validation,
translation, the engine (worker processes for a simulation), collecting and writing the run
folder, with 4 workers. An optimization run's second or so is mostly starting the engine's
worker and writing the run folder; the solve itself is milliseconds.

**Memory.** The peak resident memory of the pytest process and every process it started,
sampled every 0.1 s, was 488 to 503 MiB during an optimization run and 723 to 749 MiB during
a simulation run (the four worker processes); these include pytest itself, which had grown to
about 400 MiB by then from the checks run before. `resource.getrusage` at the end of the
template checks: `RUSAGE_SELF` 402.3 MiB, `RUSAGE_CHILDREN` 402.3 MiB (the largest finished
child, a service process of the earlier checks). The control group's
`memory.max_usage_in_bytes` was 1,013,710,848 bytes (967 MiB) for the whole session.

**The other targets in the same session** (`taskset -c 0-3 pytest -m perf`, 32 passed):

| Target (spec 2 and 3, proposed) | Measured | Met |
| --- | --- | --- |
| A 30-replication run of the three-machine line in under one minute (M3) | 1.45 s | yes |
| Service ready within 5 s (M6) | 1.145, 1.221, 1.215 s | yes |
| Validation of a 200-component model within 200 ms (M6) | median 0.068 s, max 0.148 s | yes |
| Under 300 MB idle after a run (M6) | 249.1 MiB (261 MB) | yes |
| Selecting a block on a 200-component canvas paints within 100 ms (M9) | largest of 12: 29.1 ms (median 16.6) | yes |
| Service ready and idle with the interface served (M9) | 1.295 s; 183.2 MiB | yes |

### Machine and cap

- **Cores:** `taskset -c 0-3`; the container has 4 cores (`os.cpu_count()` 4, affinity 4).
- **Memory cap, as enforced:** a cgroup v1 memory control group, `/sys/fs/cgroup/memory/lcsim-lowtier`,
  with `memory.limit_in_bytes` and `memory.memsw.limit_in_bytes` both 8,589,934,592 bytes
  (8 GiB); the shell that started pytest was moved into it first, so pytest and every
  process it started (workers, services, Node and Chromium) were in it. The check reads the
  limit back from `/proc/self/cgroup` and records it (`cgroup_memory_limit_gib` 8.0). That
  the limit is enforced was shown first with a 100 MiB group in which a 300 MiB allocation
  was killed (exit 137, `memory.failcnt` 131). `RLIMIT_AS` was not set: an address-space
  limit counts reserved virtual memory, which Chromium and the worker processes reserve far
  beyond what they use, so it would not model 8 GB of memory. The container has no swap.
- **Physical memory** 15.71 GiB (16,086 MiB; the cap is what limits the run).
- Linux 6.18.44 (glibc 2.39), Python 3.13.18; numpy 2.5.4, scipy 1.18.1, pyarrow 26.0.1,
  simpy 4.1.2, pint 0.26.2; HiGHS through Pyomo as at M5; Node 22.23.4, Playwright 1.63.0,
  Chromium 153.0.8010.12.
- This is a cloud container, not the owner's low-tier laptop: its cores may be faster or
  slower than a laptop's, and its disk and memory bandwidth differ. Spec 0 says real low-end
  hardware should still be tried before any release.

## Sources

- Spec 0 "Platform and hardware" and "Success measures"; spec 3 "Performance targets" and
  its acceptance table; the Build guide's "Performance measurement protocol".
- `tests/perf/test_templates.py` (this check), `tests/perf/test_three_machine_line.py`,
  `test_service.py` and `test_interface.py` (the earlier checks, unchanged).
- The Linux kernel's cgroup v1 memory controller documentation (`memory.limit_in_bytes`,
  `memory.memsw.limit_in_bytes`, `memory.max_usage_in_bytes`, `memory.failcnt`).

## Decision

- The low-tier performance measure is **measured**: all ten Phase 1 templates and their
  exercises run to completion on 4 cores within 8 GiB. Spec 0 sets no time for a template;
  the slowest, a search over five candidates, takes about 8 s. It is **confirmed** when the
  owner runs the command below on a machine capped to 4 cores and 8 GB (AKS-82).
- The check runs each template and its exercise, as a learner runs them, through the local
  target the service uses; it asserts only that each run ends `done` (spec 0's "run to
  completion") and records the times (rule 5, owner to confirm).
- "8 GB" is read as 8 GiB, the larger reading, enforced by a memory control group, not by
  `RLIMIT_AS` (rule 5, owner to confirm).

## Tested

```bash
sudo mkdir /sys/fs/cgroup/memory/lcsim-lowtier            # cgroup v1; on cgroup v2 use
echo 8589934592 | sudo tee /sys/fs/cgroup/memory/lcsim-lowtier/memory.limit_in_bytes
echo 8589934592 | sudo tee /sys/fs/cgroup/memory/lcsim-lowtier/memory.memsw.limit_in_bytes
(cd ui && npm run build)
sh -c 'echo $$ > /sys/fs/cgroup/memory/lcsim-lowtier/cgroup.procs; exec taskset -c 0-3 pytest -m perf'
```

On cgroup v2, or without root, a systemd scope with `MemoryMax=8G` should do the same
(`systemd-run --user --scope -p MemoryMax=8G taskset -c 0-3 pytest -m perf`; not tried here,
since this container's cgroups are v1). On the owner's low-tier machine, or WSL capped with
`memory=8GB` and `processors=4` in `.wslconfig`, plain `taskset -c 0-3 pytest -m perf` is the
protocol's command.

Run here at commit f9a15e2 plus this check (the check's file was committed with this note):
exit 0, 32 passed, 3,899 deselected, 174.75 s; the per-run lines above are the session's
"performance measurements" section.
