# Simulation library (spec 2, M2)

## Question

Spec 2 "Research before building", M2: compare SimPy, salabim and Ciw on features, speed,
upkeep and licence. Spec 2's summary names SimPy ("discrete-event simulation on SimPy");
this note confirms or replaces it. It also checks spec 2's rule for simultaneous events
against the chosen library.

## Finding

| | SimPy 4.1.2 | salabim 26.0.9 | Ciw 3.2.7 |
| --- | --- | --- | --- |
| Licence (from the wheel's licence file) | MIT, `LICENSE.rst` | MIT, `LICENSE.txt` | MIT, `LICENSE.txt` |
| What it is | Process-based DES kernel: events, processes, `Resource`, `PriorityResource`, `PreemptiveResource`, `Container`, `Store` | Object-oriented DES with queues, resources, stores, states, monitors, 2D/3D animation | Simulator for open queueing networks: classes, Type I blocking, priorities, baulking, reneging, server schedules, batch arrivals |
| Dependencies | none | none; its default "yieldless" mode needs `greenlet` (MIT AND PSF-2.0), which it does not declare | numpy, networkx, tqdm, setuptools |
| Requires-Python | >=3.8 | >=3.7 | not declared; docs say tested on 3.8 to 3.12 |
| Releases since 2024-11-06 | 1 (4.1.2, 2026-05-24) | 36 (latest 26.0.9, 2026-11-03) | 4 (latest 3.2.7, 2025-12-05) |
| 100 replications of the spec 2 M/M/1 case, one process | 4.7 to 5.4 s | 142.3 s (yieldless default); about 119 s (yield mode, extrapolated from 10 replications in 11.9 s) | 8.9 s |
| Random numbers | Supplied by the caller; any numpy `Generator` per component works | Supplied by the caller works (tested) | Built-in distributions call Python's global `random` module (`ciw.dists.Exponential.sample` is `expovariate(self.rate)`); `ciw.seed()` seeds the global `random` and a module-level `ciw.rng` |
| Capacity that changes over time (spec 2 `schedule`) | No: `Resource.capacity` is a read-only property; the adapter must build it | Yes: `Resource.set_capacity()` | Yes: server schedules |
| Inventory with reorder (spec 2 `store`) | `Container` gives the stock level; the reorder rule is adapter logic | `Store`/`Resource` with adapter logic | No inventory concept |
| Shared pool across servers (spec 2 `resource_pool`) | Yes: a second `Resource` both servers request | Yes | No: servers belong to one node |

Speed and correctness (see Tested): all three libraries reproduce the M/M/1 mean wait
within three standard errors of 4.500 min. SimPy and salabim, fed the same numpy streams,
give the same mean and standard error over the 100 replications (4.533 min, 0.053), which
cross-checks both FIFO server implementations. salabim is about 25 to 30 times slower than
SimPy here; a profile of one replication shows 68% of the time in salabim's
`_check_overlapping_parameters`,
which calls `inspect.signature` every time a component (here, a customer) is created.
Ciw is under twice SimPy's time but draws its random numbers from Python's global
generator, which CLAUDE.md forbids ("never the global random generator") and which breaks
spec 1's per-component stream scheme unless every distribution and routing object is
replaced.

Upkeep: SimPy releases rarely (4.1.1 in November 2023, 4.1.2 in May 2026, adding Python
3.13 and 3.14 support and a GitLab CI), but its API has been stable since 4.0 (April 2020).
salabim releases often, from one main developer.
Ciw is maintained by an academic group at a slower pace and does not list Python 3.13.

Simultaneous events in SimPy 4.1.2 (tested and read in `simpy/core.py`): the event list is a
heap of `(time, priority, event id, event)`; `URGENT` (0) sorts before `NORMAL` (1), and
the event id is a counter, so events at one instant run in scheduling order within a
priority. `Initialize` (the first step of a new process) and `Interruption` are `URGENT`.
So a process started at time t runs its first step before `NORMAL` events already due at
t, which departs from spec 2's plain "in the order they were scheduled". `env.run(until=T)`
schedules its stop event as `URGENT` at T, so no event due exactly at T runs (also stated
in SimPy's "Environments" guide).

Gaps the adapter must fill at M4 (event logic, not numerical code): capacity that changes
with a schedule (SimPy has no capacity setter), LIFO discipline (use `PriorityResource`
with a priority that decreases with arrival order), and preempt-resume for failures
(`PreemptiveResource` or interrupts preempt, but the adapter tracks remaining service).

## Sources

- SimPy on PyPI, https://pypi.org/project/simpy/ (opened 2026-11-06): version 4.1.2, MIT.
- SimPy repository, https://gitlab.com/team-simpy/simpy (opened 2026-11-06): 4.1.2 changes,
  Python 3.13 and 3.14 support, CI.
- SimPy "Environments" guide,
  https://simpy.readthedocs.io/en/latest/topical_guides/environments.html (opened
  2026-11-06): `run(until=10)` "will not process any events scheduled for time 10".
- SimPy "Shared Resources" guide,
  https://simpy.readthedocs.io/en/latest/topical_guides/resources.html (opened 2026-11-06):
  `Resource`, `PriorityResource`, `PreemptiveResource`, `Container`, `Store`.
- salabim on PyPI, https://pypi.org/project/salabim/ (opened 2026-11-06), and repository,
  https://github.com/salabim/salabim (opened 2026-11-06): features, MIT.
- Ciw on PyPI, https://pypi.org/project/Ciw/ (opened 2026-11-06), and documentation,
  https://ciw.readthedocs.io/en/latest/ (opened 2026-11-06): features, tested Python
  versions.
- PyPI JSON API, `https://pypi.org/pypi/<name>/json` for simpy, salabim and ciw (read
  2026-11-06): release dates and Requires-Python.
- Installed wheels' licence files and source (`simpy/core.py`, `simpy/events.py`,
  `simpy/resources/base.py`, `ciw/auxiliary.py`, `ciw/dists/distributions.py`), read
  2026-11-06.

