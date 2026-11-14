# Rate units in throughput constraints (#77)

Written 2026-11-14 for M13, before the change. Issue #77 (E1, M1-7): 30 per hour must be
written `0.008333` today, and the format should accept, for example, `"30 1/h"`, as an
additive change.

## What spec 1 already said

- "Metric names" said a rate is a plain number of items per second because Phase 1 has no
  rate unit, and that "a rate unit such as `1/h` would be an additive minor version".
- "Versioning" says a minor increase is additive and needs no migration. A reader opens any
  file of its major whose minor is no higher than its own.
- The precedent is format 0.2 (AKS-123). A key that 0.2 added, found in a file of an older
  minor, is E100 with a hint to set `format_version`, because a reader of that minor would
  not know it.

## The units

- **Which units.** Rates are the time units inverted: `1/s`, `1/min`, `1/h` and `1/d`. They
  are written exactly so, case matters, and they follow the "Quantities" grammar (a JSON
  number, one space, the unit).
- **How they convert.** pint 0.25 converts each to items per second, dimensionality
  `[time]⁻¹`. For example, `30 1/h` gives 0.008333…, `0.5 1/min` gives 1/120 and `48 1/d`
  gives 1/1800. Checked in this session.
- **Spellings that are refused.** pint's `parse_unit_name` reads none of these as a single
  unit name, so the loader's check that the unit is "known in another dimension" says no,
  and they are E141: `30 /h`, `30 1/hour`, `30 per hour`, `30 1/H`, `30 1/m`.
- **Where they apply.** Only in a constraint on a rate: `throughput`, `orders` or
  `discarded`. Every distribution setting is still a time, and a rate unit there is E140
  (a Phase 1 unit of another dimension). Before, it would have been E141, because pint does
  not parse `1/h` as a unit name.
- **How a value is read.** A constraint's `value` is read as a time or a rate by the unit it
  is written in. The meaning pass then checks the kind against the metric (E123): a time
  for `wait.mean` or `cycle_time.mean`; a rate or a plain number for a rate; a plain number
  for anything else. A plain number of items per second stays valid for a rate, so no file
  changes meaning.

## The version

- The reader becomes 0.3, and a new project is written as 0.3.
- A rate unit in a `process` constraint's `value` in a file of 0.0 to 0.2 is E100 at that
  `value`. The hint says to set `format_version` to `"0.3"`, or to write the plain number,
  and gives the plain number.
- An older reader would have reported E141 for that value, so the version is what tells a
  reader whether it can read the file.

## Where the value goes

The experiment manager's search compares constraint values in SI units, through
`magnitude`, so a rate quantity is judged exactly as its plain number. The interface
already sends text it cannot read as a number unchanged, so `"30 1/h"` reaches the service
as written.

## Review of PR #165: conversions near the float limit

Two review findings showed one class. A written number beyond a float, in a unit below 1,
was refused (`"1e309 1/h"` is 2.8e305 per second), and an hourly figure computed as
`value * 3600` overflowed in a hint ("inf per hour").

Conversions now go through `ithax.model.units`:

- `UNIT_SIZES` holds each unit's exact size.
- `in_unit` converts exactly, and gives `None` beyond a float. Python's `Fraction`
  division and IEEE float division both round correctly, so a finite result is unchanged.
- `parse_quantity` scales exactly only when the written number is not a finite float.

A convention test bans hand-written unit factors elsewhere in `src`.

