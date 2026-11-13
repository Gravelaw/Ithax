# Simulation optimization literature, read for the Phase 1 review and specs 5 to 7

## Question

The owner shared two sources on 2026-11-11 and asked whether they answer any of the open decisions in the end-of-Phase-1 decision list (`Ithax-owner-decisions-final-2026-11-11.md`, Parts B, D and F). The owner also asked whether they inform the expansion of specs 5 to 7 and the work of Phase 2 to Phase 4.

The two sources:

1. Nanjing Jian and Shane G. Henderson, "An Introduction to Simulation Optimization", Introductory Tutorials, Winter Simulation Conference, 7 December 2015, Cornell University. Slides: https://people.orie.cornell.edu/shane/pubs/WSC2015TutSlides.pdf
2. Satyajith Amaran, Nikolaos V. Sahinidis, Bikram Sharda and Scott J. Bury, "Simulation optimization: a review of algorithms and applications", 4OR 12, 301–333 (2014); arXiv:1706.08591v1, 26 June 2017. https://arxiv.org/pdf/1706.08591

Both were read in full on 2026-11-11.

## Finding

### What the sources say

**Jian and Henderson (2015), the tutorial.**

- **Problems with noisy evaluation.**
  - Noise can swamp the signal. The remedies are to choose the run length so that differences are statistically significant, and to use common random numbers (CRN) from separate streams.
  - The best of several noisy estimates underestimates the true optimum ("Poor estimates of the optimal value"). The remedy is to "run a longer simulation using [an] independent sample (new random stream)" for the chosen solution.
  - Even if every point is visited, the optimum cannot be recognized for sure. The remedy is ranking and selection (R&S) as a "clean-up step after an initial search".
- **Ranking and selection.**
  - It suits a finite, "small" (under about 500) set of candidates.
  - Procedures that guarantee a probability of correct or good selection (PCS or PGS) within an indifference zone are "usually very conservative".
  - Optimal computing budget allocation (OCBA) and the expected value of perfect information are more efficient but give no guarantee.
  - Parallel R&S has handled about 10⁶ systems.
- **The five tool families:** sample average approximation (SAA), metamodelling or response-surface methodology, stochastic approximation with gradient estimation, R&S, and random search.
  - **SAA** fixes the random inputs, using CRN, so that the problem becomes a deterministic program for a deterministic optimizer. The example is staffing a call centre over 1,000 simulated days.
- **When to stop:** under a budget in practice. Alternatively, start with few replications and increase them while the solution settles.
- **"Model madness".** Do not build one huge model and then optimize it. Build a succession of models of rising fidelity; each answers part of the question and seeds the next. In the Citi Bike case study (about 330 stations, morning rush, Poisson demand that varies by station and destination), the succession is:
  1. half-full stations;
  2. a fluid model;
  3. a continuous-time Markov chain (CTMC);
  4. a discrete-event simulation (DES).
  
  Searching the DES from the CTMC solution went from 567 to 443 unhappy users. Searching from equal allocation went from 1,096 to 493.
- **The flaw of averages.** In the newsvendor example, replacing demand by its mean overstates the expected profit, by about 40% in the example shown.
- **Applications listed:** the newsvendor; portfolios (with expected-value and quantile, that is value-at-risk, objectives); (s, S) and order-up-to inventory; call-centre staffing; ambulance base locations.
- **Test problems:** SimOpt (simopt.org).
- **Takeaways:**
  - Simulation optimization is not easy.
  - Do not build one huge model.
  - With standard tools, keep to low-dimensional problems.
  - Use CRN with streams.

**Amaran, Sahinidis, Sharda and Bury (2014/2017), the review.**

- **How to choose a method.** Methods are chosen by problem features:
  - local or global;
  - discrete or continuous;
  - randomized or not;
  - expensive or cheap evaluations;
  - exploration or exploitation;
  - assumptions about the noise;
  - whether continuity holds.
  
  Table 3 classifies the method families this way, and the review points to Figueira and Almada-Lobo for a taxonomy that helps choose an approach.
- **Four ways to combine simulation and optimization:**
  1. simulation with optimization-based iterations;
  2. optimization with simulation-based iterations;
  3. sequential simulation and optimization;
  4. alternating simulation and optimization.
- **Use domain knowledge:**
  - screen the input variables;
  - scale and reduce the ranges of the decisions;
  - give good initial guesses;
  - use known structure.
- **Finite solution sets.**
  - Ranking and selection, from basic two-stage procedures (Rinott) to fully sequential ones (Kim and Nelson).
  - CRN-aware procedures beat the conservative Bonferroni approach.
  - A constrained version exists (Andradóttir and Kim 2010).
  - OCBA is the formulation that works within a fixed budget.
  - Multiple comparisons cover comparison with a control.
