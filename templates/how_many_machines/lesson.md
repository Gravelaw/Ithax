# How many machines?

## Customers arrive

Component: `arrivals`

This is the coffee shop again: customers arrive at random, one every 2 minutes on average. The question is how many tills to open. Each choice is run 200 hours, and the first 10 hours are warm-up, so the results cover the remaining 190 hours. Instead of trying each choice by hand, the experiment `base` runs a search that tries them for us.

## The till is the machine to count

Component: `till`

The till's capacity is the parameter `tills`, which may be 1 to 5. The search's objective is the shortest mean wait at the till. Its constraint, `busy`, says each till must be busy at least 35% of the time, so the shop does not pay for idle tills. More tills always cut the wait, so the constraint decides where to stop.

## Search, then confirm

Component: `exit`

With only five choices, the search runs every one, 10 repeat runs each. The best few that meet the constraint are run again with all 30 repeat runs, and the constraint is judged on those. The answer is 2 tills: a wait of about 15 seconds, each till busy 37.5% of the time. Three tills would be busy only 25%, below the limit.

## Exercise: accept quieter tills

Component: `till`

### Change

Lower the constraint `busy` from 35% to 20%, so each till may be idle more of the time, and run the search again.

### Prediction

- [ ] Still 2 tills: the wait is already short.
- [x] 3 tills: they are busy 25% of the time, now allowed, and the wait falls to about 2 seconds.
- [ ] 5 tills: the most tills always give the shortest wait.

### Explanation

With the limit at 20%, three tills (each 25% busy) are allowed, and they cut the wait from about 15 seconds to about 2, as Erlang C predicts (1.8 seconds). Four tills would be busy only 18.75%, below the new limit. The constraint, not the objective, sets the answer: the search finds the shortest wait among the choices the limit allows.
