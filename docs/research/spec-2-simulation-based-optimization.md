# Simulation-based optimization (spec 2, M5)

## Question

Spec 2 "Research before building", M5: "Simulation-based optimization. Ranking-and-selection
and Bayesian methods from the simulation literature. Record which ranking-and-selection
procedure, if any, replaces the fixed top-three confirmation." Spec 2 "Simulation-based
optimization" proposes:

- **Search.** Every integer combination is run when there are at most `budget` of them;
  otherwise Optuna's TPE sampler proposes candidates, "seeded from the spec 1 stream key
  `<seed>:0:optimizer` … so a search repeats exactly".
- **Confirmation.** The baseline and the best three candidates by search-stage mean among
  those feasible at the search stage are re-run with the experiment's full `replications`;
  constraints are re-judged on the confirmed means; the best confirmed feasible candidate is
  reported, with whether it is separated from the confirmed runner-up by a paired interval.

The search (AKS-109) also needs four facts about Optuna before it is built: how
`TPESampler(seed=...)` is seeded and how to derive that seed from the spec 1 stream; whether
a seeded study repeats exactly across runs and processes; how integer parameters are
suggested and whether points already tried are suggested again, and what to do about that
under a fixed budget; and what logging to silence.

## Finding

### Ranking and selection, and Bayesian allocation

Hong and Nelson (2009) sort optimization via simulation by the size of the solution set and
treat the first category, "a small number of solutions (often less than 100)", with
ranking-and-selection (R&S) procedures that select the solution with the best mean. Their
summary of the frequentist side:

| Procedure | What it assumes and does | Parameters the user must give |
| --- | --- | --- |
| Bechhofer (1954) | Known, equal variances; one stage of n = ⌈2h²σ²/δ²⌉ observations per solution, then the best sample mean | δ, 1 − α |
| Rinott (1978) | Unknown, unequal variances; a two-stage procedure, whose first stage samples each solution to estimate the variances | n₀, δ, 1 − α |
| Nelson and Matejcik (1995) | As Rinott, with common random numbers | n₀, δ, 1 − α |
| NSGS, Nelson, Swann, Goldsman and Song (2001) | Adds a screening step after the first stage, so clearly inferior solutions skip the second stage | n₀, δ, 1 − α |
| KN, Kim and Nelson (2001) | Fully sequential: one observation at a time from each surviving solution, eliminating the apparently inferior early; unknown, unequal variances; allows common random numbers; assumes normal data, with batching discussed | n₀, δ, 1 − α |

Each guarantees, for an indifference-zone parameter δ > 0 ("often set as the smallest
difference that is practically significant"), that the best solution is selected with
probability at least 1 − α whenever it is at least δ better than the second best (Hong and
Nelson, equation 2). On the Bayesian side, Hong and Nelson name two streams: optimal
computing budget allocation (OCBA, Chen, Lin, Yücesan and Chick 2000), which allocates the
simulation budget "to maximize the posterior probability of correct selection", and expected
value of information (Chick and Inoue 2001), which minimises the expected opportunity cost of
the choice. Branke, Chick and Schmidt (2007) compared many selection procedures on normal,
independent samples; Hong and Nelson report that they "found that no R&S procedure can
dominate in all situations" and that the Bayesian procedures, though often needing fewer
samples, "do not provide the type of correct selection guarantees that the frequentist
procedures provide".

**After a search.** Boesel, Nelson and Kim (2003) address exactly the step spec 2 calls
confirmation: after a heuristic search, "the system with the best sample mean at the end
of the search procedure may not coincide with the true best system encountered during the
search". Their "clean-up" procedure first screens the systems already sampled with a
subset-selection step "which use[s] only the data already collected", then applies an
indifference-zone procedure with more simulation to the survivors, returning the best
system encountered (or one within δ of it) with a set probability. Hong and Nelson (section
5.3) recommend this as practice: "there is a natural bias toward solutions that, by chance,
received favorable simulation samples", so "the top 5 to 10% of the solutions simulated
during the search should be subjected to this controlled experiment".

**Constraints.** Spec 2's search has constraints on simulated means (the machine-count case
has `till.utilization >= 0.35`). The R&S procedures above select on one mean. Batur and Kim
(2010) give separate procedures for "finding a set of feasible or near-feasible systems …
in the presence of constraints on secondary performance measures", which a guaranteed
selection with constraints would have to add.