- **Large or infinite discrete sets.**
  - Ordinal optimization, random search, nested partitions and direct search.
  - For integer-ordered problems: COMPASS (Hong and Nelson) and R-SPLINE.
  - The Adaptive Hyperbox Algorithm, for more than about 10 to 15 variables.
- **Expensive simulations:** global response surfaces, kriging and Bayesian methods (SKO, KGCP, DiceOptim, the knowledge gradient), and trust-region response surfaces (STRONG).
- **Deterministic black-box outputs** belong to derivative-free optimization (DFO), not simulation optimization. DFO uses the same method families without the noise handling. Mesh adaptive direct search (NOMAD) is one example.
- **Commercial tools.** Most simulators bundle OptQuest (scatter search, tabu search, neural networks and integer programming): FlexSim, AnyLogic, Arena, Simio, Simul8, @RISK and others. Others use genetic or evolutionary methods. These "seem to work well but do not come with provable statistical properties". The review describes a lasting gap between research and practice.
- **Benchmarking.**
  - There is no standard test bed; SimOpt is the only one, with about 20 continuous problems at the time.
  - Comparisons use performance or data profiles, or macro-replications.
  - Solvers with random elements make results hard to reproduce.
- **Future directions:**
  - large mixed discrete and continuous problems;
  - stochastic and deterministic constraints;
  - parallel computing at the replication, iteration and algorithm levels;
  - several outputs at once;
  - risk measures as well as expected values;
  - hybrid algorithms;
  - automatic differentiation;
  - convergence guarantees;
  - easier comparison between methods;
  - better methods in commercial packages.

### How the findings bear on the open decisions

Each item below is evidence for the owner, not a decision. The codes are those of `Ithax-owner-decisions-final-2026-11-11.md`.

- **AKS-133 (owner decision, 2026-11-07, M5 item 6: fresh random numbers for confirmation).** Jian and Henderson recommend exactly this: re-run the chosen solution with an independent sample and a new random stream, because the best estimate found during the search is biased. Amaran et al. add that CRN make R&S between confirmed candidates more efficient. Together, the two sources support the owner's decision as written: fresh numbers between the search and the confirmation, and common numbers among the confirmed candidates.
- **D1 (R&S together with the top-three confirmation, chosen by a "score or vote").**
  - Both sources place R&S as the clean-up after a search, for small finite sets.
  - Amaran et al. choose methods by problem features, which gives the owner's "score that decides the method" a published basis. A transparent rule is enough; a learned vote is not needed:
    - a PCS-guaranteed procedure (Kim–Nelson with CRN; Andradóttir–Kim when there are constraints) when the candidates are few and the user gives an indifference zone;
    - OCBA when only a budget is given;
    - the present top-three confirmation otherwise.
  - The constrained case matches the Batur–Kim plan in `spec-2-simulation-based-optimization.md`.
  - Because commercial tools lack such guarantees, this could be a reason to do it sooner (Phase 1a rather than Phase 2). That is the owner's call.
- **B1 (weighted-sum objectives naming parameters).** Amaran et al. list several outputs at once as an open problem. A weighted sum is the crudest treatment. The evidence favours keeping the default (no) and planning proper multi-objective results for Phase 2: a trade-off front, or constraints on the secondary outputs.
- **B6 ("How many machines?" built with five scenarios).** For a small discrete set, both sources treat evaluating every alternative and ranking them as the right approach. The evidence supports accepting it (option a). For larger integer searches, COMPASS or R-SPLINE are the dedicated algorithms. The present Optuna TPE sampler has no simulation-specific guarantee.
- **D10 (arrivals that vary over time).** Neither source gives direct evidence. The Citi Bike case uses time-homogeneous Poisson demand over the morning rush (slide 43), and "half-full stations" is a starting allocation, not an average-demand model, so its gains do not isolate time variation. D10 rests on the owner's own use cases, not on these sources.
- **D11 (missing stock policies).** (s, S) and order-up-to inventory are standard applications of simulation optimization. This supports adding those policies in Phase 2.

### How the findings bear on specs 5 to 7 and Phase 2 to Phase 4

