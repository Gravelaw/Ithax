# Staff rota

## People on each pattern

Component: `staff`

A shop opens every day. Each person works five days in a row and then has two days off, so there are seven patterns: `mon_fri` works Monday to Friday, `tue_sat` Tuesday to Saturday, and so on. The decision `staff` is the number of people on each pattern. It must be a whole number: the shop cannot hire 0.4 of a person. That makes this an integer programme.

## The goal: as few people as possible

Component: `objective`

The goal is to minimize the people hired: the staff on all seven patterns, added up. Everyone is paid for the same five days, so fewer people also means a smaller wage bill. The table `works` says which days each pattern covers, a 1 for a working day and a 0 for a day off.

## Every day covered

Component: `cover`

The limit `cover` repeats for each day: the people working that day, added over the patterns that include it, must be at least the day's need: 6 on Monday, 5 from Tuesday to Thursday, 7 on Friday, 8 at the weekend. That is 44 person-days, and each person gives 5, so at least 8.8 people. Whole people make it 9, and the solver finds a rota of 9.

## Exercise: allow fractions of a person

Component: `staff`

### Change

Change the kind of `staff` from integer to continuous, so that a pattern may hold a fraction of a person, and run again.

### Prediction

- [ ] Still 9: the needs have not changed.
- [x] 8.8: with fractions allowed, the rota meets every day exactly.
- [ ] 8: each fraction is rounded down to a whole person.

### Explanation

Fractions let the solver meet every day's need exactly, with no spare person: 44 person-days from 8.8 people. A real rota needs whole people, and 8.8 rounds up to 9 here. Rounding does not always work: in larger rotas the rounded plan can break a limit or waste people, which is why integer programming searches whole-number plans directly.