**What this means for spec 2's confirmation.** Spec 2's stage is a clean-up in Boesel,
Nelson and Kim's sense without the guarantee: it re-runs a fixed short list with more
replications, keeps common random numbers (spec 1 "Random streams"), re-judges constraints,
and states whether the best is separated from the runner-up. Its size, three candidates
plus the baseline, is 6 to 8% of a default budget of 50, inside Hong and Nelson's 5 to 10%;
for small budgets it is a larger share (four of the five machine-count candidates).

The confirmation replications are not fresh, though. A stream's key is
`<seed>:<replication>:<component id>` (spec 1 "Random streams";
`generator_for` in `src/lcsim/model/streams.py`), and the process adapter numbers a run's
replications from 0 (`range(replications)` in `src/lcsim/engines/process/runner.py`). Spec 2
runs both stages with the experiment seed, so a candidate's first `search.replications`
confirmation replications are exactly its search-stage replications, and only the rest are
new: with the defaults (`search.replications` 10, `replications` 30), 10 of the 30 confirmed
values are the ones that selected the candidate. The confirmed mean dilutes the search
stage's selection bias, the "natural bias toward solutions that, by chance, received
favorable simulation samples" of Hong and Nelson, but does not remove it; with equal
counts it would repeat the search-stage means exactly. Boesel, Nelson and Kim's
second-stage sampling, which takes additional observations, avoids this. Disjoint
confirmation replications would too: numbering them from `search.replications` (keys
`<seed>:<search.replications + k>:<component id>` for k = 0 to `replications` − 1) keeps
common random numbers across the confirmed candidates, since all of them would still share
each key, while the confirmed means use only replications the search never saw. Replacing it
with KN, Rinott or NSGS would add δ and 1 − α to the `search` object (spec 1
"Experiments"), make the number of confirmation runs random, and still need a feasibility
procedure for the constraints; OCBA would replace the fixed `search.replications` with an
allocation rule and give no guarantee.

### Bayesian optimization in Optuna

Optuna's `TPESampler` docstring sends readers "for further information about TPE algorithm"
first to Bergstra, Bardenet, Bengio and Kégl (2011), whose abstract presents "two new greedy
sequential methods based on the expected improvement criterion", and to Watanabe (2023), an
ablation study of the estimator's components.
For constraints it cites Watanabe and Hutter (2022, c-TPE) and notes that "the Optuna
algorithm differs from the one proposed" there. Optuna (Akiba et al. 2019) also offers a
Gaussian-process sampler, `GPSampler`; on 3.13.18 with Optuna 5.0.0 it failed with
`ModuleNotFoundError: No module named 'torch'`, so it would add PyTorch as a dependency.

### Optuna 5.0.0, observed

All observations: Optuna 5.0.0 in scratch venvs on Python 3.11.18 (numpy 2.4.6) and 3.13.18
(numpy 2.5.4), 2026-11-07. Scripts and outputs are in Tested.

**Seeding.** `TPESampler(seed=s)` keeps a `LazyRandomState(s)`, which calls
`numpy.random.RandomState().seed(seed=s)`, and builds its start-up `RandomSampler(seed=s)`
the same way (`optuna/samplers/_tpe/sampler.py`, `_lazy_random_state.py`, read in the
wheel). `RandomState.seed` accepts 0 to 2³² − 1: 4294967295 is accepted, 4294967296 and −1
raise `ValueError: Seed must be between 0 and 2**32 - 1`. So the 256-bit SHA-256 entropy of
the spec 1 stream key cannot be passed directly. With `n_jobs` other than 1,
`Study.optimize` calls `sampler.reseed_rng()`, which reseeds from the operating system
(`optuna/study/_optimize.py`); the Optuna FAQ says parallel optimization has "inherent
non-determinism" and recommends "executing optimization of a study sequentially if you
would like to reproduce the result".