## Decision

SimPy stays the process engine (spec 2 summary unchanged), because it is the fastest of the
three on the benchmark case, accepts spec 1's per-component numpy streams, has the
primitives every spec 2 block needs (M4 confirms the rest), has no dependencies and is MIT;
spec 2's "Simultaneous events" rule is amended to SimPy's tested ordering.

## Tested

Scratch virtual environments outside the repository, 2026-11-06, Linux x86_64, 4 cores:
Python 3.13.18 with simpy 4.1.2, salabim 26.0.9 (plus greenlet 3.5.6), Ciw 3.2.7, numpy
2.5.4; and Python 3.11.18 with simpy 4.1.2, numpy 2.4.6.

- **Licences.** `importlib.metadata` listed each wheel's licence file: SimPy
  `simpy-4.1.2.dist-info/licenses/LICENSE.rst` "The MIT License (MIT)"; salabim
  `salabim/LICENSE.txt` "The MIT License (MIT)"; Ciw
  `ciw-3.2.7.dist-info/licenses/LICENSE.txt` "The MIT License (MIT)".
- **Speed and correctness.** One script ran 100 replications of the spec 2 M/M/1 case
  (exponential interarrival mean 2 min, one server with exponential service mean 1.5 min,
  200 h with 10 h warm-up; wait counted for items whose service starts after warm-up),
  seeds 1000 to 1099, one process. SimPy and salabim used two numpy PCG64 streams per
  replication; Ciw used `ciw.seed(seed)`.

  | Library | Wall time | Mean wait (min) | Standard error | Within 3 SE of 4.500 |
  | --- | --- | --- | --- | --- |
  | SimPy (Python 3.13) | 4.71 s, rerun 5.01 s | 4.533 | 0.053 | yes |
  | SimPy (Python 3.11) | 5.42 s | 4.533 | 0.053 | yes |
  | salabim, yieldless (default) | 142.30 s | 4.533 | 0.053 | yes |
  | salabim, yield mode, 10 replications | 11.92 s | first three 4.583, 4.291, 4.395 | | |
  | Ciw | 8.93 s, rerun 8.97 s | 4.515 | 0.058 | yes |

  salabim's yieldless mode first failed with `ModuleNotFoundError: No module named
  'greenlet'`; it ran after installing greenlet. Turning off the resource monitor and
  naming customers did not help (11.56 s for 10 replications). `cProfile` of one
  replication: 4.29 s total, 2.93 s cumulative in `_check_overlapping_parameters` (29,577
  calls).
- **Simultaneous events (SimPy 4.1.2, Python 3.11).**
  - Three timeouts scheduled at t = 0, 1, 2, all due at t = 5: ran in scheduling order
    (`c@5, b@5, a@5`).
  - Three processes started together, each with a 1-unit timeout: ran `x, y, z`.
  - At t = 3, timeouts `early`, `spawner` and `late` were due (scheduled in that order at
    t = 0); `spawner` started a new process at t = 3. Order: `early, spawner,
    child-first-step, late`. The child, scheduled last, ran before `late`, because
    `Initialize` is `URGENT`.
  - FIFO `Resource` of capacity 1: B queued at t = 1, C arrived at t = 2 as A released. B
    started at 2, C at 3.
