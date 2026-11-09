# Warehouse pick and pack

## Orders arrive

Component: `orders`

Orders arrive at random, one a minute on average, or 60 an hour, day and night. The run is 216 hours long, and the first 24 hours are warm-up, so the results cover the remaining 192 hours: 8 whole days and about 11,520 orders.

## Carts of five

Component: `carts`

Orders are not picked one by one: they are gathered onto carts of 5, a batch. An order waits for the orders after it to fill its cart, 4 for the first and none for the last: on average (5 − 1) ÷ (2 × 1 a minute) = 2 minutes. Batching saves trips round the shelves, at the cost of that wait.

## Pickers

Component: `pickers`

A picker takes a full cart round the shelves in 9 minutes on average. Twelve carts an hour need 12 × 9 = 108 picker-minutes an hour: the work of 1.8 pickers, day and night.

## Shifts

Component: `shifts`

A schedule sets how many pickers work: 3 from 06:00 to 22:00 and 1 overnight, every day. That is 56 picker-hours a day out of the 72 that 3 pickers could give, a scheduled fraction of 78%. One picker manages only 6.7 carts an hour against 12 arriving, so carts pile up overnight and are cleared in the morning.

## Busy, but when?

Component: `pickers`

The pickers are busy about 77% of the time they are on shift: 43.2 hours of work a day over 56. Utilization says how much of the time is used, not when. The overnight backlog makes a cart wait about an hour for a picker on average, though the day shift has time to spare.

## To packing

Component: `to_packing`

A full cart is wheeled to packing in exactly 3 minutes. A delay has no queue: every cart on the way moves at once.

## Unloading

Component: `unload`

An unbatch splits each cart back into its 5 orders, which reach the packer together and are packed one at a time.

## Packing

Component: `packer`

Packing takes 30 seconds an order, so the packer is busy 60 × 0.5 = 30 minutes an hour: 50%. Orders reach it 5 at a time, so even a half-busy packer keeps them waiting, about 4 minutes on average.

## Dispatch

Component: `dispatch`

Sixty orders an hour are dispatched, as many as arrive, since nothing is lost. An order takes about 80 minutes from arrival to dispatch, most of it waiting for a picker after a night.

## Exercise: a second night picker

Component: `shifts`

### Change

Set the `capacity` of the two overnight shifts, the first and the last in the list (22:00 to 06:00), from 1 to 2, and run again.

### Prediction

- [ ] Little changes: the pickers were only 77% busy, so they already had time to spare.
- [ ] The wait for a picker falls by about a seventh, in step with the extra picker-hours.
- [x] The wait for a picker falls from about an hour to about 5 minutes.

### Explanation

Two pickers manage 13.3 carts an hour, more than the 12 that arrive, so no backlog builds overnight. The pickers are on shift 89% of the time and busy about 67% of it, and a cart waits about 5 minutes for a picker instead of an hour. An order's whole trip falls from about 80 to about 22 minutes.