**The recipe that was tested.** `tpe_seed = int(optimizer_generator(seed).integers(0,
2**32))`, where `optimizer_generator` is `src/lcsim/model/streams.py`'s generator of the key
`<seed>:0:optimizer` (SHA-256 → `SeedSequence` → PCG64). For seed 12345 it gives
3441887045, both from the repository's own `optimizer_generator` and from a copy of the
recipe in the scratch script.

**Repeat.** With that seed, the ask-and-tell loop below gave the same trial sequence:

- in two studies run one after the other in one process;
- in separate processes, with `PYTHONHASHSEED` 1, 2, 11, 22 and 33;
- on Python 3.11.18 with numpy 2.4.6 and on 3.13.18 with numpy 2.5.4;
- with constraints given by `Trial.set_constraint`, by the deprecated `constraints_func`,
  or not at all (for the one-variable case, where all trials fall in the random start-up).

It did **not** repeat across Optuna versions. On the two-variable case (budget 30, seed
12345, no constraints) Optuna 4.0.0 and 4.5.0 gave one sequence (47 asks), 4.9.0 another
(61 asks) and 5.0.0 a third (41 asks), all from the same `tpe_seed`. The one-variable
machine-count case, whose few trials all fall in the random start-up phase, gave the same
sequence on all four versions. Optuna 5.0.0's release notes say "TPESampler now enables
multivariate TPE" for single-objective studies, one change of this kind. Spec 1 "Identical
runs" already limits identity to "the same machine, Python and library versions", so this
does not contradict spec 2; it means the Optuna version is part of what makes a search
repeat.

**Integer parameters and repeats.** `trial.suggest_int(name, low, high)` (`step` 1, `log`
False by default) suggests whole numbers in [low, high]. TPE does suggest points already
tried; the Optuna FAQ says so ("Optuna may sometimes suggest parameters evaluated in the
past") and its workaround returns the existing value. Counted here, asking until `budget`
distinct candidates were seen, the baseline enqueued first:

| Case | Asks for the distinct candidates | Repeats |
| --- | --- | --- |
| `tills` 1 to 5, budget 3, seed 12345 | 4 (1, 1, 2, 4) | 1 |
| `tills` 1 to 5, budget 4, seed 7 | 6 (1, 5, 5, 3, 3, 4) | 2 |
| Two variables 1 to 10, budget 30, seed 12345, no constraint | 41 | 11 |
| The same with one constraint (`set_constraint`) | 36 | 6 |
| Two variables 1 to 10, budget 50, seed 99, one constraint | 88 | 38 |

TPE's first `n_startup_trials` (default 10) trials come from its seeded `RandomSampler`, so
a search of budget 10 or less never uses the Parzen model at all: with budget 3, the
machine-count test's Optuna path is seeded random sampling.

**Constraints.** In 5.0.0 the sampler argument `constraints_func` emits `FutureWarning:
`constraints_func` has been deprecated in v5.0.0. This feature will be removed in v7.0.0.
… Use `optuna.trial.Trial.set_constraint` instead.` `Trial.set_constraint(key, value)`
(new in 5.0.0, release notes "Add `set_constraint` method to `Trial`") records a value
that is feasible when "zero or less", and TPE reads it from `trial.constraints` (the
constraint changed the two-variable sequence above). It rejects NaN (`ValueError:
Attempted to set a constraint for 'c', but NaN is not allowed.`) and accepts `math.inf`.
Optuna 4.0.0, 4.5.0 and 4.9.0 have no `set_constraint` (`AttributeError`).

**NaN objective.** `study.tell(trial, math.nan)` emits `UserWarning: The value nan is not
acceptable` and stores the trial as `FAIL`. `study.tell(trial,
state=optuna.trial.TrialState.FAIL)`, after `set_constraint(..., math.inf)`, raised no
warning (run with `-W error` on both Pythons, seed 2³² − 1, `direction="maximize"`).

**Logging.** On creating a study Optuna logs one INFO line to standard error, `[I …] A new
study created in memory with name: no-name-<uuid>`; the Optuna FAQ: "By default, Optuna shows
log messages at the `optuna.logging.INFO` level." `optuna.logging.set_verbosity(optuna.logging.WARNING)`
before creating the study removed it (0 lines on standard error). With the recipe below
(no `constraints_func`, no NaN told) no warning was raised; the two-variable script ran with
`warnings.simplefilter("error")`.

## Sources

- L. Jeff Hong and Barry L. Nelson, "A brief introduction to optimization via simulation",
  Proceedings of the 2009 Winter Simulation Conference, pp. 75–85,
  DOI 10.1109/WSC.2009.5429321; PDF https://www.informs-sim.org/wsc09papers/008.pdf (opened
  2026-11-07): section 1 (the small-number category), section 2 (R&S, equation 2, Bechhofer,
  Rinott, Nelson and Matejcik, NSGS, KN, OCBA, EVI, Branke et al.), section 5.3 (clean-up).
