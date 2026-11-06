# Simulated walkthrough: student persona (AI, not a real participant)

Date: 2026-11-06. Material: twelve static screen images (grey wireframes 01 to 08, proposed new look 10 to 12). The participant did not read the specs, design notes, research notes or decisions log.

## Persona

Priya, 20, second-year business-management undergraduate. One intro statistics module. Comfortable with Excel and Canva. Has never written code or used simulation software. Her lecturer told the class to try Ithax to learn about queues before a seminar on operations management. She has about 30 minutes and wants to understand, not just click.

## Think-aloud by task

### Task 1: First launch (08-first-start-notice.png)

- "Welcome. 'Build a model of a process, run it many times, and see where the waits and bottlenecks are.' OK, so it's about waiting. My lecturer said queues, so I think this is right."
- "'No code needed.' Good, that's a relief."
- "'Results are estimates. Use them to support your judgement.' Fine, sounds sensible, a bit like a disclaimer."
- "Licence, GNU AGPL version 3. I don't know what that is. Do I need to agree to something? There's no tick box, so I guess not."
- "It doesn't say it's for learning or that there are lessons. I'd only know that because my lecturer told me."
- "Would I continue? Yes. It's short and there's only one button."

### Task 2: Home, start the coffee shop lesson (02-home.png)

- "'What would you like to do?' Learn or Build. I want Learn. 'A guided lesson explains each block, then asks you to change something and predict.' That's exactly what I need."
- "But is the Learn box a button? It has no arrow and no 'Start' label. I'd try clicking it anyway."
- "Then below there's 'Coffee shop queue', tagged 'Students'. That's the one my lecturer meant. So do I click Learn first, or the coffee shop card? Are they the same thing?"
- "'{minutes} min' on every card. Is that broken? I wanted to know how long it takes, I've only got half an hour."
- "There's a grey note at the bottom about 'template.json (spec 4)'. That looks like a note for the developers, not for me."
- "On the right, 'Recent projects: Coffee shop, edited today'. But I've never opened this before. Did someone else use it? Should I open that instead of the template?"
- "I'd click the 'Coffee shop queue' card because it says Students. I'm guessing that starts the lesson."

### Task 3: Find the till, change tills from 1 to 2, predict (01b-canvas-learn.png, 01-canvas.png, 04-experiment.png)

- "OK, three boxes in a line: arrivals, till, exit. Like a flowchart. The till one has a purple ring and says 'Step 2 of 5'. So that's the till."
- "The box on the right explains it: 'Customers wait here until the till is free. Serving takes about 1.5 minutes on average, but every customer is different, so the time is random. Capacity says how many tills are open.' That's clear. I get it."
- "Arrivals is 'every 2 min (exp.)'. What's 'exp.'? Expected? Exponential? I remember exponential from stats but only vaguely."
- "Now change tills to 2. Under the lesson box it says Capacity, 'tills = 1'. Can I click in there and type 2? Or do I type 'tills = 2'? It looks like a formula in Excel."
- "On the till box itself it says 'capacity = tills'. So 'tills' is like a named cell? I think so, but I'm not sure."
- "In the normal canvas view the Capacity box just says 'tills' and there's a button 'Param: on'. What does Param mean? If I turn it off, does it break?"
- "Then I look at Experiment and there's already a table with 'one_till' 1 and 'two_tills' 2. So maybe I don't need to change anything? It's already set up? Now I'm confused about which place is the real one."
- "The Experiment page also has Seed, Warm-up, Replications, Confidence 0.95, Optimization, Objectives 'wait minimize till.wait.mean'. That's a lot. I'd leave it alone and hope it's fine."
- "The left list of blocks: source, sink, delay, batch, unbatch, resource_pool. Lowercase with underscores. Looks like code. I'd ignore it for the lesson."
- "My prediction: one person arrives every 2 minutes, serving takes 1.5. So one till is busy most of the time. With 2 tills, the work is split in half. So I think the wait roughly halves. If it's 4 minutes now, maybe 2 minutes with two tills."
- "I can't see where the lesson actually asks me to predict. I only see step 2 of 5. Is there a box to type my guess in?"

### Task 4: Run it (05-run-monitor.png)

- "I press the blue Run button at the top. Easy to find."
- "Now 'Run 20261106T101502-K3QX7A'. That's a horrible name. I don't need that."
- "Progress bar at 40%. 'Scenario 1 of 2, replication 12 of 30.' So it's doing it 30 times for each setup? Why 30?"
- "How long will it take? It doesn't say. It started at 10:15. I don't know what time it is now or how long 40% took. A 'about 1 minute left' would help."
- "Live key numbers: 'till.wait.mean 4.5 min', 'till.utilization 75%'. I think that means average wait 4.5 minutes and the till is busy 75% of the time. The dots and abbreviations look like code."
- "It says scenario 'default'. But my scenarios were one_till and two_tills. Which one is this?"
- "'Runs of this project': there's a queued one and an old done one. I only pressed Run once. Did I press it twice by accident?"
- "I'm mostly watching the progress bar and the 4.5 min number."

