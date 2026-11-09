# Machine breakdowns

## Jobs arrive

Component: `arrivals`

Jobs arrive at random, one every 4 minutes on average, or 15 an hour. The run is 200 hours long, and the first 10 hours are warm-up, so the results cover the remaining 190 hours: about 2,850 jobs.

## The machine

Component: `machine`

Each job takes 2 minutes on average, so the work fills half the clock: 15 × 2 = 30 minutes an hour. If it never broke down, this machine would be busy 50% of the time, and a job would wait about 2 minutes for it (the M/M/1 queue).

## Breakdowns and repairs

Component: `breakdown`

The machine breaks down at random, on average 90 minutes after its last repair, whether busy or idle, and each repair takes 10 minutes on average. A job in progress is paused and finished after the repair. Availability, the share of time the machine can work, is MTTF ÷ (MTTF + MTTR) = 90 ÷ (90 + 10) = 90%.

## The cost of downtime

Component: `machine`

Breakdowns take only 10% of the time, yet the average wait rises from about 2 to about 5 minutes. The machine is busy 0.5 ÷ 0.9, about 56%, of the time it is available, and jobs that arrive during a repair all queue up together. Downtime costs far more in waiting than its share of the clock suggests.

## Finished jobs

Component: `exit`

The exit counts 15 finished jobs an hour: the machine still keeps up, since it needs only 56% of its available time. Each job spends about 7.4 minutes in the system, of which 2 are spent being worked on.

## Exercise: faster repairs

Component: `breakdown`

### Change

Set the mean repair time (`time_to_repair`) from 10 minutes to 5 minutes, and run again.

### Prediction

- [ ] Availability rises to 100%: repairs are now so quick that they do not matter.
- [ ] Availability rises to about 95%, but the wait hardly changes, since the machine was only half busy.
- [x] Availability rises to about 95%, and the average wait falls by about 40%.

### Explanation

Availability is now 90 ÷ (90 + 5), about 94.7%. The average wait falls from about 5.1 to about 2.9 minutes, over 40% less, because shorter repairs leave shorter queues behind them. Most of the waiting that breakdowns added is gone, though the machine still fails as often as before.