- Seong-Hee Kim and Barry L. Nelson, "A fully sequential procedure for indifference-zone
  selection in simulation", ACM TOMACS 11(3), 2001, pp. 251–273, DOI 10.1145/502109.502111
  (abstract read through the Crossref API, 2026-11-07).
- Yosef Rinott, "On two-stage selection procedures and related probability-inequalities",
  Communications in Statistics – Theory and Methods 7(8), 1978, pp. 799–811,
  DOI 10.1080/03610927808827671 (Crossref record, 2026-11-07; content as Hong and Nelson
  describe it).
- Barry L. Nelson, Julie Swann, David Goldsman and Wheyming Song, "Simple procedures for
  selecting the best simulated system when the number of alternatives is large", Operations
  Research 49(6), 2001, pp. 950–963, DOI 10.1287/opre.49.6.950.10019 (abstract via Crossref,
  2026-11-07).
- Chun-Hung Chen, Jianwu Lin, Enver Yücesan and Stephen E. Chick, "Simulation budget
  allocation for further enhancing the efficiency of ordinal optimization", Discrete Event
  Dynamic Systems 10(3), 2000, pp. 251–270, DOI 10.1023/A:1008349927281 (Crossref record,
  2026-11-07; content as Hong and Nelson describe it).
- Stephen E. Chick and Koichiro Inoue, "New two-stage and sequential procedures for
  selecting the best simulated system", Operations Research 49(5), 2001, pp. 732–743,
  DOI 10.1287/opre.49.5.732.10615 (abstract via Crossref, 2026-11-07).
- Jürgen Branke, Stephen E. Chick and Christian Schmidt, "Selecting a selection procedure",
  Management Science 53(12), 2007, pp. 1916–1932, DOI 10.1287/mnsc.1070.0721 (abstract via
  Crossref, 2026-11-07).
- Justin Boesel, Barry L. Nelson and Seong-Hee Kim, "Using ranking and selection to 'clean
  up' after simulation optimization", Operations Research 51(5), 2003, pp. 814–825,
  DOI 10.1287/opre.51.5.814.16751 (abstract via Crossref, 2026-11-07).
- Demet Batur and Seong-Hee Kim, "Finding feasible systems in the presence of constraints on
  multiple performance measures", ACM TOMACS 20(3), 2010, DOI 10.1145/1842713.1842716
  (abstract via Crossref, 2026-11-07).
- James Bergstra, Rémi Bardenet, Yoshua Bengio and Balázs Kégl, "Algorithms for
  hyper-parameter optimization", NIPS 24, 2011,
  https://papers.nips.cc/paper/2011/hash/86e8f7ab32cfd12577bc2619bc635690-Abstract.html
  (opened 2026-11-07).
- Shuhei Watanabe, "Tree-structured Parzen estimator: understanding its algorithm components
  and their roles for better empirical performance", arXiv:2304.11127, 2023,
  https://arxiv.org/abs/2304.11127 (opened 2026-11-07).
- Shuhei Watanabe and Frank Hutter, "c-TPE: tree-structured Parzen estimator with
  inequality constraints for expensive hyperparameter optimization", arXiv:2211.14411, 2022,
  https://arxiv.org/abs/2211.14411 (opened 2026-11-07).
- Takuya Akiba, Shotaro Sano, Toshihiko Yanase, Takeru Ohta and Masanori Koyama, "Optuna",
  Proceedings of the 25th ACM SIGKDD Conference (KDD 2019), pp. 2623–2631,
  DOI 10.1145/3292500.3330701 (Crossref record, 2026-11-07).
