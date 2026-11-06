# User flows

Learn mode and Build mode, from first launch to first result. This serves spec 3 "Design before building" (first item). The screens are in `wireframes/`; canvas actions are in `canvas-interactions.md`.

Both modes use the same canvas and the same model file (spec 4 "Learn and Build modes"). Every step below names the screen it happens on and the API call behind it, so the flows can be checked against spec 3 "Endpoints" and turned into the M9 end-to-end tests.

## Users and their goal

| User (spec 0) | Arrives wanting to | Mode | First result looks like |
| --- | --- | --- | --- |
| Student or self-learner | Understand a method by building and running a model | Learn | The coffee shop's results: the lesson's explanation, any findings, and the till's average wait and utilization |
| Small or medium business | Answer a real question about a process | Build | Findings for the template closest to their question, with their own numbers or estimates |

Both must reach a first result with no code (spec 0 success measure: a first template model in under 30 minutes, measured at M10).

## Shared start: first launch

```text
Install -> Start the app -> [Service starts] -> First-start notice -> Home
```

1. **The app starts the service** on demand (spec 3 "Service rules", Lifetime) and reads `service.json` to find its port and token. A splash line says "Starting the engine service…". If the service is not ready within 5 seconds (spec 3 performance target), the line changes to "Still starting…" and a "Show details" link reveals the service log.
2. **First-start notice** (`wireframes/08-first-start-notice.svg`), shown once (spec 3 "First start"). It says, in three short paragraphs:
   - what the tool does: "Build a model of a process, run it many times, and see where the waits and bottlenecks are. No code needed."
   - that results are estimates: "Results are estimates from a simulation. Use them to support your judgement, not to replace it."
   - where the licence is: "This is free software under the GNU AGPL version 3. Read the licence any time in Settings, About."
   One button, "Continue". The notice is not shown again; Settings, About repeats its text.
3. **The service detects the hardware** on its first start and sets the tier (spec 3 "Hardware tiers"); nothing is asked of the user. Settings shows it.
4. **Home** (`wireframes/02-home.svg`): two large entries, "Learn" and "Build"; below them the template gallery (`GET /v1/templates`) and recent projects (`GET /v1/projects`). Secondary links: "New empty project" and "Open a project folder" (`POST /v1/projects/open`).

## Learn mode

```text
Home -> Learn -> Pick a template -> Canvas with step card -> steps 1..n -> Exercise: change + predict -> Run -> Run monitor -> Results (explanation + findings)
```

| # | Screen | User does | System does | API |
| --- | --- | --- | --- | --- |
| L1 | Home | Chooses "Learn" | Shows the template gallery filtered to lessons, ordered by audience: "Students" and "Both" first; each card shows title, summary, audience and estimated minutes (spec 4 `template.json`) | `GET /v1/templates` |
| L2 | Home | Picks "Coffee shop queue" | Creates a project from the template | `POST /v1/projects {name, template}` |
| L3 | Canvas | Reads step 1 | Opens the Canvas with the step card (`wireframes/01b-canvas-learn.svg`); highlights the step's block (`canvas-interactions.md`, "Learn mode on the canvas") | `GET /v1/templates/{tid}` (lesson text), `GET .../model`, events socket |
| L4 | Canvas | Presses Next through the steps; may click blocks and look at their settings | Moves the highlight; the side panel shows the highlighted block's settings | none, until the user edits |
| L5 | Canvas | Reaches the exercise: makes the change it asks for, for example setting `tills` from 1 to 2 | Sends the edit; validates 500 ms later | `POST .../model/edits`, `POST .../validate` |
| L6 | Canvas | Picks a prediction from the list ("The wait will fall by about half", ...) | Enables "Run" in the step card | none |
| L7 | Canvas | Presses Run | Starts the run of the template's experiment; opens the Run monitor | `POST /v1/projects/{pid}/runs {experiment_id}` |
| L8 | Run monitor | Watches progress; may leave and come back | Shows progress, live key numbers and Cancel (`wireframes/05-run-monitor.svg`) | `GET /v1/runs/{rid}/events` |
| L9 | Results | Reads the result | Shows the exercise explanation first, with "You predicted: …", then the findings, then charts and tables, then the footer (`wireframes/06-results.svg`) | `GET /v1/runs/{rid}/summary`, `GET .../tables/{name}` |
| L10 | Results | Chooses "Try another lesson" or "Change the model and run again" | Returns to Home or the Canvas | |

Notes:

- **No dead ends.** The user can leave the lesson at any step ("Exit lesson" in the step card); the project stays and opens as an ordinary project. The lesson can be restarted from Home; the step reached is not stored, because the project folder holds only what spec 3 lists.
- **No findings is a result too.** The coffee shop is the silent model for `bottleneck` and `not_enough_runs` (spec 4), so its Results may show no findings. The findings area then says "No findings for this run." and the key numbers follow.
- **Run is available before the exercise.** The top bar's Run button works throughout, as in Build mode; the step card's Run is a shortcut to the same call.
- **If validation shows errors** after the exercise change, the step card's Run is disabled with the same reason as the top bar (`canvas-interactions.md`, "Running").

## Build mode

Build mode is a fixed form, not a conversation (spec 4 "Build mode").

```text
Home -> Build -> Q1 "What do you want to find out?" -> (Q1b for the optimization answer) -> Q2 "Do you have data?"
   -> "No, I will estimate" -> Canvas with the template's parameters open -> edit numbers -> Run -> Run monitor -> Results
   -> "Yes, import a file"  -> Data -> import, map, fit -> Canvas -> Run -> Run monitor -> Results
```

