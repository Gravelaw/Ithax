# Spec 3 research: icon set and typefaces (M9 design review)

## Question

The owner asked for icons on the nav rail buttons and the canvas buttons, and for a less "traditional ERP" look (`spec-3-engaging-design.md`). Which icon library should the interface bundle (React, offline, licence compatible with AGPL-3.0), and which open-licensed typefaces should replace "system fonts only" (design choice 11 in `docs/DECISIONS.md`) while keeping the app fully offline?

## Finding

### Icon libraries

An *icon library* here is a set of SVG icons (vector drawings) published as React components. *Tree-shaking* means the build keeps only the icons the code imports, so a 2,000-icon library costs only the few dozen icons used. All libraries below install from npm and are bundled into the app at build time, so nothing is fetched at run time.

How checked: `npm view <package> version license time` on 2026-11-06, then `npm pack` of each package into the session scratchpad and a read of its `LICENSE` file; icon counts are the number of SVG files in the package (one style); name coverage was checked by looking for each file name in the package.

| Library (npm package) | Version, release date | Licence (how checked) | Icons | Styles and weights | Tree-shaking |
| --- | --- | --- | --- | --- | --- |
| Lucide (`lucide-react`) | 1.70.0, 2026-11-06 | ISC (npm metadata; `LICENSE` in `lucide-static` 1.70.0: "ISC License, Copyright (c) 2026 Lucide Icons and Contributors") | 2,322 | One outline style; stroke width is a prop (`strokeWidth`, `absoluteStrokeWidth`) | Yes: `sideEffects: false`, one ES module per icon (about 0.7 KB for `house`) |
| Phosphor (`@phosphor-icons/react`) | 2.1.10, 2025-05-22 | MIT (npm metadata; `LICENSE` in the package: "MIT License, Copyright (c) 2020 Phosphor Icons") | 1,512 | Six weights: thin, light, regular, bold, fill, duotone (duotone adds a second layer at 20% opacity) | Yes: `sideEffects: false`, one module per icon; each icon carries all six weights (about 3 KB for `House`) |
| Tabler (`@tabler/icons-react`) | 3.50.0, 2026-10-27 | MIT (`LICENSE` in `@tabler/icons`: "Copyright (c) 2020-2026 Paweł Kuna") | 5,203 outline, 1,054 filled | Outline and filled; stroke width is a prop | Yes: `sideEffects: false` |
| Material Symbols (`@material-symbols/svg-400`) | 0.48.3, 2026-11-04 | Apache-2.0 (npm metadata and `LICENSE` in the package) | 3,940 (outlined, unfilled) | Outlined, rounded, sharp; fill on or off; the variable icon *font* adds weight and grade axes but is a large file | SVG files, imported one by one through an SVG loader; no official React component package |
| Heroicons (`@heroicons/react`) | 2.2.0, 2024-11-18 | MIT (`LICENSE` in `heroicons`: "Copyright (c) Tailwind Labs, Inc.") | 324 | Outline 24, solid 24, mini 20, micro 16 | Yes: `sideEffects: false` |
| Iconoir (`iconoir-react`) | 7.12.2, 2026-11-04 | MIT (`LICENSE` in `iconoir`: "Copyright (c) 2021 Luca Burgio") | 1,383 | Regular and solid | Yes: `sideEffects: false` |
| Remix Icon (`@remixicon/react`) | 4.9.0, 2026-01-29 | **"Remix Icon License 1.0"** (npm metadata of `@remixicon/react`; `License` file in `remixicon` 4.9.1, dated January 2026). npm still lists `remixicon` itself as Apache-2.0, but the file inside says otherwise | 3,229 (line and fill) | Line and fill | Yes |

**Licence and AGPL-3.0.** ISC, MIT and Apache-2.0 are permissive and can be combined with AGPL-3.0 code; each needs its copyright and licence notice kept in the distributed app (an "open-source notices" file or About screen is enough). For Apache-2.0, the FSF considers it compatible with GPLv3, and AGPL-3.0 is in the same family (already recorded for `@xyflow/react` in `DECISIONS.md`). **Remix Icon 4.9 is not usable:** its new licence forbids using icons in a logo, app icon or brand mark and forbids building a "competing icon library". Section 7 of the AGPL does not allow passing extra restrictions on to recipients, so these field-of-use limits cannot travel with an AGPL program. Not legal advice; the release lawyer review (spec 0) should confirm.

