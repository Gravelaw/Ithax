# Teaching practice (spec 4, M10)

## Question

Spec 4 "Research before building", M10 · Teaching practice: how are simulation and
operations research taught, and which worked examples recur across textbooks? The answer
shapes the Phase 1 templates (spec 4 "Template library"): what each lesson step does, what
the closing exercise asks, and which problems the ten templates should be.

## Finding

**How simulation is taught.** A survey of the authors and chairs of the Winter Simulation
Conference's simulation education tracks from 2000 to 2017 (Mesquita, Silva and Tomotani
2019) found that teachers weigh theory (probability and statistics, output analysis)
against practice, value simulation projects on real problems, and favour active learning;
it also lists students' motivation, their modelling skills, little time and hard access to
teaching cases as the difficulties. Most published simulation-education work is about
discrete-event simulation. The common pattern of the standard texts is a small, fully
worked model first, then the same model changed by the student:

- Law, *Simulation Modeling and Analysis*, chapter 1: a single-server queue (section 1.4),
  then an (s, S) inventory system (section 1.5), both worked by hand and in code before
  any general theory.
- Banks, Carson, Nelson and Nicol, *Discrete-Event System Simulation*, chapter 2: a
  single-checkout grocery store simulated by hand in a table for 100 customers, then
  inventory and reliability examples.
- Kelton, Sadowski and Zupick, *Simulation with Arena*, chapter 4: an electronic assembly
  and test system (model 4-1), then the same system enhanced with resource schedules,
  states and failures (model 4-2).
- Hopp and Spearman, *Factory Physics*, chapter 7: the "Penny Fab" line, used to teach the
  bottleneck rate, cycle time and Little's law (WIP = TH × CT) before any variability.

**How operations research is taught.** Hillier and Lieberman, *Introduction to Operations
Research*, opens linear programming with one prototype, the Wyndor Glass product mix (two
products, three plants, maximize 3x₁ + 5x₂, optimum (2, 6)), solved graphically before
the simplex method; Winston's *Operations Research* teaches integer programming with a
post office staff rota (full-time staff working five consecutive days, minimize the number
hired). Transport problems (supply points to demand points at least cost) follow linear
programming in both. The examples are deliberately small enough to check by hand or by
enumeration.

**Why worked examples and predictions.** The worked-example effect (Sweller and Cooper;
Sweller 1988; reviewed by Atkinson, Derry, Renkl and Wortham 2000) is the most studied
cognitive-load effect: novices learn more from studying a worked example than from solving
the same problem unaided, and the benefit fades as expertise grows (expertise reversal).
Integrating explanation with the picture it explains, rather than putting them apart,
reduces load further (split attention, Chandler and Sweller). Predict–observe–explain
(White and Gunstone 1992) asks learners to predict an outcome and say why, observe it, then
reconcile the two; studies have paired it with computer simulations for the observe step
(Kearney, Treagust, Yeo and Zadnik), and writing the prediction first gives the learner a
reason to want the answer.

**Examples that recur.** Across these texts the same few problems recur: a single-server
queue (a bank teller, a till, a checkout), servers in parallel (the M/M/c), a production
line with a bottleneck, machines that fail and are repaired, routing through a branch, an
(s, S) or reorder-point inventory, a two-product mix, a transport plan, a staff rota and a
"how many servers?" question. That is spec 4's list of ten; none needs to change.

## Sources

- M. A. de Mesquita, B. C. da Silva, J. V. Tomotani, "Simulation education: a survey of
  faculty and practitioners", Proceedings of the 2019 Winter Simulation Conference,
  pp. 3344 ff., <https://www.informs-sim.org/wsc19papers/364.pdf> (read 2026-11-09:
  abstract and introduction).
- A. M. Law, *Simulation Modeling and Analysis*, chapter 1 contents (4th edition, sections
  1.4 and 1.5), table of contents at <https://sisis.rz.htw-berlin.de/inh2007/12355751.pdf>;
  chapter 1 slides at <https://www.dmi.unict.it/messina/didat/DES_17_18/chapter1.pdf>.
- J. Banks, J. S. Carson, B. L. Nelson, D. M. Nicol, *Discrete-Event System Simulation*,
  chapter 2 "Simulation Examples", as summarised by course slides at
  <https://www.sambuz.com/doc/simulation-examples-ppt-presentation-785939>.
- W. D. Kelton, R. P. Sadowski, N. B. Zupick, *Simulation with Arena*, 6th edition (2014),
  chapter 4, models 4-1 and 4-2, as listed by the slides at
  <https://ls4-www.cs.tu-dortmund.de/Lehre/07-41128/Arena-Slides2.pdf>.
- W. J. Hopp, M. L. Spearman, *Factory Physics*, chapter 7 (Penny Fab, Little's law), as
  summarised at <https://neoprimate.github.io/IEOR/supply-chain/manufacturing/factory-physics/index.html>.
- F. S. Hillier, G. J. Lieberman, *Introduction to Operations Research*, section 3.1
  (Wyndor Glass), course notes at <https://people.ohio.edu/melkonia/math4620/chapter3.pdf>.
- W. L. Winston, *Operations Research: Applications and Algorithms* (post office problem),
  as credited by <https://hakank.org/picat/post_office_problem2.pi>.
- J. Sweller, "Cognitive load during problem solving: effects on learning", *Cognitive
  Science* 12(2), 257–285 (1988); R. K. Atkinson, S. J. Derry, A. Renkl, D. Wortham,
  "Learning from examples", *Review of Educational Research* 70, 181–214 (2000); overview
  at <https://en.wikipedia.org/wiki/Worked-example_effect>.
- R. White, R. Gunstone, *Probing Understanding* (1992), the predict–observe–explain
  task, described at <https://arbs.nzcer.org.nz/node/7187>; M. Kearney, D. Treagust,
  S. Yeo, M. Zadnik, multimedia-supported POE tasks,
  <https://opus.lib.uts.edu.au/bitstream/10453/4899/1/2004004422.pdf>.

The textbooks were not read in full: their chapter structure and examples are taken from
their tables of contents and from course material that follows them. No text or number of
theirs is copied into a template (see `spec-4-template-sources.md`).

## Decision

The template format follows these findings (spec 4 "Template package", AKS-122, owner to
confirm):

- **A worked example first.** Each template opens on a model that already runs and gives
  the theory's answer; the lesson walks through it one block at a time, a step per block
  that matters, each step naming the block it highlights (split attention: the text sits
  next to the block it explains) and kept to 80 words, as spec 4 already says.
- **Predict, then observe, then explain.** The last step is an exercise in three parts:
  the change to make, two to four predictions to choose from with exactly one right, and
  the explanation shown after the run. The right prediction is checked by running the
  changed model in the template test, so the explanation never states a result the engine
  does not give.
- **Theory beside the simulation.** Where a closed form exists (M/M/1, Erlang C, Little's
  law, availability), the lesson names it and the template's `expected.json` checks it,
  so the learner sees simulation and theory agree before trusting simulation where theory
  stops (a blocking buffer, breakdowns while waiting).
- **Spec 4's ten templates stand.** Every one is among the recurring examples above; the
  table needs no change.

## Tested

The three templates of AKS-122 (coffee shop, three-machine line, machine breakdowns) were
written to this structure; `tests/templates/test_templates.py` checks each lesson step
names a component of its model and stays within 80 words, that the exercise has a change,
two to four choices with one marked right, and an explanation, and runs each template and
its exercise against `expected.json` (2026-11-09).