- **F9 and F11, spec 5 "Combining engines", "Design studies", "Surrogate models".**
  - The four combination paradigms of Amaran et al. give a ready framework for "Combining engines" and for optimization across engines.
  - SAA (Jian and Henderson) is a candidate way to join the process simulation to the HiGHS solver, but only with an extra step. Fixing the random streams makes each evaluation deterministic, yet the sample-average function still has no known algebraic form (Amaran et al., section 3.4). HiGHS needs a linear program (`src/lcsim/engines/optimize/solver.py::solve` takes a `LinearProgram`). So the bridge also needs an algebraic reformulation of the sampled scenarios, as in the call-centre staffing example over 1,000 simulated days, or a surrogate fitted to the simulation output.
  - Metamodels and response surfaces are a core family in both sources, which supports keeping "Surrogate models" and "Design studies".
- **Fidelity ladder and B7.1 (sketch fidelity, Phase 2).** "Model madness" and the Citi Bike succession support:
  - treating the sketch fidelity as the first step of a succession of models, not only as a preview;
  - seeding a search from a closed-form model, such as the Erlang C and Little's law formulas already used in the spec 2 benchmarks;
  - linking this to spec 6's fidelity ladder.
- **Spec 6 design studies (F13, F14).** Physics runs are expensive and usually deterministic. The literature points to:
  - DFO (for example mesh adaptive direct search) for deterministic outputs;
  - kriging and Bayesian metamodels (SKO, KGCP, DiceOptim, STRONG) when runs are expensive;
  - not a random search over many runs.
  
  These should be research items in spec 6. No licence has been checked.
- **Objectives (spec 2 extension, Phase 2).** Both sources list quantile and risk objectives, such as value-at-risk, alongside means. Candidates are a P90 wait or the probability of meeting a service level.
- **Stopping and replications.** Jian and Henderson suggest starting with few replications and increasing them as a search settles. That fits the existing `not_enough_runs` finding and its `n_required`.
- **Remote and cluster targets (F12 in Phase 2, F19 in Phase 4).** Parallel R&S at very large scale (about 10⁶ systems) and parallel replications are concrete uses of the SSH and Slurm targets.
- **Benchmarks for search methods (spec 2 and spec 5).** SimOpt (simopt.org) is the one public test bed of simulation optimization problems. Data profiles and macro-replications are the accepted ways to compare methods; a SimOpt problem's licence must be checked before its use. Seeded streams (spec 1) already answer the reproducibility problem that Amaran et al. raise.
- **Learn mode and templates (B7.3, template expansion in Phase 3).** The newsvendor "flaw of averages" is a ready lesson: replacing demand by its mean overstates the expected profit, by about 40% in the tutorial's example. That 40% is an overestimate of profit, not the profit lost by the decision, which is smaller. A finding that warns when a model is run without randomness is a possible Phase 2 rule.
- **Positioning.** Commercial simulators mostly ship optimizers with no statistical guarantee (Amaran et al., Table 4). Offering R&S guarantees, CRN, a fresh-stream confirmation and plain-language evidence would set Ithax apart.

### What the sources do not cover

Neither source covers any of the following:
- licences (B4, F4);
- Windows (F5);
- packaging (B5);
- hardware (F6);
- the physics engine choices (F13, F14);
- CAD (F15);
- material data (F16);
- validation of physics results (F18);
- how agents run the build (F2, F8).

## Sources

- Jian, N. and S. G. Henderson. 2015. "An Introduction to Simulation Optimization". Introductory Tutorials, Winter Simulation Conference, 7 December 2015. Slides: https://people.orie.cornell.edu/shane/pubs/WSC2015TutSlides.pdf (read 2026-11-11).
- Amaran, S., N. V. Sahinidis, B. Sharda and S. J. Bury. 2014. "Simulation optimization: a review of algorithms and applications". 4OR 12, 301–333. arXiv:1706.08591v1, 26 June 2017: https://arxiv.org/pdf/1706.08591 (read 2026-11-11).
- These references were not read here. Each was cited by one of the two sources: Kim and Nelson (2006) "Selecting the best system"; Hong, Nelson and Xu (2015) "Discrete optimization via simulation"; Chen, Chick and Lee (2015) on OCBA; Kim, Pasupathy and Henderson (2015) on SAA; Andradóttir and Kim (2010) on constrained R&S; Hong and Nelson on COMPASS; SimOpt (simopt.org); O'Mahony and Shmoys (2015) on Citi Bike.

## Decision

None. Both sources are evidence for the owner's open decisions and for the research that details specs 5 to 7. They change no spec and no code. The owner reviews each point beside its item in the decision list, and any answer is recorded in `docs/DECISIONS.md` in the usual way.

## Tested

Nothing was run. The figures quoted (567 to 443 and 1,096 to 493 unhappy users; the profit overstated by about 40%; about 500 and about 10⁶ systems; about 20 SimOpt problems) are the sources' own, not measured here.