### Task 5: Results (06-results.png, 11-new-look-result-headline.png, 12-new-look-charts-and-delete-dialog.png)

- "The wireframe Results screen is about a three-machine line and 'weld', not my coffee shop. So I can't really see my results there. I'll use the new-look pictures."
- "Headline: 'Two tills cut the average wait from 4.5 min to 0.25 min.' Wow. That's way more than half. I guessed 2 minutes. It's like 18 times less."
- "That's the interesting bit, but the screen doesn't tell me why. I want a sentence like 'with one till it's busy 75% of the time, so queues build up'."
- "My try at explaining to a classmate: 'With one till, it's busy three-quarters of the time, so most people arrive when someone's already being served and a queue builds up and doesn't clear. With two tills, it's rare that both are busy at once, so almost nobody waits.' I think that's right, but I worked it out from the 75% and 38% busy numbers in the trials table, not because the tool explained it."
- "Chart 'Wait at the till, every repeat run'. Rows for 1 till, 2 tills, 3 tills, with dots and a diamond. That's nice, I can see the groups are far apart."
- "But the axis goes 0.01, 0.1, 1, 10. Log scale. We did that once in stats and I hated it. The gap from 1 to 10 looks the same as 0.1 to 1, which is weird. I nearly read it as 'not that different'."
- "The caption says 'the blue bar is its likely range (95%)'. I can't see a blue bar clearly, just dots and the diamond."
- "'95% range' or '95% interval' means to me: the answer is somewhere in here, and we're 95% sure. Like a margin of error in a poll. I think that's roughly right? I'm not sure if it's the range for one day or for the average."
- "In the wireframe, '± 4.4 min' and '{half-width}'. Half-width? I don't know that word."
- "'Not enough runs: replications would be needed for a 10% interval.' I don't understand what I'm meant to do. Is my result wrong? Should I press Run again?"
- "The '1,000 trials: best so far' chart has hundreds of dots. Too much for me. I didn't ask for 1,000 trials."
- "The trials table: row 633 has 3 tills and only 0.04 min wait, but 'OK? No'. Why is the best one not OK? Is 25% busy bad? Nothing tells me."
- "The 'Minutes between arrivals' chart with bars and a curve makes sense. The curve fits the bars. Nice."
- "Charts help a bit. The repeat-run dots chart is the best one, if it wasn't log scale. The search charts confuse me."

### Task 6: Delete a block by mistake (12-new-look-charts-and-delete-dialog.png, 10-new-look-canvas.png, 01-canvas.png)

- "In the new look there's a bin icon at the bottom of the canvas. In the grey version I can't see a delete button at all. Maybe I'd press the Delete key."
- "I click the bin. A box pops up: 'Delete 2 blocks? This removes Till, Baristas and 2 connections. You can undo it with Ctrl+Z.' Good, it tells me exactly what goes."
- "Wait, I only meant one block. Baristas too? I guess I had both selected. Good that it tells me."
- "Cancel and Delete are clear. Delete is red, so I know it's the dangerous one."
- "If I'd already deleted it, I'd press Undo at the top. It's a big labelled button in the grey version. In the new look it's just an arrow icon, but I'd guess it."
- "'Don't ask me again' — I'd never tick that."
- "One worry: in the new look there's a 'Baristas, resource pool' box linked to Till by 'pool'. So is the number of tills set in Till or in Baristas? I'm not sure which one I'd change for the exercise."

### Task 7: Grey wireframes versus new look (10, 11, 12)

- "The new look, easily. It's warm, has icons, and the boxes look like things, not code."
- "'Source', 'Delay', 'Resource pool' with capitals and icons, not 'resource_pool'. Much friendlier."
- "The till shows '75%' in a ring and a red 'Bottleneck' tag, and 'Queue avg 4.5 min' underneath. I can see the problem on the picture without going to another screen. That's the best thing in the whole app."
- "The headline card with the trophy reads like a news headline. I'd screenshot that for the seminar."
- "The grey one feels like a form in a spreadsheet. Fine for checking, but boring for a whole afternoon."
- "The new-look canvas picture is cut off on the right, so I couldn't read the settings panel."
- "The fonts in the charts look a bit techy, like a typewriter. Not bad though."

## Problems found