**Coverage of the concepts Ithax needs** (Y: a clear match exists; ~: only a loose match; checked by file name in each package):

| Concept | Lucide | Phosphor | Tabler | Material | Heroicons | Iconoir |
| --- | --- | --- | --- | --- | --- | --- |
| Home | Y `house` | Y `house` | Y `home` | Y `home` | Y `home` | Y `home-simple-door` |
| Canvas / flow graph | Y `workflow` | Y `flow-arrow` | Y `schema` | Y `account_tree` | ~ `share` | ~ `network` |
| Data / table | Y `table` | Y `table` | Y `table` | Y `table_chart` | Y `table-cells` | Y `table` |
| Experiment / flask | Y `flask-conical` | Y `flask` | Y `flask` | Y `science` | ~ `beaker` | Y `flask` |
| Play / run | Y `play` | Y `play` | Y `player-play` | Y `play_arrow` | Y `play` | Y `play` |
| Monitor / activity | Y `activity` | Y `pulse` | Y `activity` | Y `monitor_heart` | ~ `signal` | Y `activity` |
| Results / chart | Y `chart-column` | Y `chart-bar` | Y `chart-bar` | Y `bar_chart` | Y `chart-bar` | Y `stats-up-square` |
| Settings | Y `settings` | Y `gear-six` | Y `settings` | Y `settings` | Y `cog-6-tooth` | Y `settings` |
| Source (arrivals) | Y `log-in` | Y `sign-in` | Y `door-enter` | Y `login` | Y `arrow-right-end-on-rectangle` | Y `log-in` |
| Sink (exit) | Y `log-out` | Y `sign-out` | Y `door-exit` | Y `logout` | Y `arrow-left-start-on-rectangle` | Y `log-out` |
| Delay (timer) | Y `timer` | Y `timer` | Y `hourglass` | Y `timer` | Y `clock` | Y `timer` |
| Branch (split) | Y `split` | Y `arrows-split` | Y `arrows-split` | Y `call_split` | ~ `arrows-right-left` | Y `git-fork` |
| Server (worker, machine) | Y `user-cog` | Y `user-gear` | Y `user-cog` | Y `engineering` | ~ `user` | ~ `user` |
| Queue | ~ `rows-3`, `list-ordered` | ~ `rows`, `list-numbers` | ~ `list-numbers` | ~ `format_list_numbered` | ~ `queue-list` | ~ `numbered-list-left` |
| Batch | Y `group` | Y `box-arrow-down` | Y `package-import` | Y `move_to_inbox` | ~ `archive-box` | ~ `package` |
| Unbatch | Y `ungroup` | Y `box-arrow-up` | Y `package-export` | Y `unarchive` | ~ | ~ |
| Store (warehouse) | Y `warehouse` | Y `warehouse` | Y `building-warehouse` | Y `warehouse` | ~ `building-storefront` | ~ `shop` |
| Resource pool | Y `users` | Y `users-three` | Y `users-group` | Y `groups` | Y `user-group` | Y `group` |
| Schedule (calendar) | Y `calendar-clock` | Y `calendar-dots` | Y `calendar-time` | Y `calendar_month` | Y `calendar-days` | Y `calendar` |
| Failure (wrench, alert) | Y `wrench` | Y `wrench` | Y `tool` | Y `build_circle` | Y `wrench-screwdriver` | Y `wrench` |