- Optuna FAQ, https://optuna.readthedocs.io/en/stable/faq.html (opened 2026-11-07):
  reproducibility, duplicated parameters, log levels.
- Optuna v5.0.0 release notes, https://github.com/optuna/optuna/releases/tag/v5.0.0 (opened
  2026-11-07): `constraints_func` deprecated, `Trial.set_constraint` added, multivariate TPE
  by default.
- Optuna 5.0.0 source in the wheel: `optuna/samplers/_tpe/sampler.py`,
  `optuna/samplers/_lazy_random_state.py`, `optuna/samplers/_random.py`,
  `optuna/study/_optimize.py`, `optuna/trial/_trial.py`.

## Decision

- **No ranking-and-selection procedure replaces the fixed top-three confirmation in Phase
  1.** Spec 2's confirmation stays as written. It is the clean-up step the literature
  recommends (Boesel, Nelson and Kim; Hong and Nelson 5.3), sized within Hong and Nelson's
  5 to 10% at the default budget, and it needs no new user setting. KN, Rinott and NSGS
  would add an indifference zone δ and a probability 1 − α to `search`, make the run count
  random, and still not handle the constraints without a further feasibility procedure
  (Batur and Kim); OCBA and other Bayesian allocations give no correct-selection guarantee.
  The M5 tests do not need any of them: the machine-count case has five candidates whose
  confirmed means are far apart (4.500, 0.245 min and three infeasible), and its Optuna path
  checks only feasibility and repeatability. Recorded for Phase 2 (owner to confirm): KN
  with common random numbers, plus Batur and Kim's feasibility check, as the candidate if a
  guaranteed selection is wanted.
- **Overlap of the two stages** (found in review of PR #30). As spec 2 is written, the
  confirmation re-runs replications 0 to `replications` − 1 with the experiment seed, so its
  first `search.replications` values are the search stage's own, and the confirmed means
  keep part of the search's selection bias. AKS-109 builds the spec as written (simplest
  reading) and the overlap is put to the owner: numbering the confirmation replications from
  `search.replications` would make them disjoint while keeping common random numbers across
  the confirmed candidates. Choosing it is a spec 2 change (and a line in spec 1 "Random
  streams"), owner to decide. Neither machine-count assertion depends on it: the theory
  values are far apart, and the Optuna path checks only feasibility and repeatability.
- **Optuna's TPE sampler stays** as the search driver; `GPSampler` is not used (it needs
  PyTorch).
