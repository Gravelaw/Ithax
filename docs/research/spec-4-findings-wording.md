# Findings wording: how simulation tools phrase bottleneck, stability and precision findings (spec 4, M8)

## Question

Spec 4 "Research before building", M8: "Findings wording. How commercial tools phrase
bottleneck and stability findings for non-experts." Done before any finding-rule code
(guide rule 3, AKS-117).

Spec 4 "Finding rules" already fixes five wording patterns. The question for M8 is whether
the way simulation tools and their teaching texts speak to non-experts supports them, and
where it suggests a change. Four sub-questions:

1. **Bottleneck.** How a tool names the bottleneck, and what "busy" is measured against
   when a resource has shifts or breakdowns.
2. **Stability.** How an overloaded resource, whose queue grows for as long as the run
   lasts, is explained.
3. **Not enough runs.** How a tool says that an estimate is too imprecise, and how it
   suggests the number of replications that would be enough.
4. **Comparing scenarios.** How a tool says that two alternatives cannot yet be told apart.

## Finding

Sources were read on 2026-11-08 (vendor help pages, a vendor textbook, a vendor-based
course, and teaching material). No tool publishes a fixed rule set of findings like spec
4's; each reports statistics and leaves the sentence to the user or the teacher, so the
wording below is the vocabulary these sources use when they explain a result.

### Bottleneck

- **Highest utilization is the usual definition.** Hopp and Spearman's *Factory Physics*
  defines the bottleneck rate of a line as the rate of the workstation with the highest
  long-term utilization; Evoma's bottleneck-analysis page restates it ("As per Factory
  Physics (Hopp & Spearman, 2011), the station with the highest utilization (arrival rate
  ÷ capacity) is the bottleneck"). The desflow tutorial says it in one line for
  newcomers: "The one with the highest utilisation is the bottleneck: it decides how long
  everything waits." Spec 4's rule (highest utilization, at least 0.85) matches.
- **Utilization is said as a share of time busy, in percent.** Simio's textbook writes
  "the inspection operators are busy roughly 77.3% of the time that they are working";
  AnyLogic's resource API returns "the fraction of time the unit was busy". Spec 4's
  "busy {utilization} of the time" is the same phrase.
- **Against available time, not the clock.** Simio's textbook works through a rework
  operator on one 8-hour shift a day who is busy 6.28 h: busy time over 24 h gives 26.17%,
  "However, if you were the rework operator, you'd likely say 'Wait a minute, I was way
  busier than that!'"; over the 8 available hours it is 78.50%, "a value with which the
  rework operator would likely agree". Simio reports this as `ScheduledUtilization`, "The
  percent utilization of the object's scheduled capacity during the run". AnyLogic does
  the same: with a schedule, "utilization will be calculated only for the operating hours
  of the resource unit". Spec 2's utilization (busy time over available capacity) is that
  measure, and spec 4's `bottleneck` row already judges on it. Simio's own sentence adds
  the qualifier "of the time that they are working" when a schedule applies; without it a
  reader can take 78.5% as a share of the whole day.
- **Signs a non-expert can check.** Practitioner guides list the bottleneck's signs as
  "The longest persistent queue", "The resource operating near 100% utilization" and "Long
  or volatile waiting times" (Simatron). Spec 4's pattern pairs the utilization with the
  average wait, which gives the reader the second sign as well as the first.

### Stability

- **Plain statement of the cause.** desflow's queueing page: "Above 1, orders arrive
  faster than the packers can pack them. The queue grows without limit in every case", and
  "At 1 or above it is not [stable]: the queue grows for as long as the run lasts, and
  every order waits longer than the one before." Spec 4's `unstable` pattern ("Work arrives
  faster than it can be done, so the queue will keep growing") says the same in the same
  order: the cause, then the queue.
- **Utilization exactly 1 is unstable too.** The same page notes that at exactly 1 "The
  queue does not settle, and it drifts longer over time", except for constant gaps and
  constant times. Spec 1's W201 fires at a load "at least" the capacity, which matches; the
  finding restates W201 and computes nothing new (spec 4: one computation, not two).
