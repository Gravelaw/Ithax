# Simulated walkthrough: business-user persona (AI, not a real participant)

## Persona

Daniel, 46, operations manager at a family-owned bakery-café chain: four shops and a small central bakery. He is good with Excel (pivot tables, simple formulas) and his POS reports. He does not code. He knows averages, not statistics. He has never used simulation software. He is busy and sceptical, and gives a new tool about 20 minutes.

His question: "At the busiest shop, Saturday mornings have long queues. Do I need a third person on the till, or would a faster coffee machine do more?"

His data: a CSV export from the POS, one row per order, with a timestamp and the minutes from order to hand-over.

Screens seen: 08 (first-start notice), 02 and 02b (Home, Build form), 03 (Data), 01 and 01c (canvas, block states), 04 (Experiment), 05 (Run monitor), 06 (Results), 07 (Settings), and 10 to 12 (the proposed new look). All are static images. The grey ones are wireframes and contain placeholders such as `{score}` and `{minutes}`.

## Think-aloud by task

### Task 1: First launch

"Welcome. 'Build a model of a process, run it many times, and see where the waits and bottlenecks are.' OK, that is roughly my problem. Queues are waits."

"'Results are estimates. Use them to support your judgement, not to replace it.' Fair. I like that it is honest. But it does not tell me how good the estimates are. Good enough to hire someone on?"

"Licence, GNU AGPL version 3. I have no idea what that means. 'Free software' I understand. Free is good. Free also makes me wonder who supports it."

"Who made this? Does my sales data leave my laptop? It does not say. I would want that before I load a POS export."

"Do I trust it with a business decision? Not yet. I trust it enough to try for twenty minutes."

### Task 2: Home and Build

"Learn or Build. I am not here for a lesson. Build: 'Answer a question of your own.' That's me."

"Ten templates. 'Coffee shop queue', marked 'Students'. Hm, is that for schools? I'm a business. 'Staff rota' is Business, but I don't need a rota. 'How many machines?' is Both. And every card says '{minutes} min'. Is that broken?"

"Build, step 1. 'How long will people or items wait?' gives Coffee shop queue. 'How many staff or machines do I need?' gives How many machines. My question is both. It's staff OR a machine. Which one is it?"

"I pick 'How many staff or machines do I need?' because the word staff is there. It opens 'How many machines?'. That sounds like a factory. Would it have a coffee machine in it? I can't tell until I open it."

"There's no 'compare two options' answer. That's what I actually want: option A versus option B."

"Step 2: 'Yes, import a file.' Good, I have one."

"Does the template fit my café? The canvas I see later is arrivals, till, exit. That's one till and nothing else. In my shop, you order and pay at the till, then the barista makes the drink on the machine. The coffee machine is not in this model at all."

### Task 3: Import the CSV and fit the service time

"Import CSV or Excel. Fine. It shows my file, the columns and the first rows. That part I get. It looks like Excel."

"'Fit a distribution to gap_min.' What's a distribution? I'd call it a pattern. Then exponential, weibull, lognormal. Those mean nothing to me."

"Fit score: '{score} (best)'. So there's no number in this one. Even with a number, is high good or low good? Is 0.7 good? I'd want a plain word: good fit, poor fit."

"In the new look there's a chart: bars for my data, a line for the pattern. 'If they match, the pattern is a fair stand-in.' That I understand. I can see whether the line follows the bars. That's the one thing on this screen I'd trust."

"'Use for, Block setting: arrivals · interarrival.' I want the till's service time. Is this a drop-down? What's an interarrival?"

"Wait. My column is minutes from order to hand-over. That includes the time spent waiting for the coffee behind other orders. Is that the 'service time'? I don't know. The tool doesn't ask. If it's the wrong column, everything after is wrong, and nothing warns me."

"Also, I only care about Saturday mornings. My export is the whole month. How do I keep just Saturday 8 to 12? I'd have to do that in Excel first. The tool doesn't say so."

"And I have timestamps. Can it work out how often customers arrive from those? Maybe. It doesn't offer."

### Task 4: Set up 2 vs 3 on the till, and a faster coffee machine

