# Output analysis methods (spec 2, M3)

## Question

Spec 2 "Research before building", M3: "Output analysis methods. Published methods for
choosing warm-up length and number of replications." Two decisions hang on it:

- **Warm-up.** Spec 2 "Statistic definitions" proposes a warm-up check: for each
  time-persistent statistic, the means over the first and second halves of the observed
  period are compared across replications as a paired difference, and `summary.json`
  carries W210 when the 99% interval excludes zero and the difference exceeds 5% of the
  mean. The spec says this note "may replace it with MSER-5 or Welch and must say why".
  Whatever is chosen must be a closed-form calculator over the M2 `timeseries` table
  (guide rule 7), stated precisely enough for the experiment manager (AKS-102) to build
  without guessing.
- **Number of replications.** Spec 1 sets 30 replications by default, and spec 4's
  `not_enough_runs` finding fires when a key metric's half-width exceeds 10% of its mean,
  projecting `n_required = n × (half_width / (0.1 × mean))²`. Is that the published
  approach?

## Finding

### Three ways to judge the warm-up

| | Paired halves (spec 2's proposal) | MSER-5 | Welch's method |
| --- | --- | --- | --- |
| What it gives | A yes or no: did the mean still move during the observed period? | A truncation point: how much of the start to delete | A plot from which a person reads a warm-up length |
| Input | Each replication's series, kept separate | One series (a single run, or the replications averaged) | The replications averaged, then a moving average |
| Statistic | Paired t interval across replications of (second-half mean − first-half mean) | Batch the series in fives; pick the d that minimises S²(n, d)/(n − d) over the batches left after deleting d | None: the user judges where the moving average flattens |
| False-alarm rate | Set by the confidence level: the replications are independent, so the differences are too | Not controlled: it always returns a point, often a small non-zero one on a stationary series | Not applicable |
| Automation | Full | Full | Needs a person to choose the window and read the plot |
| Rule 7 | Closed form (means, a standard deviation, a t quantile) | Closed form (a minimum over a finite set of sums) | Closed form, but the decision is human |

**Paired halves.** Testing whether a series still carries initialization bias, rather
than estimating where to cut, has a history in the hypothesis tests of Schruben (1982) and
Schruben, Singh and Tierney (1983), which Franklin and White (2008) describe as using
"hypothesis testing to decide if a sequence is stationary". Spec 2's check is a simple
test of that kind that relies on replications instead of a variance estimate from within
one run: each replication r yields one difference
d_r = (mean of the second half) − (mean of the first half), the d_r are independent and
identically distributed across replications because each replication has its own streams
(spec 1 "Random streams"), and the t interval on their mean is the ordinary paired
interval spec 2 already uses for scenario differences. Its false-alarm rate per statistic
is therefore close to 1 − confidence (normality of the d_r aside), and the
autocorrelation within a run does not enter, since each replication gives one d_r. It answers
"was the warm-up long enough?", which is what W210 says; it does not say how long the
warm-up should be.

**MSER-5.** White (1997) proposed MSER: delete the first d observations where d minimises
the marginal standard error S²(n, d)/(n − d), S² being the variance of the observations
left. Spratt (1998, a thesis cited by the next paper) applied it to batch means of five
observations (MSER-5). White, Cobb and Spratt (2000) compared five truncation rules and
found MSER-5 the most effective and robust general-purpose choice. Franklin and White (2008) give the statistic in that form
and explain that minimising it is choosing the truncation whose confidence interval about
the mean is narrowest. White, Cobb and Spratt evaluate d only over the first half of the
series; if the statistic keeps falling to d = n/2 they conclude the series is too short.
Hoad, Robinson and Davies (2008), building an automated output analyser, found MSER-5 the
best and most consistent of their shortlisted methods but recorded its weaknesses: it can
report a truncation point at the end of the series (they leave the last few points out of
the search), it is sensitive to outliers, it struggles with highly autocorrelated data,
and a truncation point beyond n/2 counts as a failure. It worked better on data averaged
over replications than on single runs. MSER-5 estimates a truncation point; it has no
significance level, so using it as a warning needs a further threshold on that point.

**Welch's method.** Welch (1983) averages the replications point by point, smooths the
average with a moving window and takes as the warm-up the point where the smoothed curve
flattens. Hoad, Robinson and Davies (2008) list it among the graphical methods and set it
aside for automation: it "requires a user to judge the smoothness and flatness of a moving
average plot; this would be difficult to automate". It suits an interface that shows the
averaged series, not a warning computed with no one watching.

### Number of replications

Hoad, Robinson and Davies (2007) name three ways to choose the number of replications: a
rule of thumb (at least 3 to 5, Law and McComas 1990), a graphical method (Robinson 2004)
and the "confidence interval with specified precision" method (Robinson 2004; Law 2007;
Banks et al. 2005), which they chose to automate. Its precision is the half-width as a
percentage of the mean, d_n = 100 · t(n − 1, α/2) · s_n / (√n · X̄_n), and replications are
added until d_n is at most the precision required (their algorithm then runs a few more to
check that it stays there).

Spec 4's `not_enough_runs` is this precision measure with 10% as the required precision,
applied after the run instead of sequentially, since Phase 1 runs a fixed number of
replications. Its `n_required` solves d_n = 10% for n while holding the sample standard
deviation, the mean and the t quantile at their current values: the half-width falls as
1/√n, so n × (half_width / (0.1 × mean))². Holding t at n − 1 degrees of freedom makes the
projection slightly high, since t shrinks as n grows, and rounding up to the next 10 adds
margin. It is an estimate, and the finding says "about".

## Sources

Bibliographic details were checked against Crossref (api.crossref.org) or Open Library on
2026-11-06. "Read" means the text was opened and the statements above taken from it;
"record only" means only the bibliographic record was seen, and the note relies on the
source only as cited by a paper that was read.

- K. Preston White, Jr., "An Effective Truncation Heuristic for Bias Reduction in
  Simulation Output", Simulation 69(6), 323–334, December 1997,
  doi:10.1177/003754979706900601. Record only; MSER as described by the two papers below.
- K. Preston White, Jr., Michael J. Cobb and Stephen C. Spratt, "A Comparison of Five
  Steady-State Truncation Heuristics for Simulation", Proceedings of the 2000 Winter
  Simulation Conference, 755–760, doi:10.1109/WSC.2000.899843. Read (a full-text copy at
  https://typeset.io/pdf/a-comparison-of-five-steady-state-truncation-heuristics-for-3tr0r3ux33.pdf):
  MSER-5 "the most effective and robust choice for a general-purpose method"; d evaluated
  over the first half; d* = n/2 means the sample is inadequate.
- William W. Franklin and K. Preston White, Jr., "Stationarity Tests and MSER-5: Exploring
  the Intuition behind Mean-Squared-Error-Reduction in Detecting and Correcting
  Initialization Bias", Proceedings of the 2008 Winter Simulation Conference,
  https://www.informs-sim.org/wsc08papers/064.pdf. Read: MSER(n, d) = S²(n, d)/(n − d),
  equation (1); MSER-5 batches five observations; minimising MSER also minimises the
  confidence interval estimate, equation (2).
- Kathryn Hoad, Stewart Robinson and Ruth Davies, "Automating Warm-up Length Estimation",
  Proceedings of the 2008 Winter Simulation Conference, 532–540,
  doi:10.1109/WSC.2008.4736110, https://www.informs-sim.org/wsc08papers/063.pdf. Read: the
  review of warm-up methods, Welch's method set aside for automation, the MSER-5 results and
  weaknesses. A journal version is in the Journal of the Operational Research Society
  61(9), 1389–1403, 2010, doi:10.1057/jors.2009.87 (record only).
- Kathryn Hoad, Stewart Robinson and Ruth Davies, "Automating DES Output Analysis: How Many
  Replications to Run", Proceedings of the 2007 Winter Simulation Conference, 505–512,
  doi:10.1109/WSC.2007.4419641, https://www.informs-sim.org/wsc07papers/060.pdf. Read: the
  three ways to choose the number of replications, the precision d_n and the stopping rule.
  A journal version is in the Journal of the Operational Research Society 61(11),
  1632–1644, 2010, doi:10.1057/jors.2009.121 (record only).
- Peter D. Welch, "The Statistical Analysis of Simulation Results", in Stephen S.
  Lavenberg (ed.), Computer Performance Modeling Handbook, Academic Press, 1983 (ISBN
  0-12-438720-9). Record only; the method as described by Hoad, Robinson and Davies (2008).
- Averill M. Law, Simulation Modeling and Analysis, McGraw-Hill (5th edition, ISBN
  978-0-07-340132-4; 6th edition 2024). Record only; the confidence interval with specified
  precision method is cited to it (4th edition, "Law 2007") by Hoad, Robinson and Davies
  (2007). The book itself was not available to read, so no page, equation or wording of it
  is relied on.
- Lee W. Schruben, "Detecting Initialization Bias in Simulation Output", Operations
  Research 30(3), 569–590, 1982, doi:10.1287/opre.30.3.569; Lee Schruben, Harbans Singh and
  Lewis Tierney, "Optimal Tests for Initialization Bias in Simulation Output", Operations
  Research 31(6), 1167–1178, 1983, doi:10.1287/opre.31.6.1167. Records only; named by
  Franklin and White (2008) as tests for the presence of initialization bias.

## Decision

**The warm-up check stays as written, with its 99% level and 5% threshold, and is now
stated precisely in spec 2 "Statistic definitions".** MSER-5 and Welch's method are not
adopted for W210. Reasons:

- W210 is a warning that the warm-up was too short. The paired-halves check is a test of
  exactly that question, with a false-alarm rate set by its level, because it works on
  independent replications. MSER-5 answers a different question (where to cut) and always
  returns a point; turning it into a warning needs a threshold that no source calibrates.
  In the runs below it returned non-zero truncation points on the shipped warehouse and
  three-machine line, whose warm-ups are adequate, so "fire when d* > 0" would be noisy.
  Welch's method needs a person.
- It is the simplest closed form of the three: two means per replication, a standard
  deviation and a t quantile, all over the existing `timeseries` table (rule 7). It reuses
  the paired-difference interval the experiment manager already computes for scenarios.
- Tested on M2 output (below), it is silent on the coffee shop at its own seed and at 40 of
  40 other seeds, and fires on a slowly filling model with no warm-up at all 40 seeds.

Its limit, shown below: it fires only on bias the replications can tell apart from their
own noise. A single server at utilization 0.95 with no warm-up, run for 20 h, fires at 24
of 40 seeds (not at seed 12345). Run for 200 h it fires at none: there the drift between
halves is small against the noise, and a 50 h warm-up leaves the estimate where it was, so
the shortfall is imprecision, not warm-up. Both runs' estimates are imprecise, and spec 4's
`not_enough_runs` fires on the server's wait (half-width 32.5% and 11.8% of the mean). A
95% level would fire more often on the heavy server (33 of 40 at 20 h) but also on 2 to 4
of 40 correct runs of each shipped example, which is the false-alarm rate spec 2 chose 99%
to avoid. MSER-5 remains a candidate for
suggesting a warm-up length in the interface (Welch's averaged plot likewise), not for the
warning; that is not decided here.

The rule, as spec 2 now states it (simplest readings, owner to confirm, recorded in
`docs/DECISIONS.md`):

1. For each scenario and each metric of the run's `timeseries` table, take each
   replication's samples with `time_s` ≥ `warmup`, in time order: J of them.
2. If J < 2, skip the metric. Otherwise h = ⌊J/2⌋; the first half is the first h samples,
   the second half the last h (the middle sample is in neither when J is odd).
3. Per replication r: d_r = mean(second half) − mean(first half); m_r = mean(all J).
4. Across the n replications: d̄ = mean of d_r, m̄ = mean of m_r, s = sample standard
   deviation of d_r (n − 1), half-width = t(0.995, n − 1) · s / √n with
   `scipy.stats.t.ppf`, whatever the experiment's `confidence`.
5. The metric has changed when |d̄| > half-width and |d̄| > 0.05 · |m̄|.
6. If any metric changed in any scenario, `summary.json` `warnings` gets one W210 for the
   run: `component` null, `path` `/experiments/<index>/warmup`, `message` "Results were
   still changing after warm-up: " plus "<metric> in scenario <scenario> changed by <p>% of
   its mean between the first and second halves of the observed period" for each changed
   metric (scenario order, then `timeseries` row order), joined by "; ", with a final full
   stop, p = round(100 · |d̄| / |m̄|); `hint` "Lengthen 'warmup' and run again.".
7. A search's candidates are left to M5.

**Number of replications.** No change. The default of 30 (spec 1) stays, and spec 4's
`not_enough_runs` and `n_required` are the published relative-precision method applied
after the run; M8 builds and checks them.

## Tested

On 2026-11-06, Python 3.13.18 (numpy 2.5.4, scipy 1.18.1, simpy 4.1.2), 4 workers, from a
throwaway script in a scratch directory outside the repository; no product code was
written or changed. Each case loads a model with `lcsim.model.loading.load_document`
(zero issues), then runs `ProcessAdapter().translate(model, "base", tmp)`,
`.run(tmp, lambda p: None, threading.Event(), 4)` and `.collect(tmp)` in a temporary
directory, and applies the rule of the Decision, steps 1 to 5, to the `timeseries` table.
The essential steps (the script also has an `if __name__ == "__main__":` guard, which the
adapter's `spawn` workers need):

```python
from math import sqrt
from statistics import fmean, stdev

from scipy.stats import t


def paired_halves(reps, conf=0.99):  # reps: {replication: [observed samples]}
    values = [reps[k] for k in sorted(reps)]
    J = len(values[0])
    half = J // 2
    if half == 0:
        return None
    d = [fmean(v[J - half :]) - fmean(v[:half]) for v in values]
    m = [fmean(v) for v in values]
    n = len(d)
    dbar = fmean(d)
    mbar = fmean(m)
    h = t.ppf(1 - (1 - conf) / 2, n - 1) * stdev(d) / sqrt(n)
    return dbar, h, mbar, abs(dbar) > h and abs(dbar) > 0.05 * abs(mbar)


# observed samples: rows of the timeseries table with time_s >= warmup (in seconds),
# grouped by (scenario, metric) and replication, in time order
```

For comparison the script also computed MSER-5 on the across-replication average of each
observed series: batches of 5 samples, d (in batches) from 0 to half the batches,
minimising Σ(Z_i − Z̄)² / (b − d)² over the b − d batches left (the S²/(n − d) of Franklin
and White with S² taken with denominator n − d), reported as d* in samples.

The models: the three examples as shipped (seed 12345, 30 replications; coffee shop and
warehouse 200 h with 10 h warm-up, line 100 h with 20 h); the coffee shop with warm-up 0;
"heavy", the coffee shop with service mean 1.9 min (utilization 0.95, M/M/1 mean queue
ρ²/(1 − ρ) = 18.05, mean wait 2,166 s); and "slow fill", a source (exponential, mean
2 min) into a `delay` (exponential, mean 10 h) into a sink, 100 h, whose `model.wip` rises
from 0 toward 300 with a 10 h time constant.

**At seed 12345** (d̄ and the 99% half-width h in items or as a fraction; "p" is |d̄|/|m̄|):

| Case | Metric | J | m̄ | d̄ | h | p | Fires | MSER-5 d* |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Coffee shop as shipped | `till.queue_length` | 190 | 2.2233 | −0.0768 | 0.2429 | 3.5% | no | 0 |
| | `till.utilization` | 190 | 0.7549 | +0.0053 | 0.0283 | 0.7% | no | 0 |
| | `model.wip` | 190 | 2.9782 | −0.0716 | 0.2478 | 2.4% | no | 0 |
| Coffee shop, warm-up 0 | `till.queue_length` | 200 | 2.2230 | −0.1207 | 0.2728 | 5.4% | no | 0 |
| | `till.utilization` | 200 | 0.7565 | +0.0043 | 0.0261 | 0.6% | no | 5 |
| | `model.wip` | 200 | 2.9795 | −0.1163 | 0.2743 | 3.9% | no | 0 |
| Slow fill, warm-up 0 | `model.wip` | 200 | 268.81 | +60.644 | 6.250 | 22.6% | **yes** | 95 |
| Slow fill, warm-up 50 h | `model.wip` | 100 | 299.13 | −2.097 | 6.794 | 0.7% | no | 0 |
| Heavy, warm-up 0, 20 h | `till.queue_length` | 200 | 10.073 | +4.217 | 5.062 | 41.9% | no | 100 |
| Heavy, warm-up 0, 200 h | `till.queue_length` | 200 | 14.971 | −1.458 | 5.119 | 9.7% | no | 15 |
| Heavy, warm-up 50 h, 200 h | `till.queue_length` | 150 | 15.291 | −2.314 | 4.613 | 15.1% | no | 55 |

So W210 is silent on the coffee shop as shipped (its largest p is 3.5%, and no interval
excludes zero) and fires on the slow fill with no warm-up, where d̄ is ten times its
half-width; with a 50 h warm-up the slow fill is silent. The heavy server is silent at this
seed at both lengths: at 20 h its queue rose by 42% of its mean between the halves, but the
99% half-width (5.06) is larger than the rise (4.22). The other heavy metrics behave the
same (`model.wip` d̄ +4.243, h 5.091 at 20 h). On the shipped line and warehouse every
metric is silent (largest p 12.3% for `cut.queue_length` with d̄ −0.113 inside h 0.142),
while MSER-5 returns d* = 20 samples for the warehouse's `pack.queue_length` and
`model.wip` (20 h past its warm-up) and the line's `paint.queue_length` (10 h).

**Across seeds** (seeds 1 to 40, the cases' own settings otherwise; fired means W210 for
the run):

| Case | Fired at 99% | Fired at 95% |
| --- | --- | --- |
| Coffee shop as shipped | 0 of 40 | 2 of 40 |
| Coffee shop, warm-up 0 | 0 of 40 | 3 of 40 |
| Three-machine line as shipped | 2 of 40 | 4 of 40 |
| Warehouse as shipped | 0 of 40 | 3 of 40 |
| Heavy, warm-up 0, 20 h | 24 of 40 | 33 of 40 |
| Heavy, warm-up 0, 200 h | 0 of 40 | 5 of 40 |
| Slow fill, warm-up 0, 100 h | 40 of 40 | 40 of 40 |
| Slow fill, warm-up 50 h, 100 h | 0 of 40 | 0 of 40 |

The two line runs that fire at 99% (seeds 24 and 33) fire on one utilization each:
`paint.utilization` m̄ 0.5094, d̄ +0.0354, h 0.0335, p 7.0%, and `cut.utilization` m̄
0.5873, d̄ +0.0329, h 0.0294, p 5.6%. Cut is the first station, so its utilization after
20 h has no start-up trend left: these are false alarms, just past both thresholds.

**Spec 4 on the heavy server** (seed 12345, `till.wait.mean`, 95% half-width): 20 h with
warm-up 0, 1,204.3 ± 391.1 s (32.5% of the mean, `n_required` 320); 200 h with warm-up 0,
1,806.9 ± 214.1 s (11.8%, 50); 200 h with warm-up 50 h, 1,844.0 ± 227.0 s (12.3%, 50);
1,000 h with warm-up 100 h, 1,985.8 ± 165.4 s (8.3%, 30). The first three exceed the 10%
`not_enough_runs` threshold; a 50 h warm-up barely moves the 200 h estimate, and the
1,000 h interval contains the theory value of 2,166 s.