| # | Screen / file | What confused or blocked | Severity | Suggested fix |
| --- | --- | --- | --- | --- |
| 1 | 01b-canvas-learn, 01-canvas, 04-experiment, 10-new-look-canvas | Three or four places look like where "number of tills" is set: the lesson panel field "tills = 1", the block's "capacity = tills", the Experiment scenarios table (already has one_till and two_tills), and the Baristas resource pool. The persona did not know which to change. | Major | The lesson step that asks for the change should point to one control, highlight it, and say "type 2 here". Hide or explain the scenarios table during the lesson. Keep the lesson model free of a resource pool, or say how it relates to capacity. |
| 2 | 06-results, 11-new-look-result-headline | Results say what happened (4.5 to 0.25 min) but not why. The learning point, that waits grow steeply as a till gets busy, is left for the student to work out. | Major | In Learn mode, add a short "Why?" line under the headline, using the busy figures: "One till is busy 75% of the time, so queues build; with two, both are rarely busy at once." Then compare with the student's prediction. |
| 3 | 01b-canvas-learn | No visible place to enter a prediction. "Predict" is promised on Home but not shown on the lesson screen seen. | Major | Show a prediction step with a simple input (a number or "less / about half / much less") before Run, and show it again beside the result. |
| 4 | 12-new-look-charts (process-run chart), 06-results | Log-scale axis (0.01, 0.1, 1, 10) misleads a student; equal gaps look like equal differences. Caption names a "blue bar" that is hard to see. | Major | In Learn mode, use a linear axis or show the three averages as large labelled numbers next to the chart. Make the 95% range bar clearly visible, or change the caption. |
| 5 | 06-results, 05-run-monitor | Jargon a student cannot decode: "95% interval", "half-width", "replications", "till.wait.mean", "till.utilization", "Not enough runs ... {n_required}". The persona read 95% as "margin of error" but was unsure what it covers and what action "Not enough runs" asks for. | Major | Plain labels ("average wait at the till", "busy"). A one-line tooltip for "95% range": "If you ran this many more times, the average would land in this range 95 times out of 100." Make "Not enough runs" end with an action button ("Run more repeats"). |
| 6 | 02-home | Two routes to the lesson: the Learn card and the "Coffee shop queue" template card. Learn card has no button or arrow. | Major | Make Learn open a list of lessons, or put a "Start lesson" button on the Coffee shop card. Give cards a visible call to action. |
| 7 | 02-home | "{minutes} min" placeholders and a developer note ("template.json (spec 4)") are visible. A student with 30 minutes wants the real time. | Minor (wireframe placeholder) | Fill real minutes; remove spec notes from user-facing screens. |
| 8 | 02-home | On first launch, Recent projects already lists "Coffee shop, edited today" and others. Persona wondered if someone else had used it. | Minor | Empty Recent list on first launch, with a line "Your projects will appear here." |
| 9 | 05-run-monitor | No time estimate; only percent and "replication 12 of 30". Run name is a long code. Live table says scenario "default" when the experiment has one_till and two_tills. A queued run appeared that the persona did not start. | Minor | Show "about N s left". Show the project and scenario names, not the run code, as the title. Name scenarios consistently. |
| 10 | 04-experiment | Optimization and search panel (objectives, constraints, seed, budget) is shown to a lesson user, with search ticked. Overwhelming; persona feared breaking something. | Minor | Hide the Experiment screen or its advanced parts during a lesson, or collapse them under "Advanced". |
| 11 | 12-new-look-charts (search table and trials chart) | Row 633 (3 tills, 0.04 min) says "OK? No" with no reason. 1,000-trial scatter is too much for a learner. | Minor | Say which limit was broken ("too idle: busy 25%, limit 30%"). Keep search charts out of the beginner lesson. |
| 12 | 01-canvas, 01b-canvas-learn | Block palette uses code names (resource_pool, unbatch); "exp." and "Param: on" are not explained; error shows a code "E131". | Minor | Friendly names as in the new look; spell out "exponential (random)"; replace "Param: on" with a clearer label or tooltip; keep codes secondary to the sentence. |
| 13 | 08-first-start-notice | Does not mention lessons; licence line is jargon for this user. | Minor | Add "New? Start with a guided lesson." Keep licence line, but shorter ("Free and open source"). |
| 14 | 12-new-look-charts (delete dialog) | "Don't ask me again" is easy to tick by accident; undo shown only as Ctrl+Z, not the Undo button. | Minor | Mention the Undo button too. Consider removing "Don't ask me again" from the dialog and leaving it in Settings. |

## What worked

- The welcome notice is short, plain and has one button.
- "Learn: a guided lesson explains each block, then asks you to change something and predict" matched the persona's goal exactly.
- The lesson highlight (purple ring, "Step 2 of 5") made it obvious which block was the till.
- The till explanation text was clear and short. It explained randomness in everyday words.
- The Run button was easy to find in every screen.
- The headline card ("Two tills cut the average wait from 4.5 min to 0.25 min") gave the answer first, in plain words.
- The repeat-run dot chart showed that the three options are clearly different.
- The arrivals histogram with its fitted curve was understood without help.
- The delete dialog named exactly what would be removed and how to undo it.
- In the new look, the busy ring, "Bottleneck" tag and "Queue avg" label on the canvas showed the problem on the picture itself. This was the persona's favourite feature.
- The persona strongly preferred the new look: friendly names, icons, warmer colours.

## Limits of this walkthrough

- This is an AI role-play. It is not a person outside the project.
- It saw static images, not a working app. It could not click, type, see transitions, or see lesson steps other than step 2.
- The wireframe Results screen showed a different model (three-machine line), so coffee shop results were judged from the new-look example images only.
- The new-look canvas image was cropped on the right, so its side panel was not assessed.
- Some problems (placeholders, spec notes) are wireframe artefacts and may not reach the product.
- It cannot replace spec 3's outside walkthrough with a real person. It should be used only to prepare for that walkthrough.