- **Near 1 the wait grows much faster than the load.** Kingman's formula for the G/G/1
  queue is "known to be generally very accurate, especially for a system operating close
  to saturation" (Wikipedia), and its utilization term ρ/(1 − ρ) is why a station at 0.90
  waits nine service times with exponential times. The 0.85 threshold of the `bottleneck`
  rule is the start of that steep part; no source gives 85% as a published cut-off (the
  Boston University "hockey stick" project says the knee depends on the number of servers
  and the variability), so it stays a proposal, as spec 4 says.

### Not enough runs

- **Vendors show the interval and leave the judgement to the user.** Simul8: "The
  confidence intervals help you establish how much trust you should put in the single
  average value"; "we can say we are 95% confident that the true average for alternative
  one lies in the range 233.8 to 257.8". Arena reports a "95% Confidence Interval Half
  Width" beside each output (Kelton et al., *Simulation with Arena*, chapter 6). Arena's
  batch-means reports print "(Insufficient)" or "(Correlated)" in place of a half-width
  when a single long run cannot support one (Rossetti, *Simulation Modeling and Arena*,
  section 5.4, from the search excerpt; the page itself could not be fetched): a flag,
  not a sentence. Spec 4's finding adds the sentence a non-expert needs.
- **Suggesting a number of replications is standard.** Simul8's Trial Calculator
  "recommends a number of runs to use for trials. The recommendation is based on your
  required precision of the confidence limits around the estimate of the mean". Kelton et
  al. give the formula a user can apply by hand: with h₀ the half-width from n₀ initial
  replications and h the half-width wanted, n ≅ n₀ h₀²/h² ("n grows quadratically as h"
  falls). Their worked example: 10 replications with a half-width of 812.82 on a mean of
  21,618.33 (3.8%), aiming at 250, gives "n ≅ 10(812.76²/250²) = 105.7, so 106", and they
  then ran 110, "conservative based on above". Spec 4's n_required, n × (half_width /
  (0.1 × mean))² rounded up to the next 10, is this formula with h = 10% of the mean, and
  its rounding is Kelton's conservative step.
- **Several outputs: take the largest.** Kelton et al.: "Use max of sample sizes for
  precisions on multiple outputs". Spec 4's finding is one per run and scenario, listing
  every metric that is too uncertain; the replications it suggests should be the largest
  of the metrics' n_required, which is the n_required of the metric whose half-width is
  the largest share of its mean (n_required grows with that share squared).
- **The suggestion is a guide.** The same course material notes that the replication
  count is approximate (t and s change with n): their 110 replications gave a half-width
  of 369.54, above the 250 aimed for ("undershot a bit?"). Spec 4's "About {n_required}
  replications" says "about", which is right.

### Comparing scenarios

- **Overlap means "run more".** Simul8's "Accuracy of results" help: when the confidence
  ranges of the alternatives overlap, "do more runs to see if they separate". Kelton et
  al. compare two scenarios with a paired-t interval on the difference and, when the
  intervals "both miss 0", "Conclude that there is a (statistically) significant
  difference". Spec 2's paired difference with `separated` (interval excluding zero) is
  this test, and spec 4's "{scenario_a} and {scenario_b} cannot be told apart on {metric}
  yet" is Simul8's advice in plain words; "yet" carries "do more runs".

## Sources

- Smith, J. S. and Sturrock, D. T., *Simio and Simulation: Modeling, Analysis,
  Applications*, 7th ed., chapter 5 "Intermediate Modeling With Simio" (utilization with
  schedules, `ScheduledUtilization`, the rework operator):
  https://textbook.simio.com/SASMAA7/ch-intermediate-modeling.html
