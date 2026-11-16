# Spec 5 research: People methods (ergonomics, human reliability, work measurement, workforce)

## Question

Spec 5 "People in models", items (a) workforce in process models and (d) ergonomics and
human reliability, and the research item "licences of assessment methods (some
time-standard systems such as MTM are proprietary)". For each method: who publishes it,
whether its text may be used and implemented, its formula or table structure, a published
worked example usable as a calculator test, and whether it fits the calculator rule
(build guide rule 7: a closed-form formula or published empirical law, citing its formula,
tested against a published worked example). For workforce: which learning, fatigue and
absenteeism settings could extend spec 2's `resource_pool` and `schedule`. Engines are in
`spec-5-people-engines.md`.

## Finding

### Summary

| Method | Publisher | Use and implement | Structure | Worked example read | Calculator? |
| --- | --- | --- | --- | --- | --- |
| Revised NIOSH lifting equation | NIOSH (US government), Applications Manual, DHHS (NIOSH) 94-110, revised Sept. 2021 | Public domain: "This document is in the public domain and may be freely copied or reprinted" (manual, front matter) | Product of seven factors | Yes, primary source; reproduced (below) | Yes |
| RULA | McAtamney & Corlett 1993, Applied Ergonomics 24(2) 91–99 | Paper under copyright (publisher not verified); author's 2024 notes say "Complete the RULA scoring using the tables from the original article or a reputable online RULA tool"; no licence for software found | Body-part scores, three lookup tables (A, B, C), action levels | Secondary only (ErgoPlus guide); original paper not read | Yes (table lookups), after the legal check |
| REBA | Hignett & McAtamney 2000, Applied Ergonomics 31(2) 201–205 | As RULA; no licence found | Body-part scores, tables A, B, C, activity score, risk levels | None read with all numbers | Yes, after the legal check and a primary example |
| HEART | J. C. Williams (1985 SaRS symposium; 1986/1988 papers) | Papers under copyright; method widely applied; no licence terms found | Nominal unreliability of a generic task type times EPC effects | Secondary only (Wikipedia); reproduced | Yes, once the tables are taken from a primary source |
| SPAR-H | US NRC / Idaho National Laboratory, NUREG/CR-6883 (INL/EXT-05-00509), August 2005 | US NRC report, free to download; no copyright notice in its text (searched) | Nominal HEP times PSF multipliers, with an adjustment | Yes, primary source; reproduced (one rounding difference) | Yes |
| MTM | MTM ASSOCIATION e. V. | Proprietary: trademarks, copyrighted data cards, licensed training | Predetermined motion times | Not applicable | No |
| MOST | H. B. Maynard and Company (now Accenture, per distributor) | Proprietary (trademark; licensed distributors) | Predetermined sequence models | Not applicable | No |

### Revised NIOSH lifting equation

- Source read: NIOSH [1994], Applications manual for the revised NIOSH lifting equation,
  by Waters TR, Putz-Anderson V, Garg A; revised September 2021,
  doi:10.26616/NIOSHPUB94110revised092021 (CDC Stacks, `cdc_110725_DS1.pdf`). The
  equation's research paper (Waters et al. 1993, Ergonomics) was not read.
- RWL = LC × HM × VM × DM × AM × FM × CM (section 1.3). Metric: LC 23 kg, HM = 25/H,
  VM = 1 − 0.003|V − 75|, DM = 0.82 + 4.5/D; US: LC 51 lb, HM = 10/H, VM = 1 − 0.0075|V −
  30|, DM = 0.82 + 1.8/D; AM = 1 − 0.0032A in both; FM from Table 5 (lifts per minute ×
  duration ≤1 h, 1–2 h, 2–8 h × V < 30 in or ≥ 30 in); CM from Table 7 (good, fair, poor ×
  V < 30 in or ≥ 30 in: 1.00/1.00, 0.95/1.00, 0.90/0.90). Lifting index LI = load / RWL.
  Limits are in the text (e.g. HM = 1 for H ≤ 10 in, HM = 0 for H > 25 in; AM = 0 for
  A > 135°).
- The manual: "Each multiplier should be computed from the appropriate formula", with
  linear interpolation in the frequency table. Its worksheets, however, use table values
  rounded to two decimals (Table 1 prints HM .44 for H = 23 in, while 10/23 = 0.4348).
