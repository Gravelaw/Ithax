# Transport plan

## Crates on each route

Component: `ship`

A wholesaler has three depots, north, centre and south, and four customers: city, harbour, park and market. The decision `ship` is the number of crates sent on each route from a depot to a customer. It is one decision repeated over two sets, depots and customers, so the plan has 3 × 4 = 12 amounts, such as `ship[north,city]`. Tables hold the numbers given for each depot, customer or route.

## The goal: the cheapest plan

Component: `objective`

Each route has a cost per crate, from £3 to £9, in the table `cost`. The goal is to minimize the total: the crates on every route times its cost, added up. Cheap routes are tempting, but a depot cannot send more than it holds, and every customer must get its order. The solver weighs all twelve routes at once and finds a plan that no other plan beats.

## Each depot's stock

Component: `supply`

The limit `supply` repeats for each depot: the crates a depot sends, added over the four customers, must be at most its stock in the table `supply`: 300 at north, 200 at centre and 250 at south. That is 750 crates for 720 ordered, so one depot will have crates left. In the best plan north keeps 30, while centre and south send everything.

## Each customer's order

Component: `demand`

The limit `demand` repeats for each customer: the crates a customer receives, added over the three depots, must be at least its order: 180, 220, 150 and 170. The best plan costs £2,690. Centre sends all 200 crates to the harbour at £3, south serves the park and part of the market, and north covers the rest. Sending crates on any unused route would raise the cost.

## Exercise: ten more crates at centre

Component: `supply`

### Change

Raise centre's stock in the table `supply` from 200 to 210 crates, and run again.

### Prediction

- [ ] Nothing changes: centre's crates already go on its cheapest route.
- [x] The cost falls by £30: centre sends 10 more crates to the harbour, saving £3 on each.
- [ ] The cost falls by £90: each extra crate saves the £9 of the dearest route.

### Explanation

Centre's 10 extra crates go to the harbour at £3 each, replacing 10 that north sent there at £6. North keeps 40 crates instead of 30, and the cost falls from £2,690 to £2,660. Each crate of stock at centre is worth £3 to the plan: the shadow price of its limit. Past 20 more crates the harbour is full, and further crates save less.
