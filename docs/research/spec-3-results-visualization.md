# Spec 3 research: visualising data, runs and search trials (M9 design review)

## Question

The owner reviewed the M9 design (AKS-118) and asked: "there is no visualization or graphs to analyze the data or output, or if, say, 1000 simulation trials are taken to optimize a process, how do I view them?"

This note answers four questions:

1. How do other simulation and optimization tools show results, experiments and search trials, and which of their views still work at 1,000 or more trials?
2. Which charts of uncertainty can a student or business user with no statistics read correctly?
3. What can each screen draw from the data the specs already define, and what is missing?
4. Which React chart library fits a Tauri 2 webview that runs offline, under AGPL-3.0?

It covers spec 3 Screens 3 (Data), 4 (Experiment), 5 (Run monitor) and 6 (Results), spec 3 "Endpoints" and "Progress events", spec 1 "Run folder and results", spec 2 "Simulation-based optimization" and "Optimization model layout", and spec 4 "Findings in plain language". It does not change any spec. Proposed changes are listed under Decision for the owner.

## Finding

### 1. What the wireframes show today

- **Data** (`wireframes/03-data.svg`): files, columns, a preview of the first rows, and a table of fitted distributions with a score. There is no picture of the data.
- **Run monitor** (`05-run-monitor.svg`): a progress bar, a table of live key numbers ("Value so far") and the run queue. No chart. Nothing special for a search run: `flows.md` says only that the monitor "shows the progress messages the service sends".
- **Results** (`06-results.svg`): findings, a key-numbers table with 95% intervals, one chart ("Mean wait by station, with 95% intervals") with its data table, and the raw `replications` and `timeseries` tables. Nothing for a search run, and nothing over time, although the `timeseries` table exists.

The owner's point stands: the design shows one chart, and no way to look at many search candidates.

### 2. How other tools do it

