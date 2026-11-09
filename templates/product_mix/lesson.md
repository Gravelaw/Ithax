# Product mix

## Two decisions

Component: `chairs`

A workshop makes chairs and tables. How many of each should it make in a week? Those two numbers are the decisions, `chairs` and `tables`. Each can be any amount from 0 upwards; a plan is one value for each. Linear programming finds the plan that is best for a stated goal while respecting every limit, and proves that no other plan does better.

## The goal: the most profit

Component: `objective`

A chair earns £45 and a table £80. The goal is to maximize the profit, 45 × chairs + 80 × tables. Tables earn more, so making only tables looks tempting. But each table also uses more of the scarce wood and labour, so the best plan balances the two products against the limits.

## Wood is limited

Component: `wood`

The workshop has 400 units of wood a week. A chair takes 5 units and a table 20, so 5 × chairs + 20 × tables must be at most 400. Wood alone would allow 20 tables and no chairs, or 80 chairs and no tables, or any mix in between.

## Labour is limited

Component: `labour`

There are 450 hours of labour: 10 a chair and 15 a table. The plans that meet both limits form a region with four corners: (0, 0), 20 tables, 45 chairs, and 24 chairs with 14 tables. The best plan of a linear programme is always at a corner. Here it is the last one: £2,200, using all the wood and all the labour.

## Exercise: tables earn more

Component: `tables`

### Change

Raise the table's profit in the goal from £80 to £100, and run again.

### Prediction

- [ ] The workshop switches to more tables and fewer chairs.
- [x] The plan stays at 24 chairs and 14 tables; the profit rises to £2,480.
- [ ] The workshop makes only tables, since they now earn more than twice as much.

### Explanation

The best plan is still the corner where wood and labour both run out. A corner stays best while the goal's slope lies between the slopes of the two limits that meet there; only the profit changes, by 14 × £20 = £280, to £2,480. The table's profit would have to pass £180 before making more tables paid.
