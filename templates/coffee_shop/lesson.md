# Coffee shop queue

## Customers arrive

Component: `arrivals`

Customers arrive at random, on average one every 2 minutes, or 30 an hour. "At random" means the gaps follow an exponential distribution: most are short and a few are long, so customers sometimes come in bunches. The run is 200 hours long, and the first 10 hours are warm-up, so the results cover the remaining 190 hours: about 5,700 customers.

## One till serves them

Component: `till`

The till serves one customer at a time, in 1.5 minutes on average, also at random. It is busy 1.5 ÷ 2 = 75% of the time. Yet customers wait about 4.5 minutes in line, three times their service: when a bunch arrives while the till is busy, the bunch must queue. Queueing theory (the M/M/1 queue) predicts exactly 4.5 minutes.

## Customers leave

Component: `exit`

Each customer leaves through the exit, which records the time spent in the shop: about 6 minutes, 4.5 waiting and 1.5 being served. Little's law links the numbers: customers inside, on average, equal the arrival rate times the time inside, 0.5 a minute × 6 minutes = 3. Each result comes with a range, from 30 repeat runs.

## Exercise: open a second till

Component: `till`

### Change

Set the parameter `tills` to 2, so that two customers can be served at once, and run again.

### Prediction

- [ ] The wait halves, to about 2.2 minutes.
- [x] The wait falls to about a quarter of a minute, far less than half.
- [ ] The wait hardly changes: the till was only 75% busy.

### Explanation

Two tills are each busy 37.5% of the time, so a customer rarely finds both serving. The wait falls from 4.5 minutes to about 15 seconds, as the Erlang C formula predicts (14.7 seconds). Halving the load cuts the wait by far more than half, because waiting grows steeply as a server gets close to full.
