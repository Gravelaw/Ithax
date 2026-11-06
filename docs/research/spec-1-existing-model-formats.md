# Existing model formats

Research item: spec 1, "Research before building", M1 · Existing model formats. Ticket AKS-85.
Date: 2026-11-06.

## Question

What can the spec 1 model file borrow from System Structure and Parameterization (SSP),
the FMI model description, Modelica, SysML v2 and the DEVS formalism?

## Finding

Current versions, read on 2026-11-06:

| Standard | Current version | What it stores |
| --- | --- | --- |
| SSP | 2.0.1 (release news dated 2026-05-05) | A ZIP archive with `SystemStructure.ssd` (XML system structure), plus parameter values (`.ssv`), parameter mappings (`.ssm`) and signal dictionaries (`.ssb`) |
| FMI | 3.0.2 | `modelDescription.xml`: the variables of one model unit, with units |
| Modelica | Language Specification 3.7 (2026); 3.8 is in development | Modelica source text (`.mo`) |
| SysML v2 | SysML 2.0, KerML 1.0 and Systems Modeling API and Services 1.0, formally adopted by OMG on 30 June 2025 (announced 21 July 2025); edited in March 2026 for submission to ISO | Textual and graphical notation; JSON schemas for KerML, SysML and the API are normative machine-readable files of the API specification |
| DEVS | Formalism (Zeigler 1976; second edition 2000) | Mathematical structure, not a file format |

What each one does that bears on spec 1:

1. **Components, ports and connections.** DEVS couples models only through ports. A coupled
   model is a set of components plus three coupling sets: external input (EIC), external
   output (EOC) and internal (IC), where an internal coupling joins an output port of one
   component to an input port of another. SSP connections name `startElement`,
   `startConnector`, `endElement` and `endConnector`; an absent element means a connector
   of the enclosing system. Spec 1's `{"from": "<id>.<port>", "to": "<id>.<port>"}` is the
   DEVS internal coupling, and is the same information as an SSP connection in one string
   per end. Spec 1 has no EIC or EOC because a Phase 1 model is flat (no nested systems).
2. **Unique names in a list.** FMI 3.0 (section 1.3) requires every `name` to be unique
   within its list. Spec 1 already requires unique identifiers within each list.
3. **Units.** FMI 3.0 (section 2.4.3) defines a unit as exponents of the seven SI base
   units plus `rad`, with a `factor` and an `offset`; the value in base units is
   `factor × value + offset`, and the offset is dropped when `relativeQuantity` is true.
   SSP 2.0.1 (section 4.4.2) says its units are "completely aligned" with FMI 3.0. Modelica
   (chapter 19) writes units as strings with no white space (`"kg.m/s2"`), reads `m` as
   metre, never milli, and lists minute, hour and day among the units every tool must
   know. Modelica 3.7 also has unitful literals such as `9.8'm/s2'`, converted to the
   component's unit in binding equations. All three convert to coherent SI. Spec 1 does the
   same: a quantity string is converted to SI at load.
4. **Absolute and relative quantities.** FMI (`relativeQuantity`) and Modelica (the
   `absoluteValue` annotation, section 18.17) both mark whether an offset applies. A
   temperature difference and a temperature are converted differently. Phase 1 quantities
   are times only, so nothing in spec 1 is affected now. A physics domain with temperatures
   (spec 6) needs the same distinction.
5. **Layout and tool data kept apart from the model.** Modelica keeps diagram positions in
   `Placement` annotations (section 18.9.2) and lets vendors add `__Vendor` annotations that
   other tools ignore (section 18.4). SSP stores tool-specific data in `Annotation`
   elements with a reverse-domain `type`. Spec 1's `ui` key, never read by an engine, is the
   same idea.
6. **Parameters.** FMI 3.0 (section 2.4.7.4) gives each variable a causality (`parameter`,
   `calculatedParameter`, `input`, `output`, `local`, `independent`, `structuralParameter`)
   and a variability (`constant`, `fixed`, `tunable`, `discrete`, `continuous`). SSP binds
   parameter values from inline or external `.ssv` sets; units apply only to real-valued
   parameters. Spec 1 parameters are all of one kind in FMI terms: a parameter fixed for
   the length of a run and changed between runs by scenarios and searches. Spec 1's
   `{"$param": ...}` reference and per-scenario `set` cover what SSP parameter bindings do.