"Canvas. Blocks: source, sink, delay, branch, server, queue, batch… 'sink'? Like a kitchen sink? I guess it's the exit."

"I click the till. 'Capacity: tills', and a button 'Param: on'. I think capacity is how many people are on the till. 'tills' is a word, not a number. Param? I'm guessing that means it can change between runs."

"There's a red box, server_2, 'Error E131'. The text under it is clear enough: the out port isn't connected. I'd delete it. The codes I'd ignore."

"Where do I compare 2 and 3? Not here. I find it on the Experiment screen: 'Scenarios'. The table says one_till = 1, two_tills = 2. So a scenario is a row: one version of the shop. OK, once I see the table, I get it. I'd add a row 'three_tills = 3'. The word 'scenario' I know from planning. The fact that they live on a different screen from the model, I didn't expect."

"Now the coffee machine. There is no coffee machine block. I'd have to add a 'server' after the till, call it machine, and give it a service time. Then to make it faster in one scenario, I'd need to make its mean a 'parameter' and add a column with '+ Add parameter column'. I'm guessing. Nothing tells me that's how to do it."

"And what is faster? The supplier says 'up to 40% faster'. Where do I type that? As a mean in minutes, I think. I'd need to work it out."

"Run length 200 h, warm-up 10 h, 30 replications, seed 12345, confidence 0.95, record interval. I have no idea what to put. My shop is open Saturday 7 to 3, and the rush is 8 to 11. Why 200 hours? I'd leave everything as it is and hope."

"Optimization on the right: 'wait minimize till.wait.mean', 'util till.utilization <= 0.85'. That's code. I'd stay away from that half of the screen."

"At this point I've used about fifteen of my twenty minutes."

### Task 5: Run and Run monitor

"Run. It shows a progress bar: 40%, scenario 1 of 2, replication 12 of 30. Clear enough."

"'Runs continue if the window closes; reopening shows progress.' Good. That's the line I wanted. I can go and make a coffee."

"But how long will it take? No time left, no 'about 3 minutes'. Started 10:15. Is it ten seconds or an hour?"

"The live numbers say 'default'. But my scenarios were one_till and two_tills. Which is default? Confusing."

"There's a second run queued. Did I click twice? Can I cancel it? Yes, there's a Cancel link. Fine."

"I'd wait about five minutes, maybe ten, if the bar keeps moving. Without an estimate, I'd give up after ten."

### Task 6: Results

"The Results screen I see is for a 'three-machine line', with 'weld'. Not my shop, but I'll imagine."

"Findings at the top: 'weld is the bottleneck: busy 90% of the time, with an average wait of 17.3 min.' That's a sentence. Good. I'd want 'the till is the bottleneck' or 'the coffee machine is the bottleneck'. That would almost answer my question by itself."

"'Not enough runs… plus or minus 4.4 min… About {n_required} replications would be needed for a 10% interval.' I don't understand that. Is the answer wrong? Should I run again? It should just say 'run longer for a firmer answer' and give me a button."

"In the new look: 'Two tills cut the average wait from 4.5 min to 0.25 min.' That's the best thing I've seen. I'd show that line to the owner. But I asked 3 versus 2 and a faster machine. Where's the side-by-side of my three options? I see a table per metric, not per option."

"The 'every repeat run' chart with 1 till, 2 tills, 3 tills is nice. Dots far apart means the answer is solid, I think. But 'log scale', 0.01, 0.1, 1, 10. My owner will ask why the gaps aren't even."

"Would I show the owner? The headline sentence, yes. The rest, no."

"What's missing: cost. A third person costs me about £12 an hour, 5 hours each Saturday. A new machine costs, say, £8,000 once. I need 'option B saves X minutes of wait per customer for Y pounds a week'. Even better: how many customers walk out when the queue is long. That's lost sales. None of that is here. Without it, I'm still doing the sum in Excel."

"Export PDF and Export CSV are there. CSV I can use. Good."

### Task 7: Search over 1,000 trials

"On the Experiment screen the search says Budget 50. You tell me 1,000. I'd guess budget means how many tries."

"Chart: '1,000 trials: best so far'. Lots of dots. Green ones meet my limits, hollow ones break one. A line that steps down. I get that it found something good early, then barely improved after trial 350. So 1,000 was more than needed?"