- AnyLogic Help, "Resource functions" (`getUtilization()`: "the fraction of time the unit
  was busy ... calculated only for the operating hours of the resource unit"):
  https://anylogic.help/library-reference-guides/process-modeling-library/resource-api.html
- Simul8 Help (Minitab), "Accuracy of Results" (confidence range, "do more runs to see if
  they separate"):
  https://support.minitab.com/en-us/simul8/help-and-how-to/getting-started/accuracy-of-results/
- Simul8 Help (Minitab), "Trials" (five runs by default, 95% confidence limits, the Trial
  Calculator): https://support.minitab.com/en-us/simul8/help-and-how-to/simulation-key-concepts/trials/
- Kelton, W. D., Sadowski, R. P. et al., *Simulation with Arena*, 5th ed.,
  chapter 6 "Statistical Output Analysis for Terminating Simulations", lecture slides used
  at Bilkent University IE 324 (half-width, n ≅ n₀ h₀²/h², the 106 and 110 replications
  example, "Use max of sample sizes", paired-t comparison):
  https://courses.ie.bilkent.edu.tr/ie324/wp-content/uploads/sites/4/2016/09/Chapter6-TerminatingSimulations.pdf
- Rossetti, M. D., *Simulation Modeling and Arena*, section 5.4 "The Batch Means Method"
  ("Insufficient" and "Correlated" half-widths; read from the search engine's excerpt, the
  page returned 404 when fetched): https://rossetti.github.io/RossettiArenaBook/ch5-BatchMeansMethod.html
- Evoma, "Bottleneck and System Performance Analysis" (highest utilization, after Hopp and
  Spearman): https://evoma.se/use-case/bottleneck-and-system-performance-analysis/
- Simatron, "Where Is the Bottleneck? A Practical Guide to Simulation Modeling and
  Analysis" (signs of a bottleneck):
  https://simatron.solutions/where-is-the-bottleneck-a-practical-guide-to-simulation-modeling-and-analysis/
- desflow documentation, "Queueing Basics" and "Queues and Capacity" (stability in plain
  words; highest utilization as the bottleneck):
  https://jaehyeon.me/desflow/latest/learn/concepts/queueing-basics/ and
  https://jaehyeon.me/desflow/latest/tutorials/queues-and-capacity/
- Wikipedia, "Kingman's formula": https://en.wikipedia.org/wiki/Kingman%27s_formula
- Boston University MET DS Lab, "Finding the Knee of a Waiting Line 'Hockey Stick' Curve"
  (the knee depends on servers and variability):
  https://sites.bu.edu/met-dslab/projects/past_projects/finding-the-knee-of-a-waiting-line-hockey-stick-curve

Not found: a vendor page that defines a fixed bottleneck sentence (Simul8's bottleneck
page speaks only of "where bottlenecks are building up"; FlexSim's documentation found was
about state charts and utilization collectors), or a published 85% cut-off.

## Decision

Spec 4's five patterns stand; no finding contradicts the spec, so spec 4 is not changed
before the code. The rules are built to the patterns with these readings (rule 5, owner to
confirm), each logged in `docs/DECISIONS.md`:

1. **Utilization in percent, against available time.** `{utilization}` and `{idle}` are
   whole percentages ("busy 90% of the time"). When a `schedule` or `failure` changes a
   server's capacity (a schedule on the server or on its pool, or a failure on the
   server), the text says "of the time it was available" in place of "of the time", as
   Simio's textbook does, since spec 2's utilization is over available capacity.
2. **`not_enough_runs` names the widest metric and the largest n.** The finding lists
   every key metric that is too uncertain; `{metric}`, `{mean}` and `{half_width}` are
   those of the metric whose half-width is the largest share of its mean, and
   `{n_required}` is the largest of the listed metrics' n_required, which is that same
   metric's (Kelton et al.: "Use max of sample sizes").
3. **n_required as spec 4 gives it.** n × (half_width / (0.1 × mean))², rounded up to the
   next multiple of 10 (Kelton et al.'s formula with h = 10% of the mean, and their
   conservative rounding); the threshold's share replaces 0.1 when the threshold is
   changed, so the suggested count is always the one for the interval the user asked for.
4. **Scenario comparison.** The pair wording stays "{scenario_a} and {scenario_b} cannot
   be told apart on {metric} yet."; with several metrics they are joined ("on a and b
   yet").
5. **Unstable.** The pattern stays; the finding is built from the W201 issues in
   `summary.json` `warnings` and computes nothing.
6. **Display units.** Times in the largest Phase 1 unit they reach (s, min, h, d) and
   rates per hour, to three significant figures; the half-width in the unit of its mean
   (spec 4's example: "17.3 min").

## Tested

`tests/findings/` (AKS-117): each rule fires on its `_fires` fixture and is silent on its
`_silent` fixture, and the wording tests check every pattern above, including the
available-time phrase, the widest metric and largest n_required, and n_required's
rounding.
