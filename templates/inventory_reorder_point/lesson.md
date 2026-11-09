# Inventory reorder point

## Customers arrive

Component: `customers`

Customers come at random to buy one spare part, 4 a day on average. The run is 1,000 days long, and the first 50 days are warm-up, so the results cover the remaining 950 days: about 3,800 customers.

## The stock rule

Component: `stock`

The store follows a reorder point rule: when the parts on the shelf plus those on order fall to 20, it orders 50 more, which arrive exactly 5 days later. Every 50 parts sold bring one order: 4 ÷ 50 = 0.08 orders a day, one every 12.5 days.

## Why 20 is tight

Component: `stock`

In 5 days customers take 20 parts on average, so an order placed at 20 should arrive just as the shelf empties. But demand is random: in almost half of the lead times more than 20 customers come, and the shelf is empty before the delivery.

## Stock-outs

Component: `stock`

About 3.6% of customers, some 135 in 950 days, find the shelf empty: each is a stock-out and waits for the next delivery. The shelf holds about 25.6 parts on average. Stock on the shelf costs money; too little costs customers.

## Parts sold

Component: `sold`

Every customer is served in the end, so 4 parts a day are sold. Averaged over everyone, a customer waits about half an hour, but that hides the few who meet an empty shelf: they wait about 15 hours.

## Exercise: safety stock

Component: `stock`

### Change

Set the store's `reorder_point` from 20 to 30, and run again. Each order is still 50 parts.

### Prediction

- [ ] Nothing changes: the shop still orders 50 parts at a time.
- [ ] Stock-outs halve, and the average stock rises by about 10 parts.
- [x] Stock-outs almost vanish, and the average stock rises by about 10 parts.

### Explanation

Ordering at 30 keeps 10 parts of safety stock above the 20 that a lead time needs on average. More than 30 customers in 5 days is rare, so stock-outs fall from about 135 to a handful in 950 days (theory: about 2.4). The price is 10 more parts on the shelf all the time, 35.5 on average.