"The trials table I like. It's like a spreadsheet. Trial 412: 2 tills, 7 to 19, 0.25 min, 38% busy, OK yes. 'Use.'"

"But wait. 'Opening hours'? I didn't ask to change my opening hours. Where did that come from?"

"Trial 633: 3 tills, 0.04 min wait, 'No'. Why no? It's the shortest wait. Which limit did it break? I'd guess too idle at 25% busy, but it doesn't say."

"0.25, 0.27, 0.31 minutes. Is that a real difference or just luck? I can't tell. I'd treat them as the same."

"How would I pick? I'd sort by wait, drop anything with 'No', and then pick the cheapest. But there's no cost column, so 'cheapest' means fewest tills in my head. I'd pick trial 412: two tills. Then I'd ask: does that mean I don't need a third person? It seems to say yes. But the coffee machine wasn't in the search at all."

"'Use copies that trial's settings into the model.' I don't want to change the model. I want to write down a decision."

### Task 8: Grey wireframes versus the new look

"The grey ones look like a form from a council website. Fine, but it feels like a programmer's tool. Code-looking words everywhere: till.wait.mean, gap_min, E131."

"The new look: icons on the blocks, 'Arrivals', 'Till', 'Exit' with capital letters. A red 'Bottleneck' tag right on the till. A ring saying 75%. 'Queue avg 4.5 min' under it. That I'd understand from across the room. A trophy and one sentence for the answer. That looks like something I'd pay for."

"The colours are warm, a bit like a café menu, actually. Charts have plain captions under them: 'Bars: your data. Line: the pattern.' That's how it should talk to me everywhere."

"But the side panel still says 'server · capacity = tills', 'expo… min'. A nice coat of paint on the same words. The look gets me to stay five more minutes. The words decide if I stay."

"Verdict: the new look, clearly. If I could get to that headline sentence for my own three options in twenty minutes, with costs next to it, I'd use it. Today I wouldn't get there."

## Problems found