| # | Screen | User does | System does | API |
| --- | --- | --- | --- | --- |
| B1 | Home | Chooses "Build" | Opens the Build form, step 1 (`wireframes/02b-build-form.svg`) | |
| B2 | Build form | Answers "What do you want to find out?" with one of six answers (spec 4): how long will people or items wait; where is the bottleneck; how much does downtime cost; how many staff or machines do I need; how much stock should I hold; what mix, plan or rota is best | Shows the template each answer opens beside the answer: Coffee shop, Three-machine line, Machine breakdowns, How many machines, Inventory reorder point, and for the last answer a second question | |
| B2b | Build form | For "what mix, plan or rota is best", answers the second question: "a product mix", "a transport plan" or "a staff rota" | Selects Product mix, Transport plan or Staff rota (spec 4) | |
| B3 | Build form | Names the project (default: the template title) and answers "Do you have data?" | | |
| B4a | Canvas | Chose "No, I will estimate" | Creates the project from the template and opens the Canvas with nothing selected, so the side panel shows the model's parameters (spec 4: "Canvas with the template's parameters open") | `POST /v1/projects {name, template}` |
| B4b | Data | Chose "Yes, import a file" | Creates the project and opens the Data screen (`wireframes/03-data.svg`) | `POST /v1/projects` |
| B5b | Data | Drops or picks a CSV or Excel file | Uploads it; shows columns, types and a preview | `POST /v1/projects/{pid}/data` |
| B6b | Data | Picks a column (for example "minutes between arrivals") and presses "Fit a distribution" | Lists candidate distributions with their fitted fields and fit score, best first | `POST .../data/{file}/fit {column}` |
| B7b | Data | Picks a candidate and "Use for…" a block setting, for example `arrivals` interarrival | Sets that setting to the fitted distribution, or to `empirical` with a data reference if the user chooses "Use the data as it is" | `POST .../model/edits` (`set_setting`) |
| B8 | Canvas | Changes numbers in the side panel; may add or remove blocks | Saves and validates after each change | `POST .../model/edits`, `POST .../validate` |
| B9 | Canvas or Experiment | Optionally sets run length, replications, scenarios on the Experiment screen (`wireframes/04-experiment.svg`) | Template experiments are already valid, so this step can be skipped | `POST .../model/edits` (`set_experiment`, `set_scenario`) |
| B10 | Canvas | Presses Run | Starts the run; opens the Run monitor | `POST /v1/projects/{pid}/runs` |
| B11 | Run monitor | Waits | Progress, live key numbers | `GET /v1/runs/{rid}/events` |
| B12 | Results | Reads findings first, then charts and tables; exports CSV, PDF or the project zip | `wireframes/06-results.svg` | `GET /v1/runs/{rid}/summary`, `GET .../tables/{name}` |

Notes:

- **Build mode never requires a data file** (spec 4). Path B4a reaches a result changing only parameters, which is the spec 4 acceptance row "A Build-mode user without data reaches a completed run changing only parameters".
- **The data path rejoins the canvas.** After B7b the Data screen offers "Go to the canvas"; the user can import more files first.
- **Optimization answers** (Product mix, Transport plan, Staff rota) open an optimization model. Its Canvas screen is the variables, objective and constraints form (`canvas-interactions.md`, "The model and the canvas"); Run sends no `experiment_id`; Results shows the variable values, the objective and which constraints are tight (spec 2), with the `optimization_result` finding first.
- **"How many machines?"** opens a process model whose experiment has a `search` (spec 2 "Simulation-based optimization"); the Run monitor shows the progress messages the service sends, and Results leads with the `optimization_result` finding.

## Returning users

- **Home → a recent project** opens the Canvas at the model's last state. If a run of that project is still going, the top bar shows "Run in progress" with a link to the Run monitor (spec 3 acceptance: "Reopening the interface mid-run shows its progress").
- **An assistant built the model** (spec 4 "Visible to the user"): the project appears in Home's recent list (`GET /v1/projects`); opening it shows the model on the Canvas like any other.

## Error and edge paths

| Situation | What the user sees |
| --- | --- |
| The service does not start | The splash line: "The engine service did not start." with "Show details" (the log) and "Try again" |
| The service stops while the app is open | A banner on every screen: "Lost contact with the engine service. Reconnecting…"; the Canvas is read-only until it returns; runs continue, because runs belong to the service (spec 3 "Runs outlive the interface") |
| The template fails to create | A notice with the error's message; the user stays on Home |
| The imported file cannot be read | The Data screen shows the service's message under the file and keeps the previous files |
| The model has errors | Run disabled with "N errors. Fix them to run." (`canvas-interactions.md`, "Running") |
| A run fails | The Run monitor shows the state and the issue (E190, E192) in plain language, with "Open the log" and "Back to the canvas" |
| The user cancels a run | The Run monitor asks "Stop this run?" with "Stop run" and "Keep running"; after stopping it shows the cancelled state |

## Traceability

| Flow step | Spec |
| --- | --- |
| First-start notice | Spec 3 "Service rules", First start |
| Tier detection | Spec 3 "Hardware tiers" |
| Learn walkthrough, highlight, exercise | Spec 4 "Learn and Build modes", "Template package" |
| Build questions and template mapping | Spec 4 "Build mode" |
| Data import, fit, use | Spec 3 Screen 3 and "Endpoints"; spec 1 `empirical` with `data` |
| Results order and footer | Spec 3 Screen 6 |
| Every call | Spec 3 "Endpoints" (no private channel, spec 3 "API") |
