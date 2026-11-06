# Spec 3 research: interface study (M9)

## Question

How do JaamSim, PrePoMax, AnyLogic and FlexSim lay out the canvas, the palette, the properties and the results, and what do their users praise and complain about? (Spec 3, "Research before building", M9 · Interface study.)

## Finding

### Layout

All four tools use the same three-column arrangement: a palette or tree on the left, the model in the centre, the selected object's properties on the right. They differ in where results go.

| Tool | Palette | Canvas | Properties | Results |
| --- | --- | --- | --- | --- |
| JaamSim (Apache-2.0, Java) | "Model Builder": palettes of objects dragged and dropped into a View window; hovering shows a description; F1 opens help for the object | "View window", a 3D scene; several views can be defined | "Input Editor": the selected object's inputs grouped under tabs, with a Default column and a Value column, edited like a spreadsheet; an invalid input shows an error message giving its cause | "Output Viewer": present values of the selected object's outputs; tooltips describe each output |
| PrePoMax (open source, CalculiX front end) | A model tree in three tabs, Geometry, Model and Results, each with a search box | A 3D view (VTK) | Property forms for materials, loads and other model items | The Results tab of the tree; 3D scalar fields with animation, and 2D plots of history output |
| AnyLogic (commercial) | "Palette view": model elements grouped in stencils | "Graphical editor", one diagram per agent type | "Properties view" for the selected items | Not described on the pages read; Problems, Search and Console views can be opened |
| FlexSim (commercial) | Left pane: "Library" of objects, sharing the pane with the "Toolbox" of tools (Process Flow, Dashboards, Global Tables) | Centre pane: the 3D model | Right pane: "Properties" of the selected object; during a run it also shows statistics | Dashboards and tables open as tabs in the centre |

Interaction details worth copying:

- **Generated names.** JaamSim names a dropped object by appending a number to its type (`DisplayEntity1`, `DisplayEntity2`); spec 3 already asks for the same (`server_2`).
- **Renaming in place.** JaamSim renames with F2 or a double-click on the label, accepted with Enter, cancelled with Escape; the Object Selector is a tree of every object, so an object can be found without the canvas.
- **Adding without dragging.** FlexSim offers three ways to add an object: drag from the Library, a "Quick Library" opened by double-clicking empty space, and a "Create Objects" mode (click the Library item, then click the model; Escape leaves the mode). This matters for WCAG 2.2 success criterion 2.5.7 (dragging movements).
- **Undo.** JaamSim's Input Editor undoes and redoes model changes with Ctrl+Z and Ctrl+Y.
- **Help at the point of use.** JaamSim and FlexSim both open the manual at the selected object.

### What users praise

- **Drag and drop with ready-made blocks.** AnyLogic reviewers: "The drag-and-drop interface and built-in libraries made it easy to visualize processes" (Software Advice). A FlexSim reviewer praises its "great 3D capability" and says "The conveyors library is also very easy to use" (GetApp).
- **Free and easy to install for teaching.** A JaamSim teacher (University of Zaragoza, 2017) names the open-source licence, "a very convenient graphic interface for modelling and animation" and the easy handling of common random numbers. A Rutgers teacher (2020) moved from Arena: JaamSim "is much faster, has way more appealing graphics, and runs on Macs".
- **Statistics while the model runs.** This is a documented feature rather than a quoted review: JaamSim's Output Viewer shows the present values of the selected object's outputs, and FlexSim's Properties pane shows statistics of the selected object during a run.

### What users complain about

- **Code is needed for anything beyond the basics.** AnyLogic reviews repeat that Java is needed: "you should know the JAVA for most of the task" (Capterra, Software Advice); "Dependencia de conocimiento de programación" from a lecturer of industrial engineers (Capterra, January 2026).
- **Steep learning curve and dated interface.** "The user interface feels very outdated compared to modern software ... especially for beginners who may find navigation cumbersome" (AnyLogic, Capterra, November 2025). FlexSim: "It's not very user friendly and a lot of issues are solved by trial and error" (GetApp).
- **Unclear errors.** AnyLogic: "error messages were sometimes hard to interpret" (Software Advice). GetApp's summary of 518 AnyLogic reviews: "debugging and error messages can be challenging".
- **No warning before an unstable model bogs down.** The Rutgers teacher: "It would be nice to have a way of warning unsophisticated students that they are generating entitites much faster than they are processing them, balooning their queues" (JaamSim forum, 2020; spelling as posted).
- **Dated tools around the canvas.** A FlexSim reviewer says the distribution-fitting tool's interface "dates back from Window 3.0 age", and asks for better contextual help (GetApp).
- **Unfinished blocks are errors.** A JaamSim teacher who left unconfigured blocks in a starter model got error messages and had to work around them (JaamSim forum, 2018).
- **Long expressions in one-line boxes, and no modular reuse** (JaamSim forum, 2017).
- **Small text and icons.** A PrePoMax user asks for adjustable text and icon size: "they can be too small with some screen resolutions" (PrePoMax forum, 2022).

