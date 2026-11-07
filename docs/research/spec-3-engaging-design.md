# Spec 3 research: engaging visual design (M9 design review)

## Question

The owner reviewed the first design (`docs/design/`, AKS-118) and said it is very functional but has no "wow factor" and looks like a traditional ERP (enterprise resource planning software: dense grey forms and tables). What does research and well-known design teaching say about why visual appeal matters, which visual devices make products feel delightful and keep people using them, which engagement patterns are fair and which are manipulative, and which concrete design moves should Ithax make while staying at WCAG 2.2 Level AA?

## Finding

### 1. Why visual appeal matters: what was measured

**The aesthetic-usability effect.** This is the finding that people judge attractive interfaces as easier to use, even when they are not.

- **Measured.** Kurosu and Kashimura (Hitachi Design Center, CHI 1995) showed 252 people 26 layouts of a cash-machine screen. Ratings of beauty correlated more strongly with how easy people *thought* a layout was than with how easy it actually was (as summarised by Nielsen Norman Group, Moran).
- **Measured.** Tractinsky, Katz and Ikar (2000, *Interacting with Computers* 13(2)) varied both beauty and real usability in an experiment. After use, the system's beauty affected how usable people said it was; its real usability did not.
- **Measured, and it disagrees.** Hassenzahl (2004) found beauty was driven by "hedonic" qualities (stimulation, identity), not by usability; usability mattered for overall "goodness", more so after use. Tuch et al. (2012) found that poor usability lowered beauty ratings after use, but beauty did not raise perceived usability. A Cornell thesis also failed to replicate Tractinsky's result.
- **Teaching (NN/g).** Moran's article: attractive design makes users "more tolerant of minor usability problems", but "not of large ones", and it can hide problems in usability tests, so watch what users do, not only what they say.

**Plain reading:** looks raise first impressions and goodwill. They never rescue a confusing product. Usability must come first, and good looks must not hide problems from testers.

**Google's Material 3 Expressive research (published May 2025).** "Expressive" here means bolder colour, larger shapes and type, more varied shapes and springy motion. Google's own page reports:

