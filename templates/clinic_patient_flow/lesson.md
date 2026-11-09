# Clinic patient flow

## Patients arrive

Component: `patients`

Patients arrive at random, one every 5 minutes on average, or 12 an hour. The run is 200 hours long, and the first 10 hours are warm-up, so the results cover the remaining 190 hours: about 2,280 patients.

## Reception routes each patient

Component: `reception`

Reception sends each patient one way at random: 3 in 5 to a check-up in an exam room, 2 in 5 to have a dressing changed in a treatment room. A branch with weights 3 and 2 splits the 12 patients an hour into about 7.2 check-ups and 4.8 dressings.

## The rooms

Component: `exam_rooms`

There are 3 exam rooms and 3 treatment rooms, and either visit takes 8 minutes on average. An exam room is in use 7.2 × 8 ÷ 60 ÷ 3, about 32% of the time; a treatment room about 21%. Rooms are plentiful: they are not what patients wait for.

## Shared nurses

Component: `nurses`

Every visit needs one of the 2 nurses, whichever room it is in. The nurses are a resource pool shared by both kinds of room. The clinic needs 12 × 8 = 96 nurse-minutes an hour out of 120, so the nurses are busy 80% of the time. A patient waits in a room until a nurse is free.

## Who waits

Component: `exam_rooms`

The nurses see patients in turn, so the clinic as a whole is a queue with 2 servers (Erlang C): the average wait is about 14 minutes. Check-ups wait longer, about 16 minutes against 11 for dressings: when all 3 exam rooms are taken, the next check-up waits for a room while dressings go ahead.

## Going home

Component: `home`

Patients leave at 12 an hour, as many as arrive. Each spends about 22 minutes in the clinic, 8 of them with a nurse. On average 4.4 patients are inside: Little's law, 12 an hour × 22.2 minutes.

## Exercise: one more nurse

Component: `nurses`

### Change

Set the nurses' `capacity` from 2 to 3, and run again. The rooms stay as they are.

### Prediction

- [ ] Little changes: the rooms, not the nurses, were the limit.
- [ ] The wait falls by about a third, in step with the extra nurse.
- [x] The wait falls from about 14 minutes to under 2, though the nurses are still busy half the time.

### Explanation

With 3 nurses they are busy about 53% of the time, and the average wait falls from about 14 minutes to about 1.6 (Erlang C with 3 servers). Time in the clinic drops from about 22 to under 10 minutes. Near full use, a little extra capacity removes most of the waiting.