- Example 1 ("Loading Punch Press Stock", section 3.2.1): load 44 lb, H 23 in, V 15 in
  (origin) and 63 in (destination), F < 0.2 lifts/min, under 1 h, A 0, coupling fair.
  Printed: RWL 16.3 lb (origin) and 14.5 lb (destination), LI 2.7 and 3.0; modified job
  (H 10 and 12 in, poor coupling) RWL 35.1 and 24.6 lb, LI 1.3 and 1.8. Reproduced with
  table-rounded multipliers (16.32, 14.47, 35.13, 24.57 lb); with unrounded formulas the
  results are 16.03, 14.31, 34.93, 24.68 lb, up to 1.7 % off the printed values.
- The metric and US constants are not exact conversions (23 kg against 51 lb = 23.13 kg),
  so the same task gives slightly different RWLs in the two systems.

### RULA and REBA

- RULA: McAtamney and Corlett 1993, Applied Ergonomics 24(2), 91–99 (citation from the
  ErgoPlus guide; paper not read). REBA: Hignett and McAtamney 2000, "Rapid Entire Body
  Assessment", Applied Ergonomics 31, 201–205 (citation from search results; paper not
  read).
- Rights: the papers are copyrighted journal articles. A 2024 note by the author ("Notes for
  using RULA", Cornell ergonomics site, "© Dr Lynn McAtamney, 2024") tells assessors to use
  "the tables from the original article or a reputable online RULA tool"; that supports use
  of the method but is not a licence to publish the tables in software. Under copyright law
  a method itself is usually not protected while its expression is; whether the score
  tables are protectable expression is a legal question. Unverified; a lawyer confirms.
- Structure (RULA): group A (upper arm, lower arm, wrist, wrist twist) → Table A; plus
  muscle use and force scores; group B (neck, trunk, legs) → Table B; plus muscle and force;
  Table C gives the grand score 1–7; action levels 1–4.
- Worked example read (secondary): ErgoPlus RULA guide: upper arm 4, lower arm 2, wrist
  4, twist 1 → Table A 5; muscle 0, force +2 → 7; neck 3, trunk 2, legs 1 → Table B 3;
  muscle 0, force +2 → 5; Table C → final score 7. Not reproduced, because the tables were
  not read from the paper.
- REBA: no worked example with every number was read. Search results quoting a
  third-party guide were incomplete and inconsistent, so none is recorded.

### HEART

- Formula: HEP = nominal unreliability of the generic task type (GTT) × Π over chosen
  error producing conditions (EPC) of ((maximum effect − 1) × assessed proportion + 1).
  The GTT and EPC tables come from Williams' papers (not read).
- Example read on the English Wikipedia page "Human error assessment and reduction
  technique" (2026-11-16): GTT F, 0.003; EPCs ×3 at 0.4, ×6 at 1.0, ×4 at 0.8, ×2.5 at 0.8,
  ×1.2 at 0.6; effects 1.8, 6.0, 3.4, 2.2, 1.12; HEP 0.27. Reproduced: 0.2714. The page
  cites Williams 1985 (SaRS symposium, NEC Birmingham); the example's primary source is not
  given there.
- The "assessed proportion" is the assessor's judgement; a calculator takes it as an
  input.

### SPAR-H

- Source read: D. Gertman, H. Blackman, J. Marble, J. Byers, C. Smith (Idaho National
  Laboratory), "The SPAR-H Human Reliability Analysis Method", NUREG/CR-6883,
  INL/EXT-05-00509, US NRC, published August 2005 (from `nrc.gov/.../cr6883/cr6883.pdf`).
- NHEP 0.01 for diagnosis, 0.001 for action; composite PSF = product of the eight PSF
  multipliers (available time, stress, complexity, experience and training, procedures,
  ergonomics and HMI, fitness for duty, work processes); with three or more negative PSFs,
  HEP = NHEP × PSFc / (NHEP × (PSFc − 1) + 1) (section 2.5). Worksheets with the PSF levels
  are in the appendices; dependency between tasks follows THERP levels (section 2.6).
- Section 2.5.1, example 1 (diagnosis; procedures misleading 10, ergonomics poor 20,
  complexity moderate 2): printed unadjusted 4.0 and adjusted 0.81. Reproduced: 4.0000 and
  0.8016, which rounds to 0.80, not 0.81 (0.01 × 400 / 4.99). Example 2 (action; 0.8, 0.8,
  0.1): printed 6.4E-5 and 6.41E-5; reproduced 6.400e-05 and 6.4060e-05.
- Note: example 2 has no negative PSF yet the report applies the adjustment ("The
  adjustment factor is also applicable in situations ... where the positive influence of
  PSFs is present"). The rule for when to adjust needs one reading in the spec.

### MTM and MOST

- MTM: "MTM-1, MTM-2, MTM-UAS, MTM-MEK, MTM-SD, MTM-HWD, MTM-LOG und EAWS are registered
  trademarks of MTM ASSOCIATION e. V. All rights reserved." (MTM Qualification Procedures,
  APO 2024, English edition, which is itself "subject to copyright ... No part of this
  publication may be ... reproduced ... without the prior written permission"). The MTM-1
  data card is part of the mandatory training materials "published by MTMA"; practitioners
  qualify through licensed instructors. Confirmed proprietary. EAWS (an ergonomics
  worksheet) is an MTM trademark too.
- MOST: "MOST is a registered trademark of H. B. Maynard and Company, Inc." and a UK
  distributor's statement that it is registered to Accenture, with certification and
  analyst cards issued by H B Maynard (now Accenture) (from search results summarising
  Wikipedia and scott-grant.co.uk; pages not read in full). Treated as proprietary;
  unverified in detail.
- Ithax can still use time standards the user owns: a user who holds MTM or MOST studies
  enters the resulting times as service-time settings.

### Workforce settings (spec 2 extensions)

- **Learning curve.** Crawford's unit theory T_x = T_1 x^b, b = ln(slope)/ln 2 (Wright's
  1936 cumulative-average form differs). Published table read: G. K. Mislick (Naval
  Postgraduate School), "Cost Estimation, Chapter 10, Learning Curves: Unit Theory", ICEAA
  2016 training TRN 03, slide "80% Learning Rate Example": T_1 = 1000, b = −.3219, units 1,
  2, 3, 4, 5, 10, 50, 100, 500, 1000 = 1000, 800, 702, 640, 596, 477, 284, 227, 135, 108.
  All ten reproduced after rounding. As a setting: a server's service time for the n-th
  item of a worker, product or run is multiplied by n^b, with a floor (a plateau) as an
  optional setting. This is a closed-form multiplier, a calculator inside the engine.
- **Absenteeism.** Each unit of a `resource_pool` is absent for a whole shift with a given
  probability, drawn at the shift start from the pool's own stream (spec 1 stream scheme).
  Equivalent to a schedule with random capacity; uses no formula beyond a Bernoulli draw.
  No source needed beyond the user's data; none read.
- **Skill.** Pool units carry skills; a server names the skill it needs. A setting, not a
  formula. Rules for choosing among eligible units are a design choice to specify.
- **Fatigue.** No published model was read in this session. Candidates (unverified, not
  read): service-time multipliers rising with time on shift and recovering in breaks,
  rest-allowance tables from work-measurement texts. Left open.

## Sources

- NIOSH [1994], Applications manual for the revised NIOSH lifting equation, revised
  September 2021, `https://stacks.cdc.gov/view/cdc/110725/cdc_110725_DS1.pdf`, read
  2026-11-16 (sections 1.3, 3.2.1, Tables 1, 5, 7, front matter).
- L. McAtamney, "Notes for using RULA" (OSAR), `https://ergo.human.cornell.edu/OSAR%20for%20RULA.pdf`,
  read 2026-11-16.
- ErgoPlus, "RULA assessment tool guide", `https://ergo-plus.com/rula-assessment-tool-guide/`,
  read 2026-11-16.
- Wikipedia, "Human error assessment and reduction technique", read 2026-11-16.
- NUREG/CR-6883, `https://www.nrc.gov/sites/default/files/doc_library/cdn/legacy/reading-rm/doc-collections/nuregs/contract/cr6883/cr6883.pdf`,
  read 2026-11-16 (section 2.5).
- MTM ASSOCIATION e. V., "APO Qualification Procedures 2024",
  `https://training.mtm.org/data/MTM-LMS/seminarkatalogbilder/APO_with%20Appendix_2024_EN1.pdf`,
  read 2026-11-16; `https://mtm.org/en/education-1/blue-green-card` ("Copyright © 2020–2026
  MTM ASSOCIATION e. V."), read 2026-11-16.
- MOST: search results for Wikipedia "Maynard operation sequence technique" and
  `scott-grant.co.uk`, 2026-11-16 (not read in full).
- G. K. Mislick, ICEAA 2016 TRN 03, `https://www.iceaaonline.com/wp-content/uploads/2016/10/TRN03-Learning-Curve.pdf`,
  read 2026-11-16.
- Not read: Waters et al. 1993; McAtamney & Corlett 1993; Hignett & McAtamney 2000;
  Williams 1985/1986/1988; Kirwan 1994; Wright 1936; Crawford 1947; GAO cost guide
  (403 from this container).

## Decision

Proposed defaults (owner to confirm):

- **Phase 2, detail now:**
  - NIOSH lifting equation calculator: public domain; test against example 1 and its
    modification (four RWL and LI values). Compute multipliers from the formulas, metric
    constants after unit conversion at load, and test the printed values with a tolerance
    of 2 % (they come from rounded table values); interpolate FM linearly as the manual says.
  - SPAR-H calculator: public NRC report; test against examples 1 and 2 of section 2.5.1;
    record that example 1 prints 0.81 where the formula gives 0.8016.
  - Learning curve setting on `server` (Crawford unit form): test against the ICEAA table.
  - Absenteeism setting on `resource_pool` (per-unit, per-shift absence probability on the
    pool's stream): test by a deterministic and a statistical benchmark (mean available
    capacity = capacity × (1 − p)).
- **Phase 2, after one more source:** HEART calculator, once the GTT and EPC tables and a
  worked example are read in a primary or authoritative source (Williams 1988 or Kirwan
  1994); the Wikipedia example is a second test only.
- **Phase 2 or 3, after the legal check:** RULA and REBA calculators, from the tables of
  the original papers, with a worked example from those papers or the author's material.
- **Open:** fatigue model; skill-matching rules.
- **Excluded:** MTM, MOST and EAWS data. Users enter their own standard times.

Open questions, blocking:

- Workforce settings (learning curve, absenteeism, skill) change the spec 2 model format
  and the process engine; which ones enter Phase 2 (model format, milestone)?
- NIOSH: formula values or the manual's rounded table values? The two differ by up to
  1.7 % in example 1 (user-visible answer). Proposed: formulas, as the manual says.
- SPAR-H: apply the adjustment only with three or more negative PSFs (the worksheets'
  rule) or also as in example 2? Changes a user-visible answer.
- RULA/REBA: may Ithax ship the scoring tables? A lawyer confirms (blocks those two
  calculators only).

Open questions, reversible:

- Whether HEART's assessed proportions are free inputs (proposed) or chosen from fixed
  steps.
- Whether calculators report NIOSH in both unit systems or only in the model's units
  (proposed: model units, after conversion).

## Tested

All on 2026-11-16 with Python 3.12, standard library only (`python3 -I`). Each script holds
its source and the printed values in its docstring; output is stored beside it.

- `docs/research/spec-5-trials/people-niosh/niosh_example1.py`, `output.txt`:

  | Case | Formula RWL (lb) | Table-rounded RWL (lb) | Printed RWL | LI (rounded) | Printed LI |
  | --- | --- | --- | --- | --- | --- |
  | Example 1, origin | 16.03 | 16.32 | 16.3 | 2.70 | 2.7 |
  | Example 1, destination | 14.31 | 14.47 | 14.5 | 3.04 | 3.0 |
  | Modified, origin | 34.93 | 35.13 | 35.1 | 1.25 | 1.3 |
  | Modified, destination | 24.68 | 24.57 | 24.6 | 1.79 | 1.8 |

- `docs/research/spec-5-trials/people-hra/hra_examples.py`, `output.txt`: SPAR-H example 1
  unadjusted 4.0000 (printed 4.0), adjusted 0.8016 (printed 0.81); example 2 unadjusted
  6.400e-05 (printed 6.4E-5), adjusted 6.4060e-05 (printed 6.41E-5). HEART Wikipedia example
  0.2714 (printed 0.27).
- `docs/research/spec-5-trials/people-workforce/learning_curve.py`, `output.txt`:
  b = −0.3219 (printed −.3219); all ten tabulated units match after rounding (e.g. unit 3:
  702.10 against 702; unit 100: 227.06 against 227).
- Not run: RULA and REBA (tables not read from the papers); a HEART case from a primary
  source; fatigue and absenteeism (no engine change in a research note; absenteeism needs
  the process adapter).