No library has a true "queue" (a line of waiting items); every one has only list or playlist shapes (Phosphor's `queue` is a music playlist). Heroicons and Iconoir lack several simulation concepts. Lucide, Phosphor, Tabler and Material cover everything else.

**Choosing between the four that fit.**

- **Lucide**: the most active (a release on the day of checking), ISC, one stroke style. It is also the default icon set of the shadcn/ui kit, so it is the look of many current web apps; it adds little character on its own.
- **Phosphor**: six weights from one import. The **duotone** weight (a soft second layer behind the outline) gives friendly, filled-looking icons that can take a category tint, and the **fill** weight can mark the current nav item. It looks rounder and warmer than Lucide or Tabler, which suits the "less ERP" goal. Its React package was last released in May 2025, so it changes slowly; icons are static drawings, so a slow release pace is a small risk.
- **Tabler**: the largest set, MIT, outline plus filled; visually close to Lucide.
- **Material Symbols**: Apache-2.0 and very complete, but no React components, and its look says "Google app".

### Typefaces

A *variable font* holds a whole range of weights (and sometimes widths or optical sizes) in one file. *Tabular figures* are digits that all have the same width, so numbers line up in columns; a font either uses them by default or offers them through the OpenType feature `tnum` (turned on in CSS with `font-variant-numeric: tabular-nums`). *Optical size* (`opsz`) is an axis that adjusts letter shapes for large or small text.

How checked: `npm view @fontsource-variable/<name> version license` (and `@fontsource/<name>` for static families) on 2026-11-06, all at version 5.3.0; `npm pack` of each, a read of its `LICENSE` file (each is the SIL Open Font License 1.1 with the project's copyright line), and an inspection of the latin `.woff2` files with fontTools 4 (axes from the `fvar` table, `tnum` from the `GSUB` feature list, default digit widths from `hmtx`). Sizes are the sum of the latin and latin-extended normal (upright) files, in kilobytes; italics are extra.

| Typeface | Licence (copyright line in `LICENSE`) | Variable axes | Tabular figures | Subsets in the package | Size, upright, latin + latin-ext |
| --- | --- | --- | --- | --- | --- |
| IBM Plex Sans | OFL 1.1 (IBM Corp.) | wght 100–700, wdth 75–100 | Tabular by default | latin, latin-ext, cyrillic, greek, vietnamese | 77 KB (wght only) |
| Manrope | OFL 1.1 (The Manrope Project Authors) | wght 200–800 | `tnum` | latin, latin-ext, cyrillic, greek, vietnamese | 40 KB |
| Plus Jakarta Sans | OFL 1.1 (The Plus Jakarta Sans Project Authors) | wght 200–800 | `tnum` | latin, latin-ext, cyrillic-ext, vietnamese | 49 KB |
| Figtree | OFL 1.1 (The Figtree Project Authors) | wght 300–900 | `tnum` | latin, latin-ext | 30 KB |
| Outfit | OFL 1.1 (The Outfit Project Authors) | wght 100–900 | `tnum` | latin, latin-ext | 47 KB |
| Sora | OFL 1.1 (The Sora Project Authors) | wght 100–800 | `tnum` | latin, latin-ext | 49 KB |
| Bricolage Grotesque | OFL 1.1 (The Bricolage Grotesque Project Authors, Ateliers Triay) | opsz 12–96, wdth 75–100, wght 200–800 | `tnum` | latin, latin-ext, vietnamese | 60 KB (wght only); 185 KB (all three axes) |
| Instrument Sans | OFL 1.1 (The Instrument Sans Project Authors) | wdth 75–100, wght 400–700 | `tnum` | latin, latin-ext | 41 KB (wght only) |
| Atkinson Hyperlegible Next | OFL 1.1 (The Atkinson Hyperlegible Next Project Authors) | wght 200–800 | `tnum` | latin, latin-ext | 53 KB |
| Atkinson Hyperlegible (2020, static) | OFL 1.1 (Braille Institute of America) | none | `tnum` | latin, latin-ext | 27 KB (400 only) |
| Lexend | OFL 1.1 (The Lexend Project Authors) | wght 100–900 | **None** (no `tnum`, proportional digits) | latin, latin-ext, vietnamese | 74 KB |
| Fraunces (serif) | OFL 1.1 (The Fraunces Project Authors) | opsz 9–144, wght 100–900, SOFT 0–100, WONK 0–1 | Not found in the package's subset | latin, latin-ext, vietnamese | 70 KB (wght only); 226 KB (all axes) |
| JetBrains Mono | OFL 1.1 (The JetBrains Mono Project Authors) | wght 100–800 | Monospaced, so always tabular | latin, latin-ext, cyrillic, greek, vietnamese | 56 KB |
| IBM Plex Mono (static) | OFL 1.1 (IBM Corp.) | none | Monospaced | latin, latin-ext, cyrillic, vietnamese | 28 KB (400 only) |

Notes on fit:

- **Atkinson Hyperlegible Next** (Braille Institute, released 2025-02-10) is drawn for low-vision readers: letters that are easy to confuse (I, l, 1; O, 0; b, d) are made distinct. That matters for ids such as `server_1` and `till_l`. The 2025 version adds seven weights with italics and support for over 150 languages (Braille Institute press coverage). A matching Atkinson Hyperlegible Mono also exists.
- **Lexend** was designed from Bonnie Shaver-Troup's reading-fluency research. The evidence is mostly from its designers and not independently replicated, and it has no tabular figures, so numbers in tables would not line up. Not suitable as the interface face.
- **Bricolage Grotesque** has an optical-size axis: at large sizes it becomes tighter and quirkier (ink traps, characterful curves), at small sizes plainer. It is distinctive without being hard to read, and is not the overused Inter or Space Grotesk look.
- **Fraunces** is a lively "wonky" serif; good for a learning brand, but a serif display next to data tables makes two strong voices, and its subset lacks tabular figures.
- **IBM Plex Sans** is excellent and very complete, but corporate in tone, which works against the owner's "not ERP" comment.
- **Figtree, Manrope, Plus Jakarta Sans, Outfit, Sora** are friendly geometric faces; all usable. Figtree is the smallest file.

**Offline.** Bundling the `.woff2` files into the Tauri app and loading them with `@font-face` from the app's own files works with no network. The rule that matters for spec 0 principle 6 is *never download at run time*, not *never use a font file*. The fonts above are under 400 KB together, which is small next to the webview runtime.

**OFL 1.1 obligations.** Fonts may be bundled, embedded and redistributed with any software, including AGPL and commercial software. The font files may not be sold on their own; the licence text and copyright notice must go with them; a modified font may not use the original's reserved font name. The OFL applies to the font files only and does not affect the licence of the program (OFL FAQ). Bundling the unmodified `.woff2` files with their `LICENSE` meets this.

## Sources

Read or run on 2026-11-06.

- npm registry metadata, via `npm view` and `npm pack`, for: `lucide-react`, `lucide-static`, `@phosphor-icons/react`, `@phosphor-icons/core`, `@tabler/icons-react`, `@tabler/icons`, `@material-symbols/svg-400`, `@heroicons/react`, `heroicons`, `iconoir-react`, `iconoir`, `@remixicon/react`, `remixicon`; and `@fontsource-variable/*` and `@fontsource/*` 5.3.0 for each typeface listed. The `LICENSE` files were read from the packed tarballs.
- Remix Icon License v1.0 (January 2026), the `License` file in `remixicon` 4.9.1.
- GNU Affero General Public License v3, section 7 (further restrictions): https://www.gnu.org/licenses/agpl-3.0.html (not re-read; known text).
- SIL Open Font License 1.1 and its FAQ: https://openfontlicense.org (not re-read; the licence text in each package was read).
- Braille Institute, Atkinson Hyperlegible Next launch, February 2025 (press coverage): https://ophthalmologymanagement.com/news/2025/applied-design-and-braille-institute-partner-to-launch-typeface-for-making-reading-easier/ ; Fontsource: https://fontsource.org/fonts/atkinson-hyperlegible-next/about
- Lexend background: https://lexend.com/ and https://github.com/googlefonts/lexend
- Font file inspection: fontTools (installed in a scratch virtual environment, not a project dependency).
- Owner's request and the first design: `docs/design/design-system.md`, `docs/DECISIONS.md` (design choice 11).

## Decision

All of the following are **proposals for the owner**.

**Icons: Phosphor (`@phosphor-icons/react` 2.1.10, MIT).** Reasons: the duotone weight gives the softer, friendlier look the engaging-design note asks for (block icon discs take the category tint in the 20% layer), the fill weight marks the current nav item, everything needed is covered, and MIT is compatible with AGPL-3.0. Use **regular** weight for nav and toolbar, **fill** for the current nav item (also shown by the existing `accent` marker and `aria-current`, so the weight is never the only cue), and **duotone** for block icons. Icons are 24 px in the nav rail and toolbar and 20 px in block discs; every icon keeps a visible word or an accessible name. **Fallback: Lucide** (`lucide-react` 1.70.0, ISC), if the owner prefers its plainer look or Phosphor stops being maintained; its names are in the table below. Rejected: Remix Icon (licence restrictions), Heroicons and Iconoir (missing concepts), Material Symbols (no React package, Google look), Tabler (close to Lucide with more icons than needed).

Proposed mapping (component names as imported from `@phosphor-icons/react`):

| Place | Item | Phosphor | Lucide fallback |
| --- | --- | --- | --- |
| Nav rail | Home | `House` | `House` |
| Nav rail | Canvas | `FlowArrow` | `Workflow` |
| Nav rail | Data | `Table` | `Table` |
| Nav rail | Experiment | `Flask` | `FlaskConical` |
| Nav rail | Run monitor | `Pulse` | `Activity` |
| Nav rail | Results | `ChartBar` | `ChartColumn` |
| Nav rail | Settings | `GearSix` | `Settings` |
| Canvas toolbar | Zoom in | `MagnifyingGlassPlus` | `ZoomIn` |
| Canvas toolbar | Zoom out | `MagnifyingGlassMinus` | `ZoomOut` |
| Canvas toolbar | Fit | `CornersOut` | `Scan` |
| Canvas toolbar | Undo | `ArrowUUpLeft` | `Undo2` |
| Canvas toolbar | Redo | `ArrowUUpRight` | `Redo2` |
| Canvas toolbar | Run | `Play` (fill weight on the primary button) | `Play` |
| Canvas toolbar | Delete | `Trash` | `Trash2` |
| Canvas toolbar | Connect | `PlugsConnected` | `Cable` |
| Canvas toolbar | Find | `MagnifyingGlass` | `Search` |
| Block | `source` | `SignIn` | `LogIn` |
| Block | `sink` | `SignOut` | `LogOut` |
| Block | `delay` | `Timer` | `Timer` |
| Block | `branch` | `ArrowsSplit` | `Split` |
| Block | `server` | `UserGear` | `UserCog` |
| Block | `queue` | `Rows` (check visually; alternative `ListNumbers`) | `Rows3` |
| Block | `batch` | `BoxArrowDown` | `Group` |
| Block | `unbatch` | `BoxArrowUp` | `Ungroup` |
| Block | `store` | `Warehouse` | `Warehouse` |
| Block | `resource_pool` | `UsersThree` | `Users` |
| Block | `schedule` | `CalendarDots` | `CalendarClock` |
| Block | `failure` | `Wrench` | `Wrench` |

`failure` uses a wrench rather than a warning triangle, because the triangle already marks warnings on blocks (`design-system.md` "Block states"). If no stock icon reads well as a queue in the walkthrough, a custom icon (three dots in a line before a bar) can be drawn in Phosphor's 256-unit grid and kept with the app's own assets.

**Typefaces: bundled open fonts, never downloaded at run time.**

| Role | Typeface | Licence | Why |
| --- | --- | --- | --- |
| Display: screen titles, hero numbers on Results, lesson titles, empty-state headings | **Bricolage Grotesque** (variable, opsz + wght; about 185 KB, or 60 KB with weight only) | SIL OFL 1.1 | Characterful at large sizes, plain at small sizes, has tabular figures for big numbers, and avoids the Inter look. Gives the visceral "this was designed" signal. |
| Interface and body: panels, forms, blocks, tables, findings | **Atkinson Hyperlegible Next** (variable, wght 200–800; about 53 KB upright, italics extra) | SIL OFL 1.1 | Built for legibility, distinct I/l/1 and O/0 for component ids, has tabular figures for tables and the run monitor, and a credible accessibility story for students and teachers. |
| Mono: ids, metric names, run ids | **JetBrains Mono** (variable, wght 100–800; about 56 KB) | SIL OFL 1.1 | Clear 0/O and 1/l, tabular by nature, wide script coverage. Alternative: Atkinson Hyperlegible Mono, for a single family voice. |

Alternative pairing if the owner finds Bricolage too quirky: **Figtree** (display and body) with **JetBrains Mono**. The system font stack stays as the fallback in every `font-family` list.

**Change to design choice 11:** "System fonts only, so nothing is downloaded (spec 0 principle 6)" becomes "**Bundled open fonts, never downloaded at run time** (spec 0 principle 6): Bricolage Grotesque, Atkinson Hyperlegible Next and JetBrains Mono, under SIL OFL 1.1, shipped as `.woff2` files with their licence texts; the system stack is the fallback." If the owner agrees, a later session updates `design-system.md` ("Type" and principle 4), adds a DECISIONS entry with the dependencies (`@phosphor-icons/react` 2.1.10 MIT; the three font packages at `@fontsource-variable/*` 5.3.0, OFL 1.1, or the upstream `.woff2` files), and adds the icon and font notices to the app's open-source notices.

## Tested

Partly. Versions, release dates and licences were read from npm and from the `LICENSE` file inside each package. Icon names were checked against the files in each package; the Phosphor names were checked in `@phosphor-icons/core` 2.1.1 (the drawing source; it has the same 1,512 icons as the React package's 1,512 components). Font axes, tabular figures and file sizes were read from the actual `.woff2` files with fontTools. Not tested: how the icons and fonts look at 12 to 24 px on Windows (WebView2) and Linux (WebKitGTK), whether the queue icon reads as a queue to users, and reading comfort; these belong in the owner's walkthrough. No code under `ui/` was written.