| # | Screen / file | What confused or blocked | Severity | Suggested fix |
| --- | --- | --- | --- | --- |
| 1 | 04-experiment, 01-canvas | No clear way to model "faster coffee machine" as an option. No machine block in the template; changing a service time per scenario needs a "parameter" he does not know how to make. | Blocker | Offer "Compare options" with a guided "change a time by %" or "add a person" step that creates the scenario column for him. Include a separate drink-making step in the café template. |
| 2 | 03-data | His column is order-to-hand-over time, which includes waiting. The tool lets him use it as service time with no warning. The result would be wrong without him knowing. | Blocker | Ask "Does this time include waiting in the queue?" when a column is used for a service time, and explain the difference in one sentence. Suggest using timestamps for arrivals. |
| 3 | 06-results, 11, 12 | No cost, staffing cost per hour, machine price, or lost customers. He cannot turn minutes of wait into a business decision. | Major | Add optional cost fields (per hour per person, one-off per machine) and a results column "cost per week" or "minutes saved per pound". Consider a "customers who leave" (balking) measure. |
| 4 | 02b-build-form, 02-home | No Build answer fits "compare option A with option B". "How many staff or machines" opens a template called "How many machines?" that sounds like a factory. "Coffee shop queue" is tagged "Students", which suggests it is not for business. | Major | Add "Compare two or more changes" as a Build answer. Drop audience tags or use "Lesson" vs "Ready to use". Show a one-line preview of what the template contains. |
| 5 | 04-experiment | Run length 200 h, warm-up, seed, replications, confidence, record interval: none means anything to him. His real setting is "Saturday 8 to 11". | Major | Lead with "Which hours do you want to study?" and "How sure do you need to be? (quick / standard / thorough)". Hide the rest under "Advanced". |
| 6 | 03-data | "Fit score" has no meaning or scale; candidate names (exponential, weibull, lognormal) are jargon. The wireframe shows `{score}`. | Major | Replace with a plain verdict ("good match", "rough match", "poor match") next to the overlay chart from screen 12. Keep the names under a "details" toggle. |
| 7 | 03-data | No way to filter rows (Saturday mornings only) before fitting. He would have to clean the file in Excel. | Major | Add a simple row filter by day of week and time of day on the Data screen, or at least a note saying to filter first. |
| 8 | 04-experiment, 12 (trials table) | Objective and constraint shown as code (`wait minimize till.wait.mean`, `till.utilization <= 0.85`). Search table varies "Opening hours", which he never chose. Trial 633 is marked "No" with no reason. Budget 50 on screen versus 1,000 trials in the chart. | Major | Write goals as sentences ("Keep the average wait as low as possible; keep staff busy at most 85% of the time"). Show which limit a trial breaks. Show which settings are being searched, in words. |
| 9 | 12 (trials table) | Cannot tell whether 0.25, 0.27 and 0.31 min differ for real. No guidance on how to choose among near-equal trials. | Major | Mark trials whose results overlap the best as "about as good as the best", and suggest the cheapest or simplest of them. |
| 10 | 06-results | "Not enough runs" message uses intervals and `{n_required}` replications. He reads it as "the answer may be wrong" with no next step. | Major | Say "This answer is still rough. Run again with more repeats for a firmer number." Add a button that does it. |
| 11 | 06-results | No side-by-side of his scenarios on one screen. Key numbers are per metric. | Major | Add a scenario comparison table: one row per option, columns wait, busy %, (cost), with the best marked. The headline card in screen 11 should name the winner over all options. |
| 12 | 05-run-monitor | No time estimate. Live numbers say "default" while his scenarios are named one_till and two_tills. | Minor | Show "about N minutes left". Label live rows with the scenario names the user gave. |
| 13 | 08-first-start-notice | AGPL means nothing to him. Nothing says whether data stays on his computer or who makes the tool. | Minor | Add "Your data stays on this computer" (if true) and a plain one-line licence summary ("free to use, including at work"). |
| 14 | 01-canvas, 10 | Block names (source, sink, server) and error codes (E131, W200) are developer words. "Param: on" is unexplained. | Minor | Show friendly names ("Customers arrive", "Leave", "Station") with the technical name as subtitle. Hide codes behind "details". Rename "Param" to "Vary between scenarios" with a tooltip. |
| 15 | 02-home, 03-data, 06-results | Placeholders and spec notes visible (`{minutes} min`, `{score}`, "spec 4", "E174"). | Minor | Expected in wireframes. Make sure the final build never shows them. |
| 16 | 07-settings | Findings thresholds, tier, engines and "max_concurrent_runs" are visible to everyone. Not harmful, but adds to the "this is not for me" feeling. | Minor | Group under "Advanced" in Settings. |

## What worked

- The first-start notice is short and honest: "Use them to support your judgement, not to replace it."
- The Data screen's file list, column table and preview feel like Excel. Importing was not scary.
- The fitted-pattern chart in screen 12, with its plain caption ("If they match, the pattern is a fair stand-in"), was the one way he could judge the fit.
- Scenarios as a table of rows made sense once he found it.
- The Run monitor says runs continue if the window closes. He would leave and come back.
- Findings written as sentences ("weld is the bottleneck: busy 90% of the time…") and the headline card ("Two tills cut the average wait from 4.5 min to 0.25 min") are exactly how he wants to be told.
- The 1-till / 2-tills / 3-tills dot chart showed that the options differ clearly.
- The trials table looks like a spreadsheet, so he could sort and scan it.
- Export CSV and Export PDF are where he expects them.
- The new look's block icons, the "Bottleneck" tag, the busy ring and the "Queue avg" label make the canvas readable at a glance.
- The delete dialog says what will be removed and that Ctrl+Z undoes it.

## Limits of this walkthrough

- This is an AI role-play. Daniel is not a real person, and the AI is not a person outside the project. It may share the designers' blind spots and miss problems a real café manager would hit.
- It saw static images, not a working app. It could not click, type, wait for a run or see error messages appear. Timings ("fifteen of my twenty minutes") are guesses.
- The grey screens contain placeholders and use other models (three-machine line, arrivals data) as stand-ins for his café. Some reactions are to those stand-ins.
- It cannot replace spec 3's outside walkthrough with a real participant. Treat these findings as hypotheses to check in that session.