## Sources

Read on 2026-11-06.

- JaamSim User Manual, version 2021-04, chapter 4 "Graphical User Interface" (pages 45 to 62, read as extracted text): https://jaamsim.com/docs/JaamSim%20User%20Manual%202021-04.pdf
- JaamSim repository README (licence): https://github.com/jaamsim/jaamsim
- JaamSim users group, "Teaching Simulation using JaamSim" thread (posts of 2017-04-19, 2018-02-13, 2020-05-17): https://groups.google.com/g/jaamsim-users/c/vRImCR4BD-E
- PrePoMax home page: https://prepomax.fs.um.si/
- PrePoMax UI components (third-party code documentation of a PrePoMax fork; used only for the tree and form layout): https://deepwiki.com/tsvilans/PrePoMax/10-ui-components
- PrePoMax forum, "A few small features for convenience": https://prepomax.discourse.group/t/a-few-small-features-for-convenience/130
- AnyLogic Help, "AnyLogic UI": https://anylogic.help/anylogic/ui/workspace.html
- AnyLogic Help, "Graphical editor": https://anylogic.help/anylogic/ui/graphical-editor.html
- Capterra, AnyLogic reviews: https://www.capterra.com/p/95940/AnyLogic/reviews/
- Software Advice, AnyLogic reviews: https://www.softwareadvice.com/simulation/anylogic-profile/reviews/
- GetApp, AnyLogic review summary: https://www.getapp.com/it-management-software/a/anylogic/
- FlexSim documentation 24.1, "Overview of the FlexSim User Interface": https://docs.flexsim.com/en/24.1/FlexSimUI/OverviewUserInterface/OverviewUserInterface.html
- FlexSim documentation 20.2, "Adding 3D Objects to a Model": https://docs.flexsim.com/en/20.2/Using3DObjects/WorkingWith3DObjects/AddingObjects/AddingObjects.html
- GetApp UK, FlexSim reviews: https://www.getapp.co.uk/software/125363/flexsim

Review sites show a sample of reviews. The quotes are individual opinions, not measurements.

## Decision

The design in `docs/design/` follows the shared layout and answers the complaints:

1. **Three columns:** palette on the left, canvas in the centre, side panel on the right with the selected block's settings. A navigation rail on the far left switches the seven screens of spec 3. A problems list sits under the canvas.
2. **No code anywhere.** Settings are forms generated from `GET /v1/schema/components/{type}`. Distributions are a type picker plus labelled fields. There are no expression fields. This is spec 0's promise, and the main complaint about AnyLogic.
3. **Errors in plain words, at the block.** Each issue shows as a marker on its block and as an entry in the problems list, with the spec 1 `message` and `hint`. Selecting the entry selects the block. W201 (unstable server) is a warning that is visible before the run, which answers the Rutgers teacher's request.
4. **Adding without dragging.** As well as dragging, a palette item can be clicked and then placed with one click, or added with Enter at the centre of the view. This copies FlexSim's create mode and meets WCAG 2.2 success criterion 2.5.7.
5. **Generated ids and renaming** follow JaamSim: `<type>_<n>`, F2 to rename, Enter to accept, Escape to cancel.
6. **Text size is a setting** (100% to 200%), answering the PrePoMax request, and WCAG 2.2 success criterion 1.4.4.
7. **Results are a screen of their own**, with findings first (spec 3, Screen 6), rather than a per-object output viewer. The side panel also shows the selected block's last-run key numbers, as JaamSim and FlexSim do.
8. **Not copied:** 3D views (Phase 3, spec 6), multiple views of one model, and modular sub-models. Sub-models are left for a later phase; see `spec-3-node-editor-patterns.md`.

## Tested

Not tested: no interface code exists. The owner's walkthrough with a student and a business user (spec 3 "Design before building") tests these choices.
