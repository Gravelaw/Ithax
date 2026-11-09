# Template sources (spec 4, M10)

## Question

Spec 4 "Research before building", M10 · Template sources: which example problems may be
reused freely, with their expected answers? Spec 0 "Risks" adds that templates use
textbook-style problems written for this project, or sources whose licence permits reuse,
recorded per template. This note records, for each of the ten Phase 1 templates, where its
problem comes from, under what licence, and which expected values have a theory or
benchmark source.

## Finding

**What may be reused.** Copyright protects the expression of a problem (its wording, its
story, a table laid out by an author), not the idea, method or mathematical result behind
it: 17 U.S.C. § 102(b) excludes "any idea, procedure, process, system, method of
operation, concept, principle, or discovery", and the U.S. Copyright Office's Circular 31
and Compendium say the same of methods, systems and mere computations from a formula.
Other jurisdictions draw the same idea–expression line. So the formulas of queueing theory
(M/M/1, Erlang C, Little's law, the availability of an alternating renewal process) and
the published optimum of a linear program may be used with the project's own numbers and
words; a textbook's problem text and data may not, unless its licence says so. The free
online queueing texts cited by `spec-2-benchmark-sources.md` (Adan and Resing; Sztrik)
state no licence, so only their formulas are used, as for the benchmarks.

**Openly licensed problems found.** Two code collections hold small worked problems under
permissive licences:

- SimPy's documentation examples (bank renege, carwash, machine shop with breakdowns and a
  repairman, gas station) ship with SimPy, MIT licence (`License :: OSI Approved :: MIT
  License` in the installed 4.1.2's metadata; the licence recorded in `DECISIONS.md` at M2).
- PuLP's case studies (the beer distribution transport problem: two warehouses, five bars)
  ship with PuLP, MIT licence (the `LICENSE` file of `coin-or/pulp`, read 2026-11-09).

Neither is needed: each template's problem can be written for this project with a theory
or benchmark answer, which spec 0 prefers and which the template test can check exactly.
They remain the fallback if a later ticket wants a recognisable published problem.

**Per template.** Every problem is written for this project; its numbers are chosen so a
closed form or a spec 2 benchmark gives at least one expected value. The template's
`origin` and `licence` record it (spec 4 "Template package"); a template is the project's
own content, so its licence is the product's, `AGPL-3.0-only`.

| Template (`id`) | Problem and origin | Theory or benchmark answers | Ticket |
| --- | --- | --- | --- |
| Coffee shop queue (`coffee_shop`) | `examples/coffee_shop.json`, spec 1's verbatim example, written for the project: arrivals every 2 min, one till of 1.5 min, both exponential | M/M/1: wait 270 s, queue 2.25, utilization 0.75, cycle time 360 s, throughput 1/120 per s (Adan and Resing 4.3; benchmark `mm1`); Little's law: WIP 3.0; arrivals in the 190 h measured, 5,700. Exercise, two tills: Erlang C wait 162/11 s, utilization 0.375 (benchmark `machine_count`) | AKS-122 |
| Three-machine production line (`three_machine_line`) | `examples/three_machine_line.json` (written fresh at M1) extended with a `queue` of 10 places in front of the weld station | Flow conservation in a stable line with no loss: throughput 1/120 per s, utilizations λE(S)/c: weld 0.9, paint 0.5 (cut's includes blocked time and has no closed form); 2,400 arrivals in the 80 h measured. Waits and cycle time with a blocking buffer have no closed form: `recorded` | AKS-122 |
| Machine breakdowns (`machine_breakdowns`) | Written for the project: one machine, arrivals every 4 min, 2 min jobs, failing every 90 min on average and repaired in 10 min | Availability MTTF/(MTTF + MTTR) = 0.9 (alternating renewal; benchmark `failure`); utilization over available time λE(S)/A = 5/9; throughput 1/240 per s; 2,850 arrivals. Exercise, 5 min repairs: availability 90/95. Waits: `recorded` | AKS-122 |
| Clinic patient flow (`clinic_patient_flow`) | Written for the project: patients every 5 min, a branch sending 3 in 5 to 3 exam rooms and 2 in 5 to 3 treatment rooms, every 8 min visit needing one of 2 nurses (a `resource_pool`) | Nurse utilization λE(S)/c = 0.8 (benchmark `resource_pool`); M/M/2 on the nurses: cycle time 4,000/3 s, WIP 40/9 (Erlang C, Little); room utilizations 0.32 and 0.2133 (branch split, benchmark `branch`'s rule); throughput 1/300 per s; 2,280 arrivals. Exercise, 3 nurses: M/M/3, utilization 8/15, cycle time 573.87 s, WIP 1.9129. Per-room waits: `recorded` | AKS-139 |
| Warehouse pick and pack (`warehouse_pick_pack`) | Written for the project, fresh rather than extending `examples/warehouse.json` (see below): orders every minute onto carts of 5, pickers on day and night shifts, a 3 min transfer, unloading and packing | Cart wait (n − 1)/(2λ) = 120 s (benchmark `batch_unbatch`); scheduled fraction 7/9 from the shift table; throughput 1/60 per s and packer utilization 0.5 by flow conservation over whole days; 11,520 arrivals. Exercise, 2 pickers overnight: scheduled fraction 8/9. Pickers' utilization and waits: `recorded` | AKS-139 |
| Inventory reorder point (`inventory_reorder_point`) | Written for the project: a shop selling a spare part, 4 a day at random, reordering 50 at a reorder point of 20 with a 5-day lead time | The (R, Q) policy with Poisson demand (Zipkin 6.2; Axsäter 5.3): stock mean 25.588, stock-outs 135.03 in 950 days, waiting customers 0.088181, cycle time 1,904.7 s; orders λ/Q; throughput λ; 3,800 arrivals. Exercise, reorder point 30: stock mean 35.501 (theory); stock-outs `recorded` (theory 2.4414, too rare for 30 replications) | AKS-139 |
| Product mix (`product_mix`) | Spec 2's product mix (chairs and tables), written for the project by the review council; the idea of a two-product LP is Hillier and Lieberman's prototype, but no number or wording of theirs is used | Optimum 24 chairs, 14 tables, profit 2,200, by vertex enumeration (benchmark `product_mix`) | AKS-140 |
| Transport plan (`transport_plan`) | To be written for the project with the indexed layout (supply points to demand points); PuLP's MIT-licensed beer distribution problem is the fallback | Optimum verified by enumeration of the basic solutions or by hand, and the spec 2 transport benchmark of the same ticket | AKS-123 |
| Staff rota (`staff_rota`) | To be written for the project: staff on five-consecutive-day patterns covering daily needs (the classic pattern of Winston's post office problem; the idea only, not its numbers) | Optimum verified by enumeration (small enough to list every pattern count) | AKS-140 |
| How many machines? (`how_many_machines`) | The coffee shop with `tills` searched, as `benchmarks/machine_count` (spec 2) | Erlang C: best `tills` 2, wait 162/11 s at utilization 0.375 (benchmark `machine_count`) | AKS-140 |

The ids above are proposed for the later tickets, which may refine the problems; the
licence rule does not change: written for the project, `AGPL-3.0-only`, or a source whose
licence permits reuse, recorded in `template.json`.

**The answers of the templates**, recomputed (AKS-122 for the first three, AKS-139 for the next three):

- Coffee shop: λ = 1/120 per s, E(S) = 90 s, ρ = 0.75. E(W) = (ρ/μ)/(1 − ρ) = 270 s;
  E(Lq) = ρ²/(1 − ρ) = 2.25; E(T) = 360 s; Little: L = λE(T) = 3.0. The experiment's
  `length` 200 h includes its 10 h warm-up (spec 1 "Experiments"; M7 item 25), so 190 h are
  measured and λ × 190 h = 5,700 customers. Two tills: c = 2, ρ = 0.375, Erlang C
  Π_W = 0.20455, E(W) = Π_W/(cμ − λ) = 162/11 s = 14.727 s, E(Lq) = λE(W) = 0.12273.
- Three-machine line: λ = 1/120 per s; weld E(S) = 108 s, paint 60 s; ρ = 0.9 and 0.5.
  The `queue` blocks rather than discards (its default `on_full`), cut's own queue is
  unlimited and the source feeds cut, so no item is lost and, while the line is stable,
  every station passes λ: throughput 1/120 per s; 80 h measured (100 h with 20 h of
  warm-up), 2,400 arrivals. With a buffer of 3 (the exercise) the line is still stable
  (cut utilization 0.895 below 1, measured), so the same flow answers hold.
- Machine breakdowns: MTTF 5,400 s, MTTR 600 s, A = 0.9; λE(S) = 120/240 = 0.5 of calendar
  time is work, and work is done only while the machine is available (preempt–resume keeps
  the work of a suspended job, spec 2 "Failure"), so utilization over available time is
  0.5/0.9 = 5/9 = 0.5556; throughput 1/240 per s; 190 h measured, 2,850 arrivals. Five-
  minute repairs: A = 5,400/5,700 = 18/19 = 0.94737, utilization 0.5 × 19/18 = 0.52778.
- Clinic patient flow: λ = 1/300 per s, E(S) = 480 s for either visit, a = λE(S) = 1.6, c = 2
  nurses, ρ = 0.8. Every visit holds a room and a nurse (spec 2 "Pool"); each kind of room
  has 3 places, at least the number of nurses, so an item waiting for a room means all 3
  of that kind are held, each in service or asking for a nurse, and the nurses are never
  idle while anyone waits. With the same exponential service for both visits the number in
  the clinic is then the M/M/2 birth–death process whatever the order of service: Erlang C
  Π_W = (a²/2)/(1 − ρ) / (1 + a + (a²/2)/(1 − ρ)) = 6.4/9 = 32/45, E(W) = Π_W/(cμ − λ) =
  (32/45) × 1,200 s = 2,560/3 s, cycle time E(W) + E(S) = 4,000/3 s, L = λ × 4,000/3 = 40/9.
  Rooms are busy only in service: exam 0.6 × 1.6/3 = 0.32, treatment 0.4 × 1.6/3 = 0.2133.
  The waits per kind of room have no closed form: a check-up that finds the 3 exam rooms
  taken waits for a room while dressings go ahead. Three nurses (the exercise; rooms still
  3 ≥ 3): ρ = 8/15, Π_W = 0.27380, E(W) = Π_W/(3/480 − 1/300) = 93.873 s, cycle time
  573.87 s, L = 1.9129.
- Warehouse pick and pack: λ = 1/60 per s into carts of n = 5, so a cart's orders wait
  (n − 1)/(2λ) = 120 s (the pickers' queue always accepts, so a cart leaves as it fills).
  Shifts: 1 picker from 0 h to 6 h and from 22 h to 24 h, 3 from 6 h to 22 h, so
  1 × 8 + 3 × 16 = 56 picker-hours of 3 × 24 = 72: scheduled fraction 7/9 in every whole day
  (8/9 with 2 overnight). Over whole days the backlog that builds overnight (6.7 carts an
  hour against 12) is cleared by day (20 an hour), so the system is periodic and every
  order is dispatched: throughput 1/60 per s, packer utilization λ × 30 s = 0.5, and
  192 h measured give 11,520 arrivals. The offered picking work, 12 carts an hour × 9 min =
  43.2 picker-hours a day over 56 available, is 0.7714, but spec 2 counts no busy time
  above the available capacity, so a cart finished after the evening shift change adds
  only part of its time, and the measured utilization (0.7694) is `recorded`. The model is
  written fresh rather than extending `examples/warehouse.json`: picking by cart makes a
  cart the picker's unit, the example's branch is not among spec 4's blocks for this
  template, and a schedule on the example's pickers would make the orders reaching a
  batch after them non-Poisson, leaving the batch wait without a closed form.
- Inventory reorder point: demand λ = 4 a day, lead time L = 5 d, so D ~ Poisson(20); R = 20,
  Q = 50. With at most one order outstanding (P(D ≥ 50) = 1.2 × 10⁻⁸) the store is the (R, Q)
  policy with backorders (spec 2 "Store"): the position is uniform on 21 to 70, net stock
  NI = IP − D. A customer finds no stock (PASTA) with probability (1/Q)Σ_{y=21}^{70}
  P(D ≥ y) = 0.035534, so 4 × 950 × 0.035534 = 135.03 stock-outs in the 950 days measured;
  mean stock (1/Q)Σ E[(y − D)⁺] = 25.588; mean net stock R + (Q + 1)/2 − λL = 25.5, so
  0.088181 customers wait on average and, by Little's law, the mean cycle time is
  0.088181/λ = 1,904.7 s; orders λ/Q, one every 12.5 days. Reorder point 30 (the
  exercise): P = 0.00064248, stock-outs 2.4414, mean stock 35.501.

## Sources

- 17 U.S.C. § 102, <https://www.govinfo.gov/content/pkg/USCODE-2018-title17/html/USCODE-2018-title17-chap1-sec102.htm>.
- U.S. Copyright Office, Circular 31 "Ideas, Methods, or Systems" (archived copy),
  <https://webarchive.library.unt.edu/eot2008/20090101091118/http:/www.copyright.gov/circs/circ31.html>;
  Compendium II, chapter 200, <https://ipmall.law.unh.edu/node/52>.
- SimPy 4.1.2 machine shop example, <https://simpy.readthedocs.io/en/4.1.2/_sources/examples/machine_shop.rst.txt>;
  licence from the installed package's metadata (MIT).
- PuLP, "A Transportation Problem", <https://www.coin-or.org/PuLP/CaseStudies/a_transportation_problem.html>;
  licence <https://raw.githubusercontent.com/coin-or/pulp/master/LICENSE> (MIT, read 2026-11-09).
- I. Adan, J. Resing, *Queueing Systems* (2015), sections 3.4, 4.3 and 5.1 to 5.2, as cited
  in `docs/research/spec-2-benchmark-sources.md`; Wikipedia, "Availability" (MTTF/(MTTF +
  MTTR)), as cited there.
- `docs/research/spec-2-benchmark-sources.md` (the benchmark answers and their derivations).
- P. H. Zipkin, *Foundations of Inventory Management* (2000), section 6.2 (the (r, q)
  policy with Poisson demand and a constant lead time: the inventory position uniform on
  r + 1, ..., r + q and the net inventory the position less the lead-time demand); S.
  Axsäter, *Inventory Control*, 3rd edition (2015), section 5.3 (the same result). Only the
  formulas are used; the book's examples were not.
- I. Adan, J. Resing, *Queueing Systems* (2015), equations (5.1) and (5.3) (Erlang C), as
  cited in `docs/research/spec-2-benchmark-sources.md`, for the clinic.

## Decision

- Every Phase 1 template's problem is written for this project, with the project's own
  numbers and words; its `template.json` records `origin` (where the problem comes from)
  and `licence` (`AGPL-3.0-only`, the product's). A template that ever reuses outside
  content records that source and its licence instead, and only a licence that permits
  reuse is accepted (spec 0 "Risks"; owner to confirm).
- Each simulation template's `expected.json` has at least one `theory` row (a closed form,
  cited) or `benchmark` row (a `benchmarks/<case>` id); values with no closed form are
  `recorded` regression rows (spec 4 "Template package").
- The ids and problems of the seven later templates in the table were proposals for
  AKS-139, AKS-123 and AKS-140; AKS-139 kept its three ids and wrote the problems above
  (owner to confirm), and the other four remain proposals for AKS-123 and AKS-140.

## Tested

The three AKS-122 templates were run at their files' seed 12345 (SimPy adapter, 30
replications) on 2026-11-09, and every `theory` and `benchmark` value above lay within 3
standard errors of the estimate (`tests/templates/test_templates.py`), the template run
and the exercise run alike: for example the coffee shop's wait 267.6 s (−0.50 standard
errors from 270 s) and arrivals 5,683 (−1.22 from 5,700), the line's weld utilization
0.901 (+0.19), and the breakdowns' availability 0.8986 (−0.73 from 0.9).

AKS-139 wrote the next three (clinic patient flow, warehouse pick and pack, inventory
reorder point) the same way and ran each at its file's seed 12345 (30 replications) on
2026-11-09; every `theory` and `benchmark` row lies within 3 standard errors, the template
run and the exercise run alike. Largest deviations: the clinic's treatment-room
utilization 0.2146 (+0.80 from 0.2133) and the exercise's cycle time 574.8 s (+0.24 from
573.87 s); the warehouse's cart wait 120.23 s (+0.90 from 120 s) and its exercise's
throughput (−0.60); the inventory's stock mean 25.602 (+0.21 from 25.588), stock-outs
132.87 (−0.35 from 135.03), cycle time 1,847 s (−0.51 from 1,904.7 s) and the exercise's
stock mean 35.445 (−0.81 from 35.501). Two values were checked and not used as theory:
the warehouse pickers' utilization 0.7694 (−0.53 from the offered 0.7714, which spec 2's
counting of busy time does not reach exactly) and the exercise's stock-outs, 1.2 against
2.4414 (−3.65 standard errors: rare, bunched counts, whose standard error 30 replications
underestimate; 400 replications at seed 777 gave 2.505 plus or minus 0.296, +0.42). The
clinic's Erlang C values and the inventory's (R, Q) values are recomputed from their
formulas by `tests/templates/test_templates.py`.
