# Three-machine production line

## Parts arrive

Component: `arrivals`

Parts arrive at random, 30 an hour on average. Every part visits three stations in turn: cut, weld and paint. The run is 100 hours long, and the first 20 hours are warm-up, while the empty line fills up, so the results cover the remaining 80 hours: about 2,400 parts.

## Cutting

Component: `cut`

Cutting takes 1.2 minutes on average, so the cut station is needed 30 × 1.2 = 36 minutes an hour: 60% busy. It shows a little more, about 72%, because sometimes it has finished a part but cannot pass it on. The buffer after it is full, so it stays blocked, holding the part.

## The buffer before welding

Component: `buffer`

The buffer holds up to 10 parts waiting for the weld station, and parts spend most of their time here, about 10 minutes on average. When it is full, cut must stop. A buffer decouples two stations: it absorbs bursts, so that a short hold-up at one station does not stop the other.

## Welding, the bottleneck

Component: `weld`

Welding takes 1.8 minutes on average, so the weld station is busy 30 × 1.8 = 54 minutes an hour: 90%. It is the busiest station, the bottleneck: it sets the pace of the whole line, and the queue builds in front of it. Speeding up another station barely helps; speeding up welding helps most.

## Transfer to paint

Component: `transfer`

A conveyor carries each welded part to paint in exactly 2 minutes. A delay has no queue and no capacity limit: every part on it moves at once, so it adds 2 minutes to each part but never makes one wait.

## Painting

Component: `paint`

Painting takes 1 minute on average, so the paint station is only 50% busy, and parts wait about a minute there. Not every station can be the bottleneck: paint has spare capacity.

## Finished parts

Component: `exit`

The exit counts 30 finished parts an hour, the arrival rate, since no part is lost and the line keeps up. A part takes about 25 minutes from arrival to exit, of which only 6 are work and transfer; the rest is waiting, mostly before welding.

## Exercise: a smaller buffer

Component: `buffer`

### Change

Set the buffer's `capacity` from 10 to 3, and run again.

### Prediction

- [ ] Parts get through faster, since there is less room to wait.
- [ ] The line falls behind: fewer than 30 parts an hour are finished.
- [x] The line still finishes 30 parts an hour, but cut is blocked more often and parts take longer overall.

### Explanation

A small buffer fills more often, and then cut must stop, holding a finished part: its busy share rises from about 72% to about 90%. Parts now wait in front of cut instead, and the whole trip takes about 36 minutes instead of 25. The weld station still sets the pace, 30 parts an hour.