7. **Hierarchy.** DEVS models are closed under coupling: a coupled model behaves as an
   atomic one and can be a component of a larger model. SSP systems also nest. Spec 1 is
   flat in Phase 1; if nesting is ever wanted, a sub-model component with its own ports is
   the DEVS way to add it without changing connections.
8. **Simultaneous events.** A DEVS coupled model needs a tie-breaking function (`Select`)
   for components scheduled at the same instant. Spec 2 ("Simultaneous events") already
   fixes the order: events at the same time run in the order they were scheduled.
9. **SysML v2** is a general systems engineering language, with its own textual notation
   and a standard API whose machine-readable files include JSON schemas. It is far wider
   than a process simulation file. Nothing in it is needed for Phase 1; it could become an
   export target later.

## Sources

Standard documents and specifications first, then papers.

- SSP home page, release 2.0.1: https://ssp-standard.org/ (opened 2026-11-06)
- SSP 2.0.1 specification, chapters 3 to 7 (archive, units section 4.4.2, annotations,
  connection section 5.3.2, parameter bindings and `.ssv`): https://ssp-standard.org/docs/2.0.1/
  (opened 2026-11-06)
- FMI 3.0.2 specification, sections 1.3, 2.4.3 and 2.4.7.4:
  https://fmi-standard.org/docs/3.0.2/ (opened 2026-11-06)
- Modelica Language Specification versions: https://specification.modelica.org/ (opened
  2026-11-06)
- Modelica 3.7, chapter 18 "Annotations": https://specification.modelica.org/maint/3.7/annotations.html
  (opened 2026-11-06)
- Modelica 3.7, chapter 19 "Unit expressions":
  https://specification.modelica.org/maint/3.7/unit-expressions.html (opened 2026-11-06)
- OMG press release of 21 July 2025 on the adoption of SysML 2.0, KerML 1.0 and the API:
  https://www.omg.org/news/releases/pr2025/07-21-25.htm (opened 2026-11-06)
- SysML v2 release repository README (adoption date 30 June 2025; March 2026 editorial
  update): https://github.com/Systems-Modeling/SysML-v2-Release (opened 2026-11-06)
- OMG Systems Modeling API and Services 1.0 (machine-readable files, including JSON
  schemas for KerML, SysML and the API): https://www.omg.org/spec/SystemsModelingAPI/
  (opened 2026-11-06)
- G. Wainer and C. Ruiz Martin, "Defining DEVS models using the Cadmium toolkit",
  Proceedings of the 2022 Winter Simulation Conference, section 2.2 (coupled models, EIC,
  EOC, IC, closure under coupling): https://informs-sim.org/wsc22papers/133.pdf (open
  access, opened 2026-11-06)
- "DEVS", Wikipedia (atomic and coupled model tuples, `Select`):
  https://en.wikipedia.org/wiki/DEVS (opened 2026-11-06; forum-level source, used only
  where it agrees with the paper above)
- Not opened, paywalled: B. P. Zeigler, H. Praehofer and T. G. Kim, *Theory of Modeling
  and Simulation*, 2nd edition, Academic Press, 2000, ISBN 978-0-12-778455-7.

## Decision

No change to spec 1. The current format already uses what is worth borrowing for Phase 1:

- typed components with named ports joined by directed connections (DEVS internal
  coupling, SSP connections);
- unique identifiers within each list (FMI);
- units written by the author and converted to coherent SI at load (FMI, SSP, Modelica);
- tool and layout data kept apart from the model in `ui` (Modelica annotations, SSP
  annotations);
- parameters that change between runs, referenced by name (FMI parameters, SSP bindings).

Not borrowed, with the reason:

- XML and ZIP packaging (SSP, FMI): spec 1 chose one JSON file; nothing found here argues
  against it.
- Causality and variability attributes (FMI): Phase 1 has one kind of parameter.
- Nested systems (DEVS, SSP): Phase 1 models are flat. A sub-model component is the
  natural way to add nesting later.
- SysML v2: wider than the product needs; a possible later export target.

Recorded for later specs, not acted on now:

- A physics domain with temperatures must distinguish absolute from relative quantities
  (FMI `relativeQuantity`, Modelica `absoluteValue`). This belongs in spec 6 when its
  detailed section is written.

## Tested

Nothing in this note needed a test: it compares documents and changes no behaviour. The
statements about spec 1 were checked against `docs/specs/1-model-format.md` at version 0.3,
and the statement about simultaneous events against `docs/specs/2-core-engine.md`
("Simultaneous events").