- **The seeding recipe for AKS-109**, exactly:
  1. `optuna.logging.set_verbosity(optuna.logging.WARNING)` once, before the study is made.
  2. `tpe_seed = int(lcsim.model.streams.optimizer_generator(experiment_seed).integers(0, 2**32))`:
     one draw, the first from the key `<seed>:0:optimizer`, in [0, 2³² − 1]. Nothing else
     draws from that stream.
  3. `sampler = optuna.samplers.TPESampler(seed=tpe_seed)`, every other argument at its
     default (no `constraints_func`).
  4. `study = optuna.create_study(direction=<"minimize" or "maximize", from the objective's
     sense>, sampler=sampler)`, in memory (no `storage`).
  5. `study.enqueue_trial(<baseline values of the search variables>)`, so the baseline is
     trial 0.
  6. Ask and tell, one trial at a time, never `n_jobs` and never `study.optimize` in
     parallel: `trial = study.ask()`; for each variable in `search.variables` order,
     `trial.suggest_int(<parameter id>, <min>, <max>)`; for each constraint,
     `trial.set_constraint(<constraint id>, <value − mean> for `>=`, <mean − value> for
     `<=`>)`, or `math.inf` when the search-stage mean is NaN; then `study.tell(trial,
     <search-stage mean objective>)`, or `study.tell(trial,
     state=optuna.trial.TrialState.FAIL)` when it is NaN.
  7. **Repeats.** A suggested combination already evaluated is not run again: the trial is
     given the stored search-stage results (its constraints and its objective) and told
     like a new one, and does not count against `budget`. Asking stops when `budget`
     distinct candidates, the baseline included, have been evaluated, or after 10 × `budget`
     asks, whichever comes first; a search stopped by the cap reports the candidates it has.
     Simplest reading of "Budget is a number of candidates" (spec 2) for a sampler that
     repeats; owner to confirm.
  8. A repeat is promised only on the same Optuna and numpy versions (spec 1 "Identical
     runs": same library versions); the Optuna version differs between sequences as
     observed. AKS-109 records the Optuna version with the run (spec 1's manifest has
     `engine` and `generator` fields; where it goes is AKS-109's choice).
- **Lower bound** `optuna>=5.0.0`, for `Trial.set_constraint` without a deprecated
  argument (`docs/research/spec-2-solver-layer.md`).
- **Spec changes:** none. Each finding fits spec 2 as written: TPE seeded from the stream key
  repeats on the same versions, which spec 1 "Identical runs" requires; the confirmation
  stage stays. The recipe and the repeat rule above are the simplest readings for AKS-109,
  which writes them into spec 2 "Simulation-based optimization" when it builds the search,
  owner to confirm.

## Tested

Run on 2026-11-07 in scratch venvs outside the repository, Optuna 5.0.0 unless stated;
nothing was added to `src/`. The objective is the closed-form M/M/c wait of the coffee shop
(no simulation), so that only Optuna's behaviour varies.

```python
import hashlib, math, numpy, optuna
from math import factorial

optuna.logging.set_verbosity(optuna.logging.WARNING)


def optimizer_generator(seed):  # the spec 1 recipe, as in src/lcsim/model/streams.py
    key = f"{seed}:0:optimizer"
    entropy = int.from_bytes(hashlib.sha256(key.encode("utf-8")).digest(), "big")
    return numpy.random.Generator(numpy.random.PCG64(numpy.random.SeedSequence(entropy)))


def mmc(c, lam=0.5, mu=1 / 1.5):  # coffee shop: Erlang C wait in minutes, utilization
    rho, a = lam / (c * mu), lam / mu
    top = a**c / factorial(c)
    pw = top / ((1 - rho) * sum(a**n / factorial(n) for n in range(c)) + top)
    return pw / (1 - rho) / (c * mu), rho


seed, budget = 12345, 3
tpe_seed = int(optimizer_generator(seed).integers(0, 2**32))
study = optuna.create_study(direction="minimize", sampler=optuna.samplers.TPESampler(seed=tpe_seed))
study.enqueue_trial({"tills": 1})  # the baseline
seen, seq, asks = {}, [], 0
while len(seen) < budget and asks < 10 * budget:
    t = study.ask()
    asks += 1
    c = t.suggest_int("tills", 1, 5)
    wq, rho = mmc(c)
    t.set_constraint("utilization", 0.35 - rho)  # feasible when <= 0
    seq.append([t.number, c, c in seen])
    seen.setdefault(c, wq)
    study.tell(t, wq)
print(tpe_seed, asks, seq, sorted(seen))
```

Output, the same in every run listed under "Repeat" (Python 3.11.18 and 3.13.18; process
`PYTHONHASHSEED` 1, 2, 11, 22, 33; constraint modes `set_constraint`, `constraints_func`
and none):

```text
3441887045 4 [[0, 1, False], [1, 1, True], [2, 2, False], [3, 4, False]] [1, 2, 4]
```

The two-variable script used the same loop with `a`, `b` in 1 to 10, objective
(a − 3)² + (b − 8)² + 0.1ab, optional constraint `4 − a`, baseline (5, 5), and printed a
SHA-256 prefix of the trial sequence: `48d77549d4842267` (with the constraint) and
`c4cbcd270f6a8b84` (without) on Optuna 5.0.0 in every process, on both Pythons, and twice
in one process; `76d647688e54eb9a` on 4.0.0 and 4.5.0 and `a1a89633a8dfde30` on 4.9.0
(without; those versions have no `set_constraint`). In every run the best feasible point
found was (4, 8) on 5.0.0 and (4, 7) on 4.x.

Seed range: `numpy.random.RandomState().seed(2**32 - 1)` succeeded; `seed(2**32)` and
`seed(-1)` raised `ValueError: Seed must be between 0 and 2**32 - 1`.