| Tool | Experiment and output views | Search (optimization) views | Good at 1,000+ trials? |
| --- | --- | --- | --- |
| AnyLogic | Parameter variation runs the model over a grid or freeform list; its default UI is a table of the current iteration. Multi-run experiments in AnyLogic Cloud offer charts of outputs across runs. | The default optimization UI has a table of Current and Best values (iteration, parameters, objective) and a chart with simulations on the x-axis and Current objective, Best feasible and Best infeasible on the y-axis. | The best-so-far chart scales to any number of iterations (the AnyLogic tutorial runs 500). The table shows only current and best. |
| Simio | Experiment pivot grid with confidence intervals. SMORE plots (Simio Measure of Risk and Error, after Nelson 2008): a box plot of the replication results with mean, median, chosen lower and upper percentiles, min and max, optional confidence intervals on the mean and percentiles, a histogram, and the individual replication dots. One plot per scenario, side by side. | OptQuest fills the experiment grid with scenarios; results are viewed in the same grid and SMORE plots. | SMORE plots work for many replications (the Simio textbook shows 500). Side-by-side SMORE plots do not scale to hundreds of scenarios; the grid does, by sorting. |
| FlexSim | Performance Measure Results: "Replications Plot" (each replication's value per scenario, with optional box plot and mean with 90/95/99% interval), "Frequency Histogram" (overlapping scenarios), "Correlation Plot" (one measure against another), "Data Summary", "Raw Data". Dashboards and a "Scenario Chart" that repeats any dashboard chart across scenarios. | Optimizer Results tab: a graph of evaluated scenarios with chosen x and y values; click to select scenarios, export them to the scenario table or CSV. | The selectable scatter scales well; selecting points and pushing them back to scenarios is the key interaction. |
| Arena | Output Analyzer: confidence intervals and "Compare Means" on two scenarios (interval on the difference). Process Analyzer: a scenario table with controls and responses, and box-and-whisker charts with "Identify Best Scenarios", which colours the scenarios that are statistically best. Input Analyzer: histogram of the data with the fitted density drawn on top. | OptQuest results as a ranked list of solutions. | Ranked lists and box-whisker charts scale to tens of scenarios, not thousands. |
| JaamSim | Results are objects placed in the model view: a `Graph` plots chosen outputs (for example queue lengths) over the last stretch of simulated time, and a `BarGauge` sits above a server and shows a value. | None built in. | Not designed for experiments; its strength is live charts on the model itself. |
| Optuna (`optuna.visualization`, Optuna Dashboard) | Not a simulation tool. | `plot_optimization_history` (objective of each trial and best so far), `plot_slice` (objective against each parameter, one dot per trial), `plot_contour` (objective over two parameters), `plot_parallel_coordinate` (one line per trial across all parameters), `plot_param_importances`, `plot_edf` (share of trials below each objective value), `plot_rank`, `plot_timeline` (when each trial ran), `plot_pareto_front` (multi-objective). The dashboard adds a sortable, filterable trial table linked to the charts. | History, slice, EDF and the trial table scale to thousands. Parallel coordinates and contour get cluttered or slow beyond a few hundred trials without filtering. Timeline is a developer view. |
| Ax (Meta) | Not a simulation tool. | "Utility progression" (best value so far by trial, only improvements plotted, infeasible trials excluded), observed and modelled "arm effects" (each candidate's value with an interval), slice and contour plots from a surrogate model, sensitivity analysis, parallel coordinates and a summary table. | Same as Optuna. Its surrogate-model plots need a fitted model, which this product does not have. |

What they share:

- **A best-so-far line** (AnyLogic, Optuna, Ax) is the first view of any search. It answers "is the search still improving?" at any number of trials.
- **One dot per replication or trial**, with the mean and an interval drawn on top (Simio SMORE, FlexSim Replications Plot, Optuna slice). Users see spread, not just an average.
- **A sortable, filterable table linked to the chart** (Optuna Dashboard, FlexSim optimizer, Arena Process Analyzer). With 1,000 trials, the table is how a user finds and opens one trial; the chart is how they see the pattern.
- **Push a chosen trial back into the model** as a scenario (FlexSim "Export Selected Scenarios", AnyLogic "Copy" of the best).
- **Results on the model itself** (JaamSim gauges, AnyLogic and FlexSim animation): users look for the bottleneck on the drawing they built.

### 3. Showing uncertainty to non-experts

Plain meaning of each candidate chart:

- **Interval chart (mean with error bar).** A dot for the average and a bar for the range the true average probably lies in. Compact, but research finds that both lay people and experts misread intervals (Belia et al. 2005; Padilla, Kay and Hullman 2022 review).
- **Box plot.** A box holding the middle half of the results, a line at the median and whiskers to the extremes. Familiar from school, but the box shows only half the runs (the Simio textbook suggests 10% and 90% instead of quartiles for this reason).
- **Violin plot.** A smooth outline whose width shows where results are common. Looks friendly, but people must judge area.
- **Histogram.** Bars counting how many runs fell in each range. Easy to read; its shape depends on the bin width.
- **Dot strip (one dot per replication).** Every run is a dot on one line, so 30 replications are 30 dots. Nothing to learn: "in 4 of 30 runs the wait passed 10 minutes" can be counted.
- **Quantile dotplot.** A fixed number of dots (for example 20), each standing for a 5% chance. Kay et al. (2016) and Fernandes et al. (2018) found lay users judge chances more accurately and make better decisions with these than with density curves, intervals or text; Kale, Kay and Hullman (2020) found quantile dotplots gave the least biased estimates of effect size.
- **Hypothetical outcome plot (HOP).** An animation that shows one possible outcome per frame. Lay users judge trends better than with error bars (Kale et al. 2018), but it moves, needs a reduced-motion alternative and cannot be printed in the PDF.
- **SMORE plot.** A box plot plus intervals on the mean and on the percentiles, plus the replication dots. Rich, but has many elements to explain.
- **Fan chart or band over time.** A line for the typical value and a shaded band showing where most runs were at each moment. Standard for forecasts.
- **Interval shrinkage (convergence) chart.** The interval half-width against the number of replications. It answers "are 30 replications enough?" in one picture; spec 4's `not_enough_runs` finding answers the same question in words.

What the research says to do (Padilla, Kay and Hullman 2022; Padilla et al. 2021; Kale et al. 2020):

- Prefer frequency framing: show outcomes as countable things (dots), not only a mean and an interval.
- Do not let the mean dominate: adding a bold mean makes people discount the spread a little.
- Text helps but is not enough alone: textual uncertainty performed worse than dotplots or CDF charts in the transit study.

For this product, with 30 replications by default, a dot strip is already a frequency display: each dot is one equally likely run. It needs no new statistic and keeps the reported mean and interval from `summary.json` as a thin overlay.

### 4. Data screen: checking a fitted distribution

| Chart | Plain meaning | Ease for a novice |
| --- | --- | --- |
| Histogram with fitted curve on top | Bars of the user's data; a curve of the chosen distribution. If the curve follows the bars, the fit is good. | Easiest. It is what Arena's Input Analyzer shows after "Fit". Weakness: the picture changes with bin width (Rossetti, Appendix B), so the bin count should be fixed by a rule, not by the user. |
| ECDF with fitted CDF | A staircase rising from 0 to 1: at each value, the share of the data at or below it, with the fitted curve drawn on top. | Readable once explained as "share of gaps shorter than x"; no bins to choose. Fernandes et al. (2018) found CDF charts nearly as good as dotplots for lay decisions. |
| P-P plot | Data's share below each point against the fit's share; a straight diagonal means a good fit. | Abstract; hard for novices. |
| Q-Q plot | Data's sorted values against the fit's quantiles; a straight diagonal means a good fit. Shows the tails best. | Hardest. Useful for students in Learn mode, not as a default. |
| Values in file order | The column drawn in the order the rows came. Shows drift, such as arrivals getting busier at lunch, which a single distribution cannot represent. | Easy. Important because Phase 1 sources draw from one fixed distribution. |

### 5. Run monitor: what the progress events allow

Spec 3 "Progress events" defines three messages: `progress` (`fraction`, `message`), `metrics` (`scenario`, `values`: a value so far per metric) and `state`. On connection the stream sends the state and the latest `progress` only.

What can be drawn live:

- **Plain run:** the progress bar; a small line per key metric of "value so far" against the progress fraction, built in the client from successive `metrics` events (a sparkline). It shows the estimate settling. It cannot show an interval: `metrics` carries no half-width and no count of finished replications.
- **Search run:** only the progress bar and the message. There is no per-candidate event, so no best-so-far chart and no table of candidates can be drawn while a search runs.

Spec gaps found:

1. **No per-candidate progress event.** A search sends only `progress` and `metrics`. A live best-so-far chart needs one event per finished candidate.
2. **A late client misses earlier candidates.** On connection the stream sends only the latest `progress`. A user who opens the monitor at candidate 600 would see nothing of the first 599.
3. **Candidates reach the client only at the end, in `summary.json`.** Spec 2 gives `search.candidates: [{set, metrics, feasible, confirmed}]` with no candidate number (evaluation order), no stage, no half-width, and it does not say whether `metrics` holds the search-stage or the confirmed means. A best-so-far chart needs the order; a confirmation chart needs both stages and intervals.
4. **No table for candidates.** `GET /v1/runs/{rid}/tables/{name}` accepts only `replications` and `timeseries`. Spec 1 does not say what these tables hold for a search run: each candidate's search-stage replications, only the confirmation stage, or nothing. A per-candidate dot chart and a CSV export of all trials need these rows.
5. **Paired scenario differences have no place in `summary.json`.** Spec 1 says the manager computes them and spec 2 says separated pairs are reported, but the `summary.json` layout has no field for them. A comparison chart ("two tills cut the wait by 3.1 ± 0.4 min") needs it, and spec 4's `not_enough_runs` uses it.
6. **`timeseries` values are not defined precisely.** "Time-persistent statistics sampled every `record_interval`" does not say whether a sample is the state at that instant (queue length now) or the running time-average so far, nor what the metric names are (`till.queue_length` or `till.queue_length.mean`). A replay needs the state at that instant.
7. **The fit endpoint returns no data to draw.** `POST .../data/{file}/fit` returns candidates with fitted fields and a score. A histogram, an ECDF or a values-in-order chart needs the column's values or their bins, and the fitted curves. Drawing them in the interface would put statistics outside the service.
8. **No per-connection counts.** Spec 2 records throughput only at sinks. Showing how much flows along each connection or branch route needs a count per route.

What changes at 1,000 candidates (spec 2 default budget is 50):

- **Volume.** 1,000 candidates × 10 search replications = 10,000 replications, plus confirmation. A per-replication candidates table with 20 metrics is about 200,000 rows: fine for Parquet, too much to send to a chart. Charts use one row per candidate (1,000 points); the per-replication rows are for the CSV export and for one selected candidate.
- **`summary.json` size.** 1,000 candidates with every metric in `summary.json` is around 1 MB. It is better to keep `summary.json` for the best, the baseline and the confirmed candidates, and put all candidates in a table.
- **Events.** A fast model can finish many candidates a second. The client draws at most once a second (as the monitor already does for key numbers); the service may batch.
- **Rendering.** 1,000 dots is easy for SVG or canvas. A parallel-coordinates chart with 1,000 lines over several parameters needs canvas and filtering ("show the best 50"). Dots for integer parameters pile up on the same x value and need jitter or one strip per value.
- **Integer grids.** When the search space is small, spec 2 runs every combination, so "1,000 candidates" usually means continuous or many-valued parameters. With two parameters, a grid of coloured cells (one cell per combination tried) replaces the scatter.
- **Table.** The candidates table must be virtualised (only visible rows in the DOM), sortable and filterable (feasible only, a parameter range).

### 6. The canvas as a results view

- AnyLogic and FlexSim animate items moving through the model; JaamSim places gauges and graphs next to blocks. The M9 interface study (`spec-3-interface-study.md`, "What users praise") quotes users praising these tools for making processes easy to "visualize" and for their animation; FlexSim also shows statistics of the selected object in its properties pane during a run. Showing results on the drawing the user built puts the bottleneck where they already look.
- **Static overlay after a run:** each block shows its key number (utilisation 90%, mean queue 4.2) and a fill colour on a light-to-strong scale, with the bottleneck finding marked by an icon and the word "Bottleneck", so colour is never the only cue (`design-system.md` principle 2). Source: `summary.json` scenario metrics; no gap. The design tokens have no sequential scale yet.
- **Replay:** stepping through time and showing queue length and busy units on each block. It is possible from `timeseries` if gap 6 is closed so that samples are instant states. With the default `record_interval` of `length` / 200, a replay has 200 frames per replication: a slider, not smooth motion.
- **Item animation along connections** needs a per-item event trace, which no spec defines. Without it, moving dots would be invented, not simulated. It belongs in Phase 2.
- **Connection thickness by flow** needs per-route counts (gap 8).

### 7. React chart libraries for an offline Tauri webview

Versions, dates and licences from `npm view <pkg> version license time --json` on 2026-11-06. Sizes from the bundlephobia API (minified, then gzip). The ECharts and uPlot licences were also checked in the published tarballs (`npm pack`, `package/LICENSE`): Apache License 2.0 and MIT respectively.

| Library | Version (date) | Licence | Rendering | 10k to 100k points | Accessibility | Theming by tokens | Size (min / gzip) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Recharts | 3.10.1 (2026-07-25) | MIT | SVG, React components | Slows past a few thousand SVG elements; no sampling | `accessibilityLayer` on by default since 3.0: `role="application"`, tab stop, arrow keys move the tooltip, which is a live region | Props; colours from CSS variables | 562 kB / 150 kB |
| visx (`@visx/xychart`) | 4.0.0 (2026-06-11) | MIT | SVG primitives on d3 | As SVG; canvas only by hand | Whatever the app builds | Full control | 152 kB / 50 kB (xychart only) |
| Apache ECharts (`echarts`) with `echarts-for-react` | 6.1.0 (2026-05-19); wrapper 3.0.6 (2026-01-21) | Apache-2.0; depends on `zrender` 6.1.0 (BSD-3-Clause) and `tslib`; wrapper MIT | Canvas or SVG, chosen per chart | Canvas renderer with `large` mode for scatter, `sampling: 'lttb'` for lines, progressive rendering; the project claims millions of points | `aria` component writes an `aria-label` description from the data or a custom text; `decal` patterns tell series apart without colour; no keyboard navigation of points | Registered theme objects; colours set from tokens at start | 1,115 kB / 368 kB full; tree-shakable by importing only used charts |
| Plotly.js (`plotly.js-dist-min`) | 4.2.0 (2026-10-29) | MIT | SVG; WebGL (`scattergl`) for large scatter | Good with WebGL, which depends on the graphics stack | Limited | Layout templates | 4,652 kB / 1,409 kB |
| uPlot | 1.6.32 (2025-03-14) | MIT | Canvas 2D | Fastest: its README cites 166,650 points in 25 ms, and 10% CPU when streaming 3,600 points at 60 fps against 70% for ECharts | None built in | Options object | 51 kB / 22 kB |
| Observable Plot (`@observablehq/plot`) | 0.6.19 (2026-11-05) | ISC | SVG | SVG limits | `ariaLabel`/`ariaDescription` options on marks | CSS | 381 kB / 127 kB |
| Vega-Lite (+ `vega`, `vega-embed`) | 6.5.0 (2026-10-08); vega 6.4.0; vega-embed 7.3.0 | BSD-3-Clause | SVG or canvas | Canvas renderer handles tens of thousands | ARIA descriptions generated from the spec | Config object | 281 kB + 519 kB / 90 kB + 182 kB |
| Nivo (`@nivo/*`) | 0.99.0 (2025-05-23) | MIT | SVG, some canvas variants | Canvas variants only | Some ARIA props per chart | Theme object | `@nivo/line` 285 kB / 96 kB |

Points that decide the choice:

- **No WebGL.** `design-system.md` principle 3 says no effect may depend on graphics hardware, and Tauri on Linux uses WebKitGTK, whose WebGL depends on the system's drivers (`spec-3-framework-check.md`). This rules out Plotly's fast mode and any WebGL plotter.
- **Chart types needed.** Dot strips with jitter, box plots, histograms, step lines, bands, scatter with selection, heat grids, parallel coordinates. ECharts has all of these built in (`boxplot`, `scatter`, `heatmap`, `parallel`, line `step`, `areaStyle` bands, `brush` selection, `dataZoom`). Recharts has no box plot, heat grid or parallel coordinates. uPlot has no box plot, heat grid or parallel coordinates either.
- **Accessibility is mostly ours in any library.** `accessibility.md` already requires a data table beside every chart. ECharts adds a description and decal patterns; Recharts adds arrow-key reading. Neither replaces the table.
- **One library is simpler** to theme, test and learn than two. ECharts' canvas mode covers the 1,000-candidate scatter and 100,000-row time series without a second library. uPlot stays in reserve if measured performance on the low tier is short for live time series.
- **Licences.** Apache-2.0, MIT, BSD-3-Clause and ISC are all compatible with distributing the product under AGPL-3.0. Apache-2.0 requires keeping its licence and any `NOTICE` file in the distribution.

### 8. Optimization (linear) models

`summary.json` for an `optimization` model holds `status`, `objective`, `variables` and, per constraint, `tight` and `slack`. With the model file's `rhs`, the amount used of each limit is `rhs` minus `slack` for a `<=` constraint: a bar per resource against its limit needs no new data. For a model with exactly two continuous variables (the product mix), the classic "feasible region" picture can be drawn by shading each constraint's half-plane from its two axis intercepts and placing HiGHS's answer as a point; no vertices are computed, so no linear system is solved in product code (Build guide rule 7). "What if a limit changes" (shadow prices) needs dual values, which spec 2 does not report; that is a later extension.

## Sources

- AnyLogic Help, "Optimization" (default optimization UI: Current and Best table; chart of Current, Best feasible and Best infeasible objective by simulation): https://anylogic.help/anylogic/experiments/optimization.html
- AnyLogic Help, "Parameter variation": https://www.anylogic.help/anylogic/experiments/parameter-variation.html ; "Charts" (AnyLogic Cloud multi-run charts): https://www.anylogic.help/cloud/experiment/charts.html ; tutorial "Optimizing the strategy" (500 runs): https://www.anylogic.help/tutorials/system-dynamics/13-optimizing-strategy.html
- J. S. Smith and D. T. Sturrock, *Simio and Simulation: Modeling, Analysis, Applications*, ch. 4 "First Model" (SMORE plots, percentiles, 500 replications): https://textbook.simio.com/SASMAA7/ch-first-model.html
- R. Thiesing, "Recent innovations in Simio", WSC 2014 (SMORE plot elements; B. L. Nelson 2008, MORE plots): https://informs-sim.org/wsc14papers/includes/files/479.pdf
- FlexSim documentation, "The Performance Measure Results Window" (24.2): https://docs.flexsim.com/en/24.2/Reference/Tools/PerformanceMeasureResults/PerformanceMeasuresResults.html ; "The Experimenter and Optimizer" (20.2): https://docs.flexsim.com/en/20.2/Reference/Tools/ExperimenterOptimizer/ExperimenterOptimizer.html ; "Scenario Chart" (19.2): https://docs.flexsim.com/en/19.2/Reference/Dashboard/Charts/ScenarioChart/ScenarioChart.html
- M. D. Rossetti, *Simulation Modeling and Arena*, ch. 8 (Process Analyzer box-whiskers chart): https://rossetti.github.io/RossettiArenaBook/08-Chapter8.html ; Appendix B (Input Analyzer, P-P and Q-Q plots, bin sensitivity): https://rossetti.github.io/RossettiArenaBook/10-AppDistributionFitting.html
- Arena course notes on Output Analyzer and Process Analyzer "Identify Best Scenarios" (A. Sencer, after Kelton et al., *Simulation with Arena*): https://studylib.net/doc/5804502/chapter-6 ; Input Analyzer fitted curve drawn on the histogram: https://studylib.net/doc/5840023/
- JaamSim User Manual (2021-04), sections 3.2.3 "Adding Bar Gauges" and 3.2.4 "Adding a Graph": https://jaamsim.com/docs/JaamSim%20User%20Manual%202021-04.pdf
- Optuna documentation, "Quick Visualization for Hyperparameter Optimization Analysis": https://optuna.readthedocs.io/en/stable/tutorial/10_key_features/005_visualization.html ; `optuna.visualization` reference: https://optuna.readthedocs.io/en/stable/reference/visualization/index.html ; Optuna Dashboard: https://github.com/optuna/optuna-dashboard
- Ax, "Getting Started" (Utility Progression, arm effects, slice, contour, sensitivity): https://ax.dev/docs/tutorials/getting_started/ ; "Utilizing and Creating Ax Analyses": https://ax.dev/docs/tutorials/analyses/
- L. Padilla, M. Kay and J. Hullman, "Uncertainty Visualization", in *Computational Statistics in Data Science*, Wiley, 2022: http://space.ucmerced.edu/Downloads/publications/Uncertainty_Visualization_Padilla_Kay_Hullman_2022.pdf
- M. Kay, T. Kola, J. Hullman and S. Munson, "When (ish) is my bus? User-centered visualizations of uncertainty in everyday, mobile predictive systems", CHI 2016 (quantile dotplots), cited in the review above.
- M. Fernandes, L. Walls, S. Munson, J. Hullman and M. Kay, "Uncertainty Displays Using Quantile Dotplots or CDFs Improve Transit Decision-Making", CHI 2018: https://doi.org/10.1145/3173574.3173718
- A. Kale, F. Nguyen, M. Kay and J. Hullman, "Hypothetical Outcome Plots Help Untrained Observers Judge Trends in Ambiguous Data", IEEE TVCG 2018: https://doi.org/10.1109/tvcg.2018.2864909
- A. Kale, M. Kay and J. Hullman, "Visual Reasoning Strategies for Effect Size Judgments and Decisions", IEEE TVCG 2020: https://doi.org/10.1109/tvcg.2020.3030335
- L. Padilla, M. Powell, M. Kay and J. Hullman, "Uncertain About Uncertainty", *Frontiers in Psychology*, 2021 (summary of findings on intervals, dotplots and HOPs): https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2020.579267/full
- Apache ECharts handbook, "Aria" (descriptions and decal patterns): https://echarts.apache.org/handbook/en/best-practices/aria/ ; option reference (`series-scatter.large`, `series-line.sampling`, `progressive`): https://echarts.apache.org/en/option.html ; home page (canvas and SVG, progressive rendering): https://echarts.apache.org/en/
- "ECharts aria and Decal Patterns" (no keyboard navigation of points; SVG versus canvas): https://www.accessible-data-interfaces.com/accessible-data-component-libraries/chart-library-accessibility/echarts-aria-and-decal-patterns/
- Recharts wiki, "3.0 migration guide" and "Recharts and accessibility" (`accessibilityLayer` on by default): https://github.com/recharts/recharts/wiki/3.0-migration-guide , https://github.com/recharts/recharts/wiki/Recharts-and-accessibility
- uPlot README (size, Canvas 2D, benchmark figures, MIT): https://github.com/leeoniya/uPlot
- npm registry metadata, read with `npm view <pkg> version license time --json` and `npm view <pkg> dependencies` on 2026-11-06, for `recharts`, `@visx/xychart`, `echarts`, `echarts-for-react`, `zrender`, `plotly.js-dist-min`, `uplot`, `@observablehq/plot`, `vega-lite`, `vega-embed`, `@nivo/core`; licence files read from `npm pack echarts@6.1.0` and `npm pack uplot@1.6.32`.
- Bundle sizes: bundlephobia API, `https://bundlephobia.com/api/size?package=<pkg>@<version>`, read 2026-11-06.
- Repository: `docs/specs/1-model-format.md` ("Experiments", "Division of labour", "Run folder and results"), `docs/specs/2-core-engine.md` ("Statistic definitions", "Optimization model layout", "Simulation-based optimization"), `docs/specs/3-desktop-app.md` ("Screens", "Endpoints", "Progress events"), `docs/specs/4-content-and-ai.md` ("Finding rules"), `docs/design/wireframes/03-data.svg`, `05-run-monitor.svg`, `06-results.svg`, `docs/design/flows.md`, `docs/design/design-system.md`, `docs/design/accessibility.md`, `docs/research/spec-3-framework-check.md`, `docs/research/spec-3-interface-study.md`.

## Decision

All items below are **proposals for the owner**. No spec, wireframe or design file was changed. Accepted items go into spec 1, 2 or 3 with a dated "Changes in this version" line, into the wireframes, and into `DECISIONS.md`, in the same change.

### A. Chart library

Use **Apache ECharts 6.1.0** (`echarts`, Apache-2.0, with `zrender` 6.1.0, BSD-3-Clause) through **`echarts-for-react` 3.0.6** (MIT), imported per chart type to keep the bundle small. Canvas renderer for the large scatter, the time series and parallel coordinates; SVG renderer for small charts and the PDF export. `aria` descriptions written by us from the finding text, not generated; `decal` patterns on; colours read from `tokens.json`. Every chart keeps its data table (`accessibility.md`). No WebGL. Keep **uPlot 1.6.32** (MIT) as the fallback for live time series if the M9 performance check on the low tier fails. Record both in `DECISIONS.md` with their licences when M9 code starts; ship the ECharts `LICENSE` and `NOTICE` in the installer.

### B. Charts per screen

Each entry gives the question it answers, its data source, and its caption.

**Data screen** (`03-data.svg`, beside the fit table)

| Chart | Question | Data source | Caption |
| --- | --- | --- | --- |
| Histogram of the column with the chosen fit drawn on top (others on toggle) | "Does this distribution look like my data?" | Gap 7: fit response needs bins and curves | "Bars: your data. Line: the fitted {distribution}. A good fit follows the bars." |
| Share-below staircase (ECDF) with the fitted curve | "How close is the fit, without depending on bar widths?" | Gap 7 | "For each value, the share of your data below it. The closer the two lines, the better the fit." |
| Values in file order | "Does my data change over time, for example busier at lunch?" | Gap 7 | "Your values in the order they appear in the file. A clear trend means one distribution may not describe it." |
| Q-Q plot (Learn mode and "More charts" only) | "Does the fit hold in the tails?" | Gap 7 | "Points on the diagonal mean the fit matches your data, including rare long gaps." |

**Experiment screen** (`04-experiment.svg`)

| Chart | Question | Data source | Caption |
| --- | --- | --- | --- |
| No chart required. A line of text under Search: "{n} combinations: all will be run" or "{n} combinations: {budget} will be tried" | "How big is my search?" | Experiment parameters (`min`, `max`, `type`) and `budget`; spec 2 rule | as given |
| Optional: interval shrinkage from the last run of this experiment | "How many replications do I need?" | `replications` table of the last run; see "Results" convergence row | "With more replications the range narrows. Your last run: ±{half_width} with {n}." |

**Run monitor, plain run** (`05-run-monitor.svg`)

| Chart | Question | Data source | Caption |
| --- | --- | --- | --- |
| Progress bar (exists) | "How long is left?" | `progress` event | the service's message |
| A small "value so far" line beside each live key number | "Is the estimate settling down?" | Successive `metrics` events, kept by the client | "Estimate as the run goes on. Final values and their ranges are on the Results screen." |

**Run monitor, search run** (new panel; the wireframe needs a search variant)

| Chart | Question | Data source | Caption |
| --- | --- | --- | --- |
| Progress: "Candidate {k} of {budget}" then "Checking the best {m} with {replications} replications" | "Where is the search?" | `progress` event message (exists); stage from the proposed `candidate` event | as given |
| Best-so-far chart: a dot per candidate (filled if within limits, hollow if not), a step line for the best within limits | "Is the search still finding better settings?" | Gap 1 and 2: proposed `candidate` event | "Each dot is one setting tried. The line is the best found so far that meets your limits. A flat line means few improvements lately." |
| Best so far card: settings and objective | "What is winning now?" | Proposed `candidate` event | "Best so far (not yet checked): {settings}, {metric} {value}." |

**Results, process run** (`06-results.svg`, after findings and key numbers)

| Chart | Question | Data source | Caption |
| --- | --- | --- | --- |
| Utilisation per server, bars with a marker at 85% | "Which station is busiest?" | `summary.json` metrics | "Share of time each station is busy. Above 85% (dashed line), queues grow quickly." |
| Replication dot strip per key metric and scenario, with the mean and 95% interval as a thin overlay (box plot when replications exceed 100) | "How much do results vary from run to run, and how sure is the average?" | `replications` table; mean and half-width from `summary.json` | "Each dot is one run of the model. The bar shows where the true average probably lies (95%)." |
| Scenario difference chart: one interval per metric, a zero line | "Is scenario B really better than A?" | Gap 5: paired differences in `summary.json` | "{B} changes {metric} by {mean} ± {half_width}. If the bar crosses zero, the two cannot be told apart yet." |
| Over time: line of the typical value with a band where the middle 80% of runs were, warm-up shaded | "Does the system settle, or does a queue keep growing?" | `timeseries` table; gap 6 for the meaning of a sample | "Typical value over the run. The band shows where most runs were. Grey: warm-up, not counted." |
| Interval shrinkage with replications | "Are {n} replications enough?" | `replications` table; the running half-width needs the t quantile, so the service computes it (a derived view, or a `convergence` table; owner to choose) | "The range narrows as replications are added. About {n_required} would give ±10%." (ties to `not_enough_runs`) |

**Results, search run** (new section; leads with the `optimization_result` finding)

| Chart | Question | Data source | Caption |
| --- | --- | --- | --- |
| Before and after: baseline and best confirmed, each with its interval | "How much better is the best, and is it really better?" | `summary.json` `search.objective` and `separated`; intervals need gap 3 | "Your current settings against the best found, each checked with {replications} replications." |
| Confirmed candidates: interval per confirmed candidate, the best marked | "Were the top few close?" | Gap 3 (confirmed means and half-widths) | "These settings were re-run to check them. Overlapping bars mean they perform about the same." |
| Best-so-far chart (as in the monitor), all candidates | "How did the search go?" | Gap 3 or 4 | as in the monitor |
| Effect of each searched parameter: objective against parameter value, one dot per candidate (jittered strips for integer parameters) | "What happens when I change {parameter}?" | Gap 3 or 4 | "Each dot is one setting tried. Look for where the dots are lowest (or highest)." |
| Two parameters: a grid of cells coloured by mean objective, value printed in each cell, hatched where limits are broken | "Which combination works best?" | Gap 3 or 4 | "Each cell is one combination tried. Hatched cells break a limit." |
| Three or more parameters (under "More charts"): parallel lines, the best 50 highlighted, filterable | "Which combinations do the good settings share?" | Gap 4 | "Each line is one setting tried, across all parameters. Dark lines are the best 50." |
| Candidates table: virtualised, sortable, filter "within limits only", with "Use these settings" (adds a scenario) and "Export CSV" | "How do I find and use one of the 1,000 trials?" | Gap 4 | none (table) |

Parameter importance and timeline views from Optuna are not proposed: importance needs a fitted model, and the timeline answers a developer's question.

**Results, optimization model** (no experiments)

| Chart | Question | Data source | Caption |
| --- | --- | --- | --- |
| Variable values, bars | "What should I make or do?" | `summary.json` `variables` | "Best plan: {values}." |
| Limit use: one bar per constraint against its limit, "Fully used" label where `tight` | "Which limits hold me back?" | `summary.json` `constraints` with the model's `rhs` | "Fully used limits are the ones holding the result back." |
| Two continuous variables only (Learn mode): feasible region with the best point | "Why is this the best point?" | Model file coefficients and the solution; drawn by shading half-planes, no vertices computed | "The shaded area is every plan that respects all limits. The dot is the best one." |

**Canvas overlay after a run** (toggle "Show results on the model")

| Overlay | Question | Data source | Caption or label |
| --- | --- | --- | --- |
| Each block shows its key number and a fill from light to strong by utilisation; the bottleneck has an icon and the word "Bottleneck" | "Where is the problem in my process?" | `summary.json` metrics; the `bottleneck` finding | "Busy {utilisation}" on the block; legend "Darker blocks are busier" |
| Queue length badge on each server and queue | "Where do items wait?" | `summary.json` `queue_length.mean` | "Avg queue {n}" |
| Replay slider (later in M9 or M10) | "What happened over time?" | `timeseries`, after gap 6 is closed | "Time {t}. Queue and busy counts at this moment, run {r}." |
| Not proposed for Phase 1: moving items along connections, connection thickness by flow | | Needs an item trace and per-route counts (gap 8) | |

The design tokens need a sequential scale for the utilisation fill, with contrast checked by `scripts/contrast.py`.

### C. Spec additions proposed (smallest set)

1. **Spec 3 "Progress events": a `candidate` event**, sent once per finished candidate evaluation of a search:
   `{"type": "candidate", "index": 17, "stage": "search", "set": {"tills": 3}, "objective": {"metric": "till.wait.mean", "mean": 262.4, "half_width": 21.0}, "feasible": true, "best_index": 12}`
   `stage` is `search` or `confirm`; `index` is the evaluation order, 0 for the baseline. On connection, after the state and latest `progress`, the stream replays every `candidate` event so far (closes gaps 1 and 2).
2. **Spec 2 "Simulation-based optimization", `search.candidates`**: add `index`, and split `metrics` into `search` (means and half-widths at search replications) and `confirm` (the same at full replications, or null), so the meaning of each value is stated (gap 3). Optionally keep only confirmed candidates in `summary.json` once a `candidates` table exists, to bound its size.
3. **Spec 1 "Run folder and results": a `candidates` table** for search runs, accepted by `GET /v1/runs/{rid}/tables/{name}`: columns `candidate` (int, the `index`), `stage`, `replication`, `metric`, `value`, `unit`. Spec 1 also states that `replications` and `timeseries` of a search run hold the confirmation stage only (gap 4). `tests/service/test_routes.py` does not change: the route already exists; only its allowed names grow.
4. **Spec 1 `summary.json`: a `differences` object** per scenario pair and metric, `{mean, half_width, separated}` (gap 5).
5. **Spec 2 "Statistic definitions": define a `timeseries` sample** as the state at that instant (number waiting, busy units over available capacity, items in system, stock), and name the series (gap 6).
6. **Spec 3 `POST .../data/{file}/fit` response**: add `histogram {edges, counts}` (bin rule fixed by the service), `ecdf` (at most 500 points), `series` (the column in file order, at most 2,000 points, downsampled), and per candidate `pdf` and `cdf` points, all computed by the service (gap 7).
7. **Spec 3 "Progress events" `metrics`** (optional): add `replications_done`, so the monitor can say "after 12 of 30 runs".
8. **Later, not Phase 1**: per-route counts at branches (gap 8), an item event trace for animation, and dual values for "what if a limit changes".

### D. Design work this adds before M9 code

- Wireframe variants: Data with charts; Run monitor for a search; Results for a search run; Results for an optimization model; the canvas overlay. These follow the owner's decision on this note.
- A chart section in `design-system.md` (series colours already exist; add the sequential scale, hollow-versus-filled for limits, hatch for broken limits) and its contrast check.
- A performance check at M9: 1,000 candidates in the best-so-far chart and 100,000 time-series points drawn on the low tier within the 100 ms target used for the canvas.

## Tested

- `npm view` was run for every library in the table on 2026-11-06; versions, dates and licences are as returned. `npm view echarts dependencies` returned `tslib` and `zrender` 6.1.0; `npm view zrender@6.1.0 license` returned BSD-3-Clause.
- `npm pack echarts@6.1.0` and `npm pack uplot@1.6.32` were downloaded into a scratch folder and `package/LICENSE` read: Apache License 2.0 and MIT.
- Bundle sizes were read from the bundlephobia API for the versions listed.
- Not tested: no chart library was installed in `ui/` or rendered in Tauri; performance figures are the projects' own claims (uPlot README, ECharts home page). The ECharts canvas renderer on WebKitGTK and WebView2, the `aria` and `decal` output with a screen reader, and the 1,000-candidate and 100,000-point cases are to be measured at M9 under the performance protocol.
- The spec gaps were found by reading the cited spec sections; no code exists yet for runs, searches or the service, so none was confirmed by running.
