# How existing tools save models

Research item: spec 1, "Research before building", M1 · How existing tools save models.
Ticket AKS-85. Date: 2026-11-06.

## Question

How do JaamSim, CalculiX and OpenModelica save models, and what should the spec 1 model
file learn from them?

## Finding

**JaamSim** (Apache-2.0, discrete-event simulation; repository read at commit `d09e4e6`,
29 October 2026).

- A model is a plain-text configuration file (`.cfg`). Objects are declared by type,
  `Define Server { InspectPart  MachinePart }`, then set one keyword per line,
  `MachinePart ServiceTime { MachineDistribution }`.
- Values with units are written as a number and a unit token inside braces,
  `Simulation RunDuration { 100000  min }`; inside expressions the unit goes in brackets,
  `this.data(1)*1[min]`.
- Each object names the next one (`NextComponent`, `NextComponentList` on a branch); there
  is no separate list of connections and no named ports.
- Every distribution object carries its own `RandomSeed` input, set by the modeller (1 to 4
  in the factory example listed under Sources).
- Saving (`InputAgent.printNewConfigurationFileWithName`) copies the original file
  verbatim up to a `RecordEdits` marker, adds the marker if it is missing, then writes
  only the objects added and the inputs marked as edited (`isEdited()`), grouped by type
  with `# *** <type> ***` headers. Graphics inputs are written last, under
  `# *** GRAPHICS INPUTS ***`. An input nobody edited is not written, so its default
  stays implicit.

**CalculiX** (finite element solver; CalculiX CrunchiX User's Manual 2.23, 19 October
2025).

- The input deck `jobname.inp` is keyword cards (`*NODE`, `*MATERIAL`, `*STEP`, ...) with
  parameters on the card line and comma-separated data lines below. It is case
  insensitive and blanks carry no meaning (section 7).
- It has no units. Section 3: "Finite element programs do not know any units. The user has
  to take care of that." Section 7: "The user must make sure that all data are given in
  consistent units (the units do not appear in the calculation)." The manual's table 1
  lists the same material constants in the {m, kg, s, K}, {mm, N, s, K} and {cm, g, s, K}
  systems, because a wrong system is not detected by the program.
- Model definition cards come before the first `*STEP`; step cards follow.

**OpenModelica** (OMEdit, User's Guide 1.28.0-dev).

- A model is Modelica source text. A class or package can be stored as one `.mo` file, or
  as a directory with `package.mo`, one file per class, and an optional `package.order`
  file that keeps element order (Modelica 3.7, section 13.4). Files are UTF-8; a leading byte
  order mark is deprecated (section 13.4).
- Diagram and icon graphics are stored in the same text as annotations: shapes drawn on
  the diagram view are added to the model's diagram annotation (User's Guide, OMEdit).
- "Save Total" writes a class and every class it uses into one file.

What spec 1 should take from this:

1. **Explicit units are the right call.** CalculiX shows the cost of unitless input: unit
   mistakes are silent and the user carries the burden. Spec 1 writes every physical
   quantity with its unit and converts to SI at load. A later physics adapter (spec 6)
   that drives CalculiX converts from SI in `translate`, so the user never chooses a
   consistent unit system by hand.
2. **Layout lives in the model file, apart from what the engine reads.** JaamSim writes
   graphics inputs in their own section; Modelica keeps them in annotations. Spec 1's `ui`
   key does the same.
3. **Explicit connections with ports are better for an editor.** JaamSim stores wiring as
   a `NextComponent` on the sender. Spec 1 keeps a separate `connections` list with named
   ports, which a branch with several outputs needs (spec 1 "What the prototype changed",
   item 2) and which makes a dangling or doubled connection a checkable error (E130 to
   E132).
4. **Random streams by identifier, not by hand-set number.** JaamSim asks the modeller for
   a unique `RandomSeed` per distribution. Spec 1 derives each component's stream from the
   experiment seed, the replication and the component id, so adding a component leaves the
   other streams unchanged and nobody has to keep seed numbers unique.
5. **Writing a model back.** JaamSim writes only edited inputs and keeps hand-written text
   above its marker. The equivalent for spec 1, when the service applies an edit (spec 3,
   M6), is to write back only keys the file already has or the edit sets, never to fill in
   defaults (spec 1 "Versioning" already fills defaults in memory only), and to keep key
   order so that a file under version control gets small diffs. Spec 3 does not yet say
   how an edited file is written. This is a point for the M6 research, not an M1 change.

## Sources

Engine documentation and source code first.

- JaamSim repository and README (licence Apache-2.0): https://github.com/jaamsim/jaamsim
  (opened 2026-11-06); sparse clone of the `*.cfg` files at commit
  `d09e4e67a2ac73e418e86782e7fbe84b4d8c125d`
- JaamSim example `src/main/resources/resources/examples/Factory Example - 1) with input file.cfg`
  in that clone (read 2026-11-06)
- JaamSim source `src/main/java/com/jaamsim/input/InputAgent.java`, method
  `printNewConfigurationFileWithName`:
  https://raw.githubusercontent.com/jaamsim/jaamsim/master/src/main/java/com/jaamsim/input/InputAgent.java
  (downloaded and read 2026-11-06)
- JaamSim home page (licence statement): https://jaamsim.com/ (opened 2026-11-06)
- G. Dhondt, *CalculiX CrunchiX User's Manual version 2.23*, 19 October 2025, sections 3
  "Units" and 7 "Input deck format": http://www.dhondt.de/ccx_2.23.pdf (downloaded and
  read 2026-11-06)
- OpenModelica User's Guide, OMEdit chapter (v1.28.0-dev):
  https://openmodelica.org/doc/OpenModelicaUsersGuide/latest/omedit.html (opened
  2026-11-06)
- Modelica Language Specification 3.7, chapter 13 "Packages" (file system mapping):
  https://specification.modelica.org/maint/3.7/packages.html (opened 2026-11-06)

## Decision

No change to spec 1. The findings support choices spec 1 already makes: explicit units
converted to SI at load, a `ui` key for layout, a separate `connections` list with named
ports, and random streams derived from component ids.

Carried forward, not acted on now:

- M6 (spec 3, model edits): write back only keys the file has or the edit sets, never
  materialise defaults, and keep key order. To be settled in the M6 research and written
  into spec 3 then.
- Spec 6 (physics adapters): convert SI quantities to the engine's own consistent unit
  system inside `translate`.

## Tested

- The JaamSim save behaviour was read in the source (`InputAgent.java`, lines 855 to 900
  and 1040 to 1080 of the file downloaded on 2026-11-06), not inferred from the files.
- The JaamSim syntax quoted above was checked against the example configuration file in
  the clone.
- The CalculiX quotations were checked against the text of the manual PDF, extracted with
  `pdftotext`.
- No engine was run: none of the decisions above depends on engine behaviour.