- **Measured (Google's own studies, not independently replicated):** 46 studies, hundreds of designs, more than 18,000 participants, from 2022 to 2025. Methods: eye tracking, surveys and focus groups, preference experiments, usability tests.
- **Measured:** people spotted key interface elements up to 4 times faster. The best case was an email "Send" button made larger and placed above the keyboard. This is an "up to" figure for single tasks, not an average.
- **Measured:** users aged 45 and over found key elements as fast as younger users in the expressive designs ("dramatic erasure of age effects in fixation times").
- **Measured:** expressive designs were preferred in all age groups, most by 18 to 24 year olds (up to 87%). Ratings for "playful", "energetic", "friendly" were higher. Sample sizes for the eye tracking and age comparison are not given.
- **Google's own caveats:** usability dropped when a list was replaced by unstructured album art, and when text labels were removed from actions. A "strong minority" preferred calmer designs. Context matters; Google names banking as a case for restraint. "No amount of emotion can compensate for a lack of clarity."

**Lesson for Ithax:** expressive means *bigger, clearer, more shaped and more coloured key elements*, not decoration. Keep text labels. Offer a calmer option.

### 2. Well-known teaching (opinion and frameworks, not measurements)

- **Don Norman, *Emotional Design* (2004).** Three levels at which a product is judged. *Visceral*: the gut reaction to how it looks in the first second. *Behavioural*: how it feels to use, whether it helps reach the goal. *Reflective*: what the person thinks of it afterwards, and of themselves using it ("I built a model of my shop"). The Interaction Design Foundation teaches this in its course "Emotional Design: How to Make Products People Will Love". Ithax's first design served the behavioural level well and the visceral level little.
- **Refactoring UI (Adam Wathan and Steve Schoger, 2018).** Practical rules for developers. Relevant ones: *choose a personality first*; corner radius, typeface and colour set it (small radius reads formal, large radius reads friendly). *Use fewer borders*: separate areas with spacing, background tint and soft shadows instead of lines. *Don't overlook empty states*: they are often the first screen a person sees, so make them an invitation with a clear next step, not "No data". *You need more colours than you think*: each hue needs a scale of 8 to 10 shades. *Emphasise by de-emphasising*: make secondary things quieter rather than making everything louder.
- **Motion durations (Laubheimer, NN/g, 2020).** Feedback on small controls about 100 ms; larger screen changes 200 to 300 ms; most animation within 100 to 400 ms; exits shorter than entrances.
- **Peak-end rule (Kahneman and colleagues, 1993).** People remember an experience mostly by its most intense moment and its end. For Ithax the end of a run is that moment, and today it is a table.
- **Microinteractions (Dan Saffer, 2013).** Small single-purpose moments (a toggle, a drop, a connect) made of a trigger, rules, feedback and loops. They are where a product feels "made with care".
- **Courses.** IxDF "Emotional Design" (above). The Google UX Design Professional Certificate (Coursera) teaches visual hierarchy, typography and colour basics. NN/g publishes free articles on the aesthetic-usability effect, animation and empty states. These teach the same points as above; none adds a measured result.

### 3. What delightful products actually do

These are observations of the products' public interfaces, not measurements. Where a feature was checked in documentation this session, the source is listed.

| Product | Visual device doing the work |
| --- | --- |
| **Make.com** (automation canvas) | Each step is a large **circle** in its app's brand colour with a white icon; connections are thick dotted lines. After "Run once", a **white bubble on each module shows how many operations it ran**, and opening it shows the data that passed (Make help, "Operations"). Feels like a toy, works like a tool. The opposite of ERP boxes. |
| **n8n** (automation canvas) | Square nodes with a big centred icon and the label under the node; trigger nodes have a **rounded left side**, so shape tells role. After a run, nodes show a **green tick and item counts**. |
| **Unreal Engine Blueprints** | Node headers coloured by node kind; pins coloured by data type. While the game runs, **execution wires pulse** along the path being taken (UE 4.27 docs, "Blueprint debugging"). Watching the flow is the debugging aid. |
| **Blender geometry nodes** | **Socket shape carries meaning**: circle for a single value, diamond for a field, diamond with a dot for "could be a field, is a single value now" (Blender manual, "Fields"). Colour also codes type, but shape works without colour. |
| **ComfyUI** | Links coloured by data type; the node that is executing is outlined and a progress bar runs across the top. |
| **Duolingo** | Rounded, chunky shapes, a custom rounded typeface, a mascot and illustrations. Each answer gets **immediate feedback** with sound and a short animation; lessons sit on a visible path. Streaks (below) drive return visits. |
| **Brilliant.org** | Interactive diagrams the learner manipulates; **real-time feedback** on each step with a hint or explanation, right or wrong (Brilliant's own page). Learning by doing, not reading. |
| **Figma / FigJam** | FigJam uses a bright palette, rounded stickies, stamps and cursor reactions: playful on purpose, inside a serious tool. |
| **Linear** | Restraint plus craft: tight typography, a dark theme with subtle gradients, fast motion, keyboard first. Shows "premium" can be calm. |
| **Notion** | Monochrome hand-drawn illustrations in empty states, onboarding and templates give warmth without colour noise. |
| **Arc browser** | Colour themes per space, playful onboarding animation. |
| **Observable** | Charts update live as inputs change: the "it reacts to me" feeling. |
| **tldraw** | A hand-drawn line style and soft colours make diagrams feel approachable. |
| **Rive / Framer** | Small interactive state animations (buttons, loaders, mascots) shipped as light vector files. |

**Patterns that repeat:**

1. **Shape language.** Rounded or circular nodes read as friendly and touchable; shape (not only colour) tells kinds apart (n8n triggers, Blender sockets, Make circles).
2. **The model comes alive when it runs.** Pulsing wires, counts on nodes, progress on the active node (Unreal, Make, n8n, ComfyUI). For a simulation tool this is the most natural "wow": items visibly flowing.
3. **Big icons with colour per kind.** Recognition at a glance, labels kept.
4. **Immediate feedback and a visible path** in learning (Brilliant, Duolingo).
5. **Illustration** in empty states and onboarding (Notion, Duolingo).
6. **A clear peak at the end** of a task (Duolingo lesson end screen).
7. **Characterful type** and a palette with more than one accent.

### 4. Engagement that is fair, and dark patterns to avoid

**Duolingo's own data (company-reported, not peer reviewed):** learners who reach a 7-day streak are 2.4 times more likely to come back the next day; separating the daily goal from the streak raised day-14 retention by 3.3%; a "Streak Wager" raised day-7 retention by 14%. Streaks work, which is exactly why they need care.

**Dark patterns** (also called deceptive patterns) are designs that push people into acts against their own interest. Catalogued kinds include *nagging* (repeated interruptions to push an action), *confirmshaming* (wording that shames a "no", such as "No thanks, I like long queues"), and gamification that "coerces users into continuous use".

| Fair for a learning and business tool | Avoid |
| --- | --- |
| Progress that belongs to the work: "Lesson 3 of 8 done", a lesson map with completed steps | Streaks that break and guilt the user; loss-framed reminders ("Your streak is about to die") |
| Immediate, kind feedback on each lesson step, with the reason | Points, levels or leaderboards with no learning meaning |
| A celebration when something real happens: first run, a lesson finished, an answer that matches theory | Celebrations on every click; random rewards (variable rewards drive compulsion) |
| Notifications only when the user asked (a long run finished) | Nagging, badges that count unread "activity", confirmshaming |
| Calm defaults with a setting for more or less motion | Autoplaying motion that cannot be stopped |

Self-determination theory (Ryan and Deci) gives a usable test: support the person's *competence* (they see they can do it), *autonomy* (they choose) and *relatedness*; avoid external pressure. Ithax has no accounts or social features, so streaks and leaderboards have no place anyway.

### 5. Accessibility limits (WCAG 2.2 AA, plus 2.3.3)

- **1.4.3 and 1.4.11.** Richer colour must keep text at 4.5:1 and outlines, icons and markers at 3:1. Tints used as fills are decorative and need not pass, but anything that identifies a block (its outline or icon) must. `scripts/contrast.py` already checks this from `tokens.json`.
- **1.4.1.** Never colour alone: a category gets a shape and an icon as well as a colour.
- **2.2.2 Pause, Stop, Hide.** Moving content that starts automatically, lasts more than 5 seconds and runs beside other content needs a way to pause, stop or hide it. Item-flow animation during a run falls under this.
- **2.3.3 Animation from Interactions (AAA, followed anyway).** Motion triggered by interaction can be turned off. In practice: honour the operating system's `prefers-reduced-motion` setting, and add an in-app motion setting.
- **2.3.1 Three Flashes.** Celebrations must not flash more than three times a second.
- Animation must never be the only place information appears: counts and states also show as text.

## Sources

Read on 2026-11-06 unless marked.

- Moran, K., "The Aesthetic-Usability Effect", Nielsen Norman Group (2024, reviewed 2026): https://www.nngroup.com/articles/aesthetic-usability-effect/
- Kurosu, M. and Kashimura, K., "Apparent usability vs. inherent usability", CHI 1995 conference companion (via the NN/g summary above).
- Tractinsky, N., Katz, A. S. and Ikar, D., "What is beautiful is usable", *Interacting with Computers* 13(2), 2000, 127–145; abstract: https://academic.oup.com/iwc/article-abstract/13/2/127/898608
- Hassenzahl, M., "The interplay of beauty, goodness, and usability in interactive products", *Human-Computer Interaction* 19(4), 2004 (abstract via search summary): https://scilit.com/publications/d6511a1f44e4a339d6bb8f48af3a275c
- Tuch, A. N. et al., "Is beautiful really usable?", *Computers in Human Behavior* 28(5), 2012 (abstract via search summary): https://www.scribd.com/document/250117181/Tuch-et-al-2012
- Google, "Expressive Design: Google's UX Research": https://design.google/library/expressive-material-design-google-research
- Android Developers, "Benefits of expressive design": https://developer.android.com/design/ui/wear/guides/get-started/benefits
- Interaction Design Foundation, "Emotional Design" topic and course: https://ixdf.org/literature/topics/emotional-design and https://ixdf.org/courses/emotional-design-how-to-make-products-people-will-love
- Norman, D. A., *Emotional Design: Why We Love (or Hate) Everyday Things*, Basic Books, 2004 (book; not re-read this session).
- Wathan, A. and Schoger, S., *Refactoring UI*, 2018 (book; chapter points checked against summaries such as https://sglavoie-github-io.pages.dev/posts/2023/09/09/book-summary-refactoring-ui/).
- Laubheimer, P., "Executing UX Animations: Duration and Motion Characteristics", NN/g, 2020: https://www.nngroup.com/articles/animation-duration/
- Kahneman, D. et al., "When more pain is preferred to less: adding a better end", *Psychological Science* 4(6), 1993 (not re-read).
- Saffer, D., *Microinteractions*, O'Reilly, 2013 (not re-read).
- Make help, "Operations": https://help.make.com/operations.md
- n8n community, item counts and success tick after execution: https://community.n8n.io/t/how-to-display-infos-results-for-users-that-manually-launch-the-workflow/24139
- Unreal Engine 4.27, "Blueprint debugging": https://docs.unrealengine.com/4.27/ProgrammingAndScripting/Blueprints/BP_HowTo/Debugging
- Blender manual, "Fields" (socket shapes): https://docs.blender.org/manual/en/latest/modeling/geometry_nodes/fields.html
- Brilliant, "Learn by doing": https://next.brilliant.org
- Duolingo, "How streaks keep Duolingo learners committed": https://making.duolingo.com/how-streaks-keep-duolingo-learners-committed-to-their-language-goals and "Improving the streak": https://blog.duolingo.com/improving-the-streak
- Deceptive pattern taxonomy (nagging, confirmshaming, coercive gamification): "Deceptive Patterns as a Sociotechnical Phenomenon", https://arxiv.org/pdf/2608.27684 ; https://www.deceptive.design
- W3C, WCAG 2.2 (2.2.2, 2.3.1, 2.3.3): https://www.w3.org/TR/WCAG22/
- Product observations for Make and n8n node shapes, Duolingo's visual style, ComfyUI, Figma/FigJam, Linear, Notion, Arc, Observable, tldraw, Rive and Framer are from their public interfaces as generally known; they were not re-checked in a browser this session.

## Decision

All moves below are **proposals for the owner**. None changes behaviour in spec 3; they change the look and feel in `docs/design/`. Colour values are left to the separate Sanzo Wada palette work; every move here names token *roles*, not colours.

1. **A friendlier shape language, with shape telling the category.** Radius grows from 4 px to 12 px on blocks and 16 px on cards. Flow blocks (`source`, `sink`, `delay`, `branch`) become **capsules** (pill shapes with round ends); work blocks (`server`, `queue`, `batch`, `unbatch`, `store`) stay **rounded rectangles**; resource blocks (`resource_pool`, `schedule`, `failure`) become **rounded tags with a notched corner** and keep the dashed outline. Each block leads with a **32 px circular icon disc** in its category tint (Make's device). *Reason:* rounded shapes read friendly (Refactoring UI); shape adds a non-colour cue (WCAG 1.4.1, Blender sockets, n8n triggers). Ports, hit targets and the 1 px outline at 3:1 stay.
2. **Items flow along connections while a run plays, and on replay.** Small dots travel along each connection at a rate scaled to its throughput; a queue's block shows a growing fill bar and a count. After a run, each block shows a **count bubble** ("412 served") and servers a thin **utilisation ring** around their icon disc (Make bubbles, n8n counts, Unreal pulsing wires). *Reason:* the model "comes alive", which is the natural wow for a simulation tool and teaches queueing at the visceral level. *Limits:* a visible "Pause animation" control (WCAG 2.2.2); under reduced motion the dots are replaced by static counts on connections; all numbers also appear as text and in the side panel. This is a picture of results the engine already reports (rates, counts, queue lengths), not new numerical code (`CLAUDE.md` rule 7). Spec 3 "Run monitor" would need a line allowing it; that is the owner's call.
3. **A results "moment" when a run finishes.** The Results screen opens on a hero card: the headline finding in large display type ("Average wait 4.5 min, down 38%") with one short entrance animation (300 ms) and a brief accent sweep. The first run of a project and the end of a Learn lesson add a small illustrated celebration. Nothing celebrates on every click. *Reason:* peak-end rule; Duolingo's lesson end. *Limits:* no flashing (2.3.1), off under reduced motion, never sound by default.
4. **Illustrated empty states that start something.** Empty canvas, empty data, no results yet, and first start each get a small line illustration in the house style and two or three clear actions ("Start from a template", "Take the 5-minute lesson", "Blank model"). *Reason:* Refactoring UI and Notion; the empty canvas is the first screen. Illustrations are bundled SVG, marked decorative, and never hold the only copy of an instruction.
5. **Characterful typography.** A display face for titles, big numbers and the hero card, a highly legible face for the interface, and a mono for ids. Details and licences are in `spec-3-icons-and-type.md`. *Reason:* type sets personality more than any other single choice (Refactoring UI); M3 Expressive's bigger type helped people find key elements.
6. **A richer palette with room for Sanzo Wada combinations.** Keep the token roles; add per-category *tint* tokens (fills behind icons and capsules), a *brand* pair for the top bar and hero card, and a tinted canvas instead of neutral grey. Separate panels with tint and soft shadow instead of 1 px grey lines ("use fewer borders"). *Reason:* the grey-on-grey look is what reads as ERP. Values come from the separate colour work and must pass `scripts/contrast.py`.
7. **Icons on every nav rail item and canvas button**, with a duotone weight for block icons and a filled weight for the current nav item, words kept beside them. Icon set and mapping are in `spec-3-icons-and-type.md`. *Reason:* the owner's request; recognition at a glance; labels kept because Google found removing labels hurt usability.
8. **Microinteractions with set durations.** A block "settles" when dropped (150 ms), a new connection draws itself from port to port (200 ms), compatible ports gently pulse while connecting, the Run button shows progress inside itself. All within NN/g's 100 to 400 ms range, all removed under reduced motion. *Reason:* Saffer; NN/g durations.
9. **Learn mode as a visible path with immediate feedback, and no streaks.** A lesson map with completed steps ticked; each step checks the learner's model straight away and says why, in the manner of Brilliant; a lesson-complete card. No streaks, points, leaderboards or loss-framed reminders. *Reason:* fair engagement that supports competence and autonomy; avoids the dark patterns in section 4.
10. **A motion setting and a calm option.** Settings, Appearance gains "Motion: Full, Reduced, Off" (default follows the operating system) and keeps Light, Dark and System themes. *Reason:* Google found a strong minority prefer calmer designs; WCAG 2.3.3.

If the owner accepts, these files change in a later design session: `design-system.md` (principle 1 "Plain and calm" becomes "Calm to work in, lively when it matters"; "Motion" stops being "None"; radius, block, connection and type sections), `accessibility.md` (2.2.2 and 2.3.3 rows, which today rely on there being no animation), `tokens.json` and the wireframes; plus a DECISIONS entry replacing design choice 11.

## Tested

Not tested: no interface code exists, and nothing under `ui/` was written. The claims in section 1 come from the cited studies, of which only Google's covers interfaces like today's apps, and it is Google's own unreplicated report. The product observations in section 3 were not checked in a running product this session. The proposals should be tested in the owner's walkthrough with a student and a business user: show the current wireframe and a restyled one, watch task success first, then ask which they would rather use (to avoid the aesthetic-usability effect hiding problems).
