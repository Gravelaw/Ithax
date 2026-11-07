# Spec 3 research: Sanzo Wada colour palette (M9 design review)

## Question

The owner reviewed the first design (AKS-118) and said its colours look like a traditional ERP (enterprise resource planning) system: cool greys and a standard corporate blue. The owner asked that Sanzo Wada's "A Dictionary of Color Combinations" be the colour reference.

This note answers five questions:

1. What is the book, and how are its colours and combinations organised?
2. Where do machine-readable colour values exist, and under what licence?
3. Can the colours and combinations be used freely (copyright), and may our documents name Sanzo Wada?
4. Which Wada colours should fill the existing tokens in `docs/design/tokens.json`, for the light and the dark theme, so that every pair in the contrast table of `docs/design/design-system.md` still passes WCAG 2.2 Level AA?
5. What does the session recommend to the owner?

## Finding

### The book

- Sanzo Wada (1883 to 1967) was a Japanese painter and costume designer. He published "Haishoku Sōkan" (a colour-combination reference) in six volumes in 1933 and 1934.
- Seigensha Art Publishing in Kyoto reprinted a selection as "A Dictionary of Color Combinations" (Volume 1). Sellers give 2010 or 2011 as the reprint year. A Volume 2 (2020) adds later material from 1935 to 1938; it is not used here.
- Volume 1 holds 348 numbered combinations. Each combination is a small group of colours meant to be used together: 120 have 2 colours, 120 have 3 and 108 have 4 (counted from the dataset below).
- The colours themselves are printed as swatches with a name and a CMYK ink recipe (cyan, magenta, yellow, black percentages). The dataset has 159 swatch entries in 6 chapters, roughly by hue: reds and pinks (38), yellows, oranges and browns (49), greens (23), blues (23), violets (20), and white, greys and black (6). Two names appear twice with an A and a B variant ("Eugenia Red", "Grayish Lavender"), so there are 157 distinct names. This explains why sources say "about 157" or "159" colours.
- The same colour is reused across many combinations. For example Black is in 23 combinations, Raw Sienna in 19.

### Machine-readable data

- **mattdesl/dictionary-of-colour-combinations** (GitHub, Matt DesLauriers). File `colors.json`, version 1.0.2 (npm release 2020-05-27), branch `master` at commit `c142bd0`. It is a list of 159 colours. Each entry has a `name`, the `combinations` it belongs to (numbers 1 to 348), its `swatch` chapter (0 to 5), `cmyk`, `lab`, `rgb` and `hex`. The README says the data "maintains" the author's order.
- **Licence read:** `LICENSE.md` is "The MIT License (MIT) Copyright (c) 2020 Matt DesLauriers" with the standard MIT text. `package.json` says `"license": "MIT"`.
- **Origin:** the README says the data "has originally been compiled and open sourced by Dain M. Blodorn Kim (@dblodorn)" for an interactive website (`dblodorn/sanzo-wada`). That repository's `LICENSE` is "MIT License Copyright (c) 2024 Dain Blodorn". The fork fixed "some incorrect data from the original".
- **How the hex values were made:** the CMYK ink values from the book were converted to screen colours with the colour profiles "U.S. Web Coated (SWOP) v2" (CMYK) and "sRGB IEC61966-2.1" (RGB), "Relative Colorimetric and Black Point Compensation". The README warns: "There may still be some differences to the book's printed swatches, as the conversion is not exact." So every hex value here is an **approximation of a printed ink**, not an exact match to the paper swatch. The CMYK values themselves were typed from the book by hand.
- **Other open data:** `dblodorn/sanzo-wada` (MIT) is the upstream source with an older, less faithful RGB conversion. Several websites show the palettes, but none found offers a separately licensed dataset. The mattdesl file is the best one to cite.
- **Colour numbers in this note:** "Wada #N" means the 1-based position in `colors.json`. The README says the order follows the book, but the session did not check these positions against the printed swatch numbers. Combination numbers (1 to 348) come straight from the data and are the book's numbers.

### Copyright and naming

This is not legal advice. A lawyer confirms before the first public release (spec 0).

- **Term in Japan.** Wada died in 1967. Japan's term was then the author's life plus 50 years, ending on 31 December of the 50th year. So his works entered the public domain in Japan at the end of 31 December 2017. Japan moved to life plus 70 years on 30 December 2018 (the TPP-11 amendment). The change was not retroactive: works already in the public domain stayed there. Wikimedia Commons' "PD-Japan" guidance draws the line at authors who died in 1967 or before, which agrees.
- **Other countries.** Some countries count terms differently, and the original 1933 to 1934 publication date matters in the United States. This does not change the result below, because the parts we use are probably not protectable at all.
- **Are colours and combinations protectable?** A single colour value is a fact (a measurement of an ink), not an expression. United States rules say "mere variations of ... coloring" are not subject to copyright (37 CFR 202.1(a)). A combination of two to four colours is a very short selection. It is unlikely to meet the originality threshold on its own. The book as a whole (its selection and layout of 348 combinations) could be a compilation work, but we take only a handful of colours, not the book's structure.
- **What is still protected:** the Seigensha reprint's own text, translation, page design and photographs belong to the publisher. We copy none of them. We use colour values from the MIT dataset.
- **Licence duty.** If the product ships `colors.json` or a large part of it, the MIT notice must ship too. Copying around twenty hex values into `tokens.json` is a small use of facts; adding the attribution line below costs nothing and is still recommended.
- **Using the name.** Naming "Sanzo Wada" and the book in our documents, as the source of the palette, is ordinary attribution and is fine. The name must not be used as branding: no product, theme or feature named "Wada" or "Sanzo", and no claim of endorsement by the Wada estate or Seigensha. The theme names stay "Light" and "Dark".

Suggested attribution line for `design-system.md` and the about screen's credits: "Colours drawn from Sanzo Wada, Haishoku Sōkan (1933 to 1934), via the dictionary-of-colour-combinations dataset by Matt DesLauriers and Dain M. Blodorn Kim (MIT)."

### The proposed palette

**How it was chosen.** The colours that carry meaning come from two Wada combinations that share none of their colours but suit each other:

- **Combination 247:** Raw Sienna, Apricot Yellow, Benzol Green, Deep Lyons Blue. This gives the accent (Deep Lyons Blue), the flow category (Benzol Green) and the resource category (Raw Sienna).
- **Combination 335:** Vandyke Red, Yellow Orange, Violet, Slate Color. This gives error (Vandyke Red), warning (Yellow Orange), the work category (Violet) and the text ink (Slate Color).

Two smaller combinations fill the last gaps, and each one includes the accent:

- **Combination 38:** Diamine Green and Deep Lyons Blue. This gives success.
- **Combination 344:** Cinnamon Buff, Deep Lyons Blue, Aconite Violet, Black. This gives the Learn colour. Aconite Violet is also with Raw Sienna in combination 269.

The light theme sits on warm paper made from Wada's Ivory Buff, with Slate Color ink. The look moves from cool grey and corporate blue to warm paper and dark ink. The dark theme reverses this: dark slate made from Wada's Slate Color and Black, with Sulpher Yellow (a cream paper tone) as the text. In the dark theme, each colour that carries meaning is replaced by a lighter Wada colour of the same hue family, so the two themes read as one palette.

**"Derived"** below means the colour is not printed in the book. It is either a mix of a Wada colour with white, black or another Wada colour (stated as a percentage, simple sRGB mixing), or the same Wada hue and saturation with only the lightness changed until it passes contrast (HLS lightness, 0.005 steps).

#### Light theme

| Token | Hex | Wada source | Combinations |
| --- | --- | --- | --- |
| `canvas` | `#F9F3E5` | Derived: 28% Ivory Buff (Wada #42, `#EBD3A2`) with white | Ivory Buff: 11, 50, 94, 102 and others |
| `surface` | `#FDFAF4` | Derived: 12% Ivory Buff with white | |
| `surface-alt` | `#F7EEDC` | Derived: 38% Ivory Buff with white | |
| `border` (decorative) | `#CABD9E` | Derived: 55% Ivory Buff with 45% Warm Gray (Wada #157, `#A1A39A`) | |
| `canvas-grid` (decorative) | `#BBB49D` | Derived: 35% Ivory Buff with 65% Warm Gray | |
| `text` | `#34454C` | Slate Color (Wada #158), as printed | 335 |
| `text-muted` | `#547076` | Dark Medici Blue (Wada #125), as printed | 160, 224, 241, 249 |
| `border-strong` | `#6D7E77` | Andover Green (Wada #96), as printed | 244, 346 |
| `edge` | `#547076` | Dark Medici Blue (Wada #125), as printed | |
| `accent`, `focus` | `#1C4286` | Deep Lyons Blue (Wada #127), as printed | 247, 344, 38 |
| `on-accent` | `#FDFAF4` | Same as `surface` | |
| `error` | `#82241F` | Vandyke Red (Wada #34), as printed | 335 |
| `error-bg` | `#F1E5DF` | Derived: 10% Vandyke Red with `surface` | |
| `warning` | `#915604` | Derived from Yellow Orange (Wada #62, `#F99D1B`): same hue (35°), darker so it passes as text | 335 |
| `warning-bg` | `#FCEBD1` | Derived: 16% Yellow Orange with `surface` | |
| `success` | `#1A7444` | Diamine Green (Wada #106), as printed | 38 |
| `success-bg` | `#E9EEE4` | Derived: 9% Diamine Green with `surface` | |
| `learn` | `#8F5891` | Derived from Aconite Violet (Wada #140, `#A36AA5`): same hue (298°), darker so it passes as text | 344, 269 |
| `cat-flow` | `#00978D` | Benzol Green (Wada #101), as printed | 247 |
| `cat-work` | `#4F4086` | Violet (Wada #150), as printed | 335 |
| `cat-resource` | `#BB7125` | Raw Sienna (Wada #14), as printed | 247, 269 |

#### Dark theme

| Token | Hex | Wada source | Combinations |
| --- | --- | --- | --- |
| `canvas` | `#161A1C` | Derived: 15% Slate Color (Wada #158) with 85% Black (Wada #159, `#111314`) | Slate Color 335; Black 344, 269 |
| `surface` | `#1F272A` | Derived: 40% Slate Color with Black | |
| `surface-alt` | `#263136` | Derived: 60% Slate Color with Black | |
| `border` (decorative) | `#3D4E52` | Derived: 85% Slate Color with 15% Andover Green (Wada #96) | |
| `canvas-grid` (decorative) | `#4E5F5F` | Derived: 55% Slate Color with 45% Andover Green | |
| `text` | `#F5ECC2` | Sulpher Yellow (Wada #39), as printed: a cream paper tone | 52, 72, 80 and 15 others |
| `text-muted` | `#B6BFC1` | Neutral Gray (Wada #155), as printed | 34, 139, 180 and others |
| `border-strong` | `#818E8C` | Derived: 75% Mineral Gray (Wada #156, `#A2B0AD`) with `surface` | |
| `edge` | `#A2B0AD` | Mineral Gray (Wada #156), as printed | 11, 30 |
| `accent`, `focus` | `#97ACC8` | Salvia Blue (Wada #114), as printed. Same hue family as Deep Lyons Blue (214° against 218°) | 129, 135, 188, 294 |
| `on-accent` | `#161A1C` | Same as `canvas` | |
| `error` | `#F58E84` | Coral Red (Wada #6), as printed | 92 (with Benzol Green) |
| `error-bg` | `#3D2627` | Derived: 30% Vandyke Red (Wada #34) with `surface` | |
| `warning` | `#FCB315` | Orange Yellow (Wada #61), as printed | 257, 338 |
| `warning-bg` | `#3E3828` | Derived: 14% Yellow Orange (Wada #62) with `surface` | |
| `success` | `#96D1AA` | Cobalt Green (Wada #115), as printed | 281 (with Benzol Green), 188 (with Salvia Blue) |
| `success-bg` | `#1E3E32` | Derived: 30% Diamine Green (Wada #106) with `surface` | |
| `learn` | `#B984AF` | Lilac (Wada #137), as printed | 143, 162, 282, 347 |
| `cat-flow` | `#62C6BF` | Venice Green (Wada #117), as printed. Same hue as Benzol Green (176°) | 78, 128, 189 |
| `cat-work` | `#B5B1D8` | Grayish Lavender - A (Wada #134), as printed. Near Violet's hue (246° against 253°) | 15 (with Benzol Green) |
| `cat-resource` | `#EEB480` | Pinkish Cinnamon (Wada #45), as printed. Near Raw Sienna's hue (28° against 30°) | 161, 175, 258 |

#### Chart series

Today `design-system.md` draws charts in `accent`, `cat-flow`, `cat-work`, `cat-resource`. With Wada colours, light `accent` (Deep Lyons Blue) and `cat-work` (Violet) are both dark blue-violets of almost the same lightness (ratio 1.10:1 between them). They would be hard to tell apart as lines. The proposal is four chart colours in their own order, all from combinations 247, 344 and 269. Each scenario keeps its own marker shape and a direct label, as the design system already requires.

| Series | Light | Contrast on surface / canvas | Dark | Contrast on surface / canvas |
| --- | --- | --- | --- | --- |
| 1 | Deep Lyons Blue `#1C4286` (#127) | 9.27 / 8.73 | Salvia Blue `#97ACC8` (#114) | 6.54 / 7.55 |
| 2 | Raw Sienna `#BB7125` (#14) | 3.66 / 3.44 | Pinkish Cinnamon `#EEB480` (#45) | 8.30 / 9.57 |
| 3 | Benzol Green `#00978D` (#101) | 3.46 / 3.26 | Venice Green `#62C6BF` (#117) | 7.48 / 8.63 |
| 4 | Aconite Violet `#A36AA5` (#140), as printed | 3.90 / 3.67 | Lilac `#B984AF` (#137) | 5.05 / 5.82 |

A fifth and sixth series were left out on purpose. The remaining Wada hues are red (it would read as an error), yellow (fails 3:1 on the light paper) or near-greys. After four series the colours repeat, and the shape and label tell the series apart, as now.

### Contrast results

Every pair listed in the `pairs` array of `tokens.json` (the same rows as the contrast table in `design-system.md`), computed with the WCAG 2.2 formulas from `scripts/contrast.py`. Ratios are cut to two decimals, never rounded up. Text needs 4.5:1 (success criterion 1.4.3). Non-text needs 3:1 (success criterion 1.4.11).

| Theme | Foreground | Background | Used for | Ratio | Needed | Result |
| --- | --- | --- | --- | --- | --- | --- |
| light | `text` | `surface` | Body text on panels and blocks | 9.59:1 | 4.5:1 | pass |
| light | `text` | `surface-alt` | Text on the nav rail, table headers, hovered rows | 8.66:1 | 4.5:1 | pass |
| light | `text` | `canvas` | Text placed on the canvas | 9.03:1 | 4.5:1 | pass |
| light | `text-muted` | `surface` | Secondary text | 5.09:1 | 4.5:1 | pass |
| light | `text-muted` | `surface-alt` | Secondary text on the nav rail and table headers | 4.60:1 | 4.5:1 | pass |
| light | `text-muted` | `canvas` | Secondary text on the canvas | 4.79:1 | 4.5:1 | pass |
| light | `accent` | `surface` | Links and accent text | 9.27:1 | 4.5:1 | pass |
| light | `on-accent` | `accent` | Text on primary buttons | 9.27:1 | 4.5:1 | pass |
| light | `error` | `surface` | Error text | 9.07:1 | 4.5:1 | pass |
| light | `error` | `error-bg` | Error text in the problems list and banners | 7.65:1 | 4.5:1 | pass |
| light | `warning` | `surface` | Warning text | 5.69:1 | 4.5:1 | pass |
| light | `warning` | `warning-bg` | Warning text in the problems list and banners | 5.07:1 | 4.5:1 | pass |
| light | `success` | `surface` | Run done, saved state | 5.55:1 | 4.5:1 | pass |
| light | `success` | `success-bg` | Success banner text | 4.91:1 | 4.5:1 | pass |
| light | `learn` | `surface` | Learn-mode step label | 5.07:1 | 4.5:1 | pass |
| light | `border-strong` | `surface` | Input, checkbox and block outlines | 4.11:1 | 3.0:1 | pass |
| light | `border-strong` | `canvas` | Block outline against the canvas | 3.87:1 | 3.0:1 | pass |
| light | `focus` | `surface` | Focus ring on panels | 9.27:1 | 3.0:1 | pass |
| light | `focus` | `canvas` | Focus ring and selection outline on the canvas | 8.73:1 | 3.0:1 | pass |
| light | `edge` | `canvas` | Connection lines and ports | 4.79:1 | 3.0:1 | pass |
| light | `edge` | `surface` | Port circles on a block | 5.09:1 | 3.0:1 | pass |
| light | `error` | `canvas` | Error marker on the canvas | 8.54:1 | 3.0:1 | pass |
| light | `warning` | `canvas` | Warning marker on the canvas | 5.36:1 | 3.0:1 | pass |
| light | `learn` | `canvas` | Learn-mode highlight ring | 4.77:1 | 3.0:1 | pass |
| light | `cat-flow` | `surface` | Category stripe and icon: flow blocks | 3.46:1 | 3.0:1 | pass |
| light | `cat-work` | `surface` | Category stripe and icon: work blocks | 8.36:1 | 3.0:1 | pass |
| light | `cat-resource` | `surface` | Category stripe and icon: resource blocks | 3.66:1 | 3.0:1 | pass |
| light | `accent` | `surface` | Selected nav item marker, toggle on | 9.27:1 | 3.0:1 | pass |
| dark | `text` | `surface` | Body text on panels and blocks | 12.77:1 | 4.5:1 | pass |
| dark | `text` | `surface-alt` | Text on the nav rail, table headers, hovered rows | 11.21:1 | 4.5:1 | pass |
| dark | `text` | `canvas` | Text placed on the canvas | 14.73:1 | 4.5:1 | pass |
| dark | `text-muted` | `surface` | Secondary text | 8.11:1 | 4.5:1 | pass |
| dark | `text-muted` | `surface-alt` | Secondary text on the nav rail and table headers | 7.11:1 | 4.5:1 | pass |
| dark | `text-muted` | `canvas` | Secondary text on the canvas | 9.35:1 | 4.5:1 | pass |
| dark | `accent` | `surface` | Links and accent text | 6.54:1 | 4.5:1 | pass |
| dark | `on-accent` | `accent` | Text on primary buttons | 7.55:1 | 4.5:1 | pass |
| dark | `error` | `surface` | Error text | 6.57:1 | 4.5:1 | pass |
| dark | `error` | `error-bg` | Error text in the problems list and banners | 6.03:1 | 4.5:1 | pass |
| dark | `warning` | `surface` | Warning text | 8.39:1 | 4.5:1 | pass |
| dark | `warning` | `warning-bg` | Warning text in the problems list and banners | 6.43:1 | 4.5:1 | pass |
| dark | `success` | `surface` | Run done, saved state | 8.68:1 | 4.5:1 | pass |
| dark | `success` | `success-bg` | Success banner text | 6.70:1 | 4.5:1 | pass |
| dark | `learn` | `surface` | Learn-mode step label | 5.05:1 | 4.5:1 | pass |
| dark | `border-strong` | `surface` | Input, checkbox and block outlines | 4.47:1 | 3.0:1 | pass |
| dark | `border-strong` | `canvas` | Block outline against the canvas | 5.15:1 | 3.0:1 | pass |
| dark | `focus` | `surface` | Focus ring on panels | 6.54:1 | 3.0:1 | pass |
| dark | `focus` | `canvas` | Focus ring and selection outline on the canvas | 7.55:1 | 3.0:1 | pass |
| dark | `edge` | `canvas` | Connection lines and ports | 7.80:1 | 3.0:1 | pass |
| dark | `edge` | `surface` | Port circles on a block | 6.76:1 | 3.0:1 | pass |
| dark | `error` | `canvas` | Error marker on the canvas | 7.57:1 | 3.0:1 | pass |
| dark | `warning` | `canvas` | Warning marker on the canvas | 9.67:1 | 3.0:1 | pass |
| dark | `learn` | `canvas` | Learn-mode highlight ring | 5.82:1 | 3.0:1 | pass |
| dark | `cat-flow` | `surface` | Category stripe and icon: flow blocks | 7.48:1 | 3.0:1 | pass |
| dark | `cat-work` | `surface` | Category stripe and icon: work blocks | 7.41:1 | 3.0:1 | pass |
| dark | `cat-resource` | `surface` | Category stripe and icon: resource blocks | 8.30:1 | 3.0:1 | pass |
| dark | `accent` | `surface` | Selected nav item marker, toggle on | 6.54:1 | 3.0:1 | pass |

Lowest ratios:

- Light text: 4.60:1, `text-muted` (Dark Medici Blue) on `surface-alt`. It passes, but with little room. If `surface-alt` is made any darker, `text-muted` must be darkened too.
- Light non-text: 3.46:1, `cat-flow` (Benzol Green) on `surface`.
- Dark text: 5.05:1, `learn` (Lilac) on `surface`.
- Dark non-text: 4.47:1, `border-strong` on `surface`.

The block badges ("!" drawn in `surface` on a `warning` or `error` fill) reuse the `warning`/`error` on `surface` pairs: light 5.69:1 and 9.07:1, dark 8.39:1 and 6.57:1.

### Do the status colours still read as red, amber and green?

- Error is a red in both themes: Vandyke Red (hue 3°) and Coral Red (hue 5°).
- Warning is an amber: hue 35° in light (a dark ochre, close to the current `#8A5300`) and Orange Yellow at hue 41° in dark.
- Success is a green: Diamine Green (hue 148°) and Cobalt Green (hue 140°).
- As now, colour is never the only cue. Errors have a round "!" badge and warnings a triangle, plus words (design-system.md principle 2).

### Known weaknesses

- Warning (ochre) and `cat-resource` (Raw Sienna, Pinkish Cinnamon) are both in the orange-brown family. The current palette has the same closeness (`#8A5300` against `#8C5413`). The badge shape, the category icon and the type word tell them apart.
- In the dark theme, chart series 1 (Salvia Blue) and series 4 (Lilac) come close under simulated deuteranopia, a red-green colour-vision deficiency (CIE76 colour difference ΔE 8.1). Marker shapes and direct labels carry them, as the design system already requires.
- The hex values are screen approximations of 1930s printed inks (see "Machine-readable data"). The owner may want to compare them with the physical book and adjust a few.

## Sources

- mattdesl, "dictionary-of-colour-combinations", GitHub, branch `master` at commit `c142bd0bc8049ea48db4da5eb397981f047e8ef4`: `README.md`, `LICENSE.md` (MIT, Copyright (c) 2020 Matt DesLauriers), `package.json` (version 1.0.2), `colors.json` (SHA-256 `555f11c32eb8133078fd470dd7d5320533aaa8b636f12fa06a8dd3d0ee2703b4`), read 2026-11-06. https://github.com/mattdesl/dictionary-of-colour-combinations
- npm registry entry "dictionary-of-colour-combinations": latest 1.0.2, published 2020-05-27, licence MIT. https://registry.npmjs.org/dictionary-of-colour-combinations
- dblodorn, "sanzo-wada", GitHub, `LICENSE` (MIT, Copyright (c) 2024 Dain Blodorn) and `README.md`, read 2026-11-06. https://github.com/dblodorn/sanzo-wada
- Wikipedia, "Sanzo Wada" (1883 to 1967; Haishoku Sōkan 1933 to 1934). https://en.wikipedia.org/wiki/Sanzo_Wada
- Seller listings for the Seigensha edition (348 combinations; reprint dated 2010 or 2011 depending on the seller), for example https://www.foyles.co.uk/book/9784861522475 and https://londonbookarts.org/products/e9-85-8d-e8-89-b2-e8-be-9e-e5-85-b8-a-dictionary-of-color-combinations-by-sanzo-wada
- Wikipedia, "Copyright law of Japan" (term extended to life plus 70 years on 30 December 2018; not retroactive). https://en.wikipedia.org/wiki/Copyright_law_of_Japan
- Wikimedia Commons, "Template:PD-Japan" and "Copyright rules by territory/Japan" (authors who died in 1967 or earlier). https://commons.wikimedia.org/wiki/Template:PD-Japan
- Tokyo National Research Institute for Cultural Properties, "Extension of the Term of Protection for Copyright Works". https://www.tobunken.go.jp/materials/nenshi-en/2388106.html
- United States Code of Federal Regulations, 37 CFR 202.1(a): "mere variations of typographic ornamentation, lettering or coloring" are not subject to copyright. https://www.ecfr.gov/current/title-37/chapter-II/subchapter-A/part-202/section-202.1
- W3C, WCAG 2.2, relative luminance and contrast ratio definitions; success criteria 1.4.3 and 1.4.11. https://www.w3.org/TR/WCAG22/
- Machado, Oliveira and Fernandes (2009), "A Physiologically-based Model for Simulation of Color Vision Deficiency", IEEE TVCG 15(6): severity 1.0 matrices, used for the colour-vision check.

## Decision

Proposed, for the owner to confirm (an owner item, not a session gate). Until the owner confirms, `tokens.json` and `design-system.md` are unchanged.

1. **Reference:** use Sanzo Wada's combinations 247 (Raw Sienna, Apricot Yellow, Benzol Green, Deep Lyons Blue) and 335 (Vandyke Red, Yellow Orange, Violet, Slate Color) as the palette's core, with 38 and 344 for success and Learn. Take the values from the MIT-licensed mattdesl `colors.json` 1.0.2.
2. **Light theme:** warm Ivory Buff paper (`canvas #F9F3E5`, `surface #FDFAF4`, `surface-alt #F7EEDC`), Slate Color ink (`text #34454C`, `text-muted #547076`), `accent #1C4286` Deep Lyons Blue, `cat-flow #00978D` Benzol Green, `cat-work #4F4086` Violet, `cat-resource #BB7125` Raw Sienna, `error #82241F` Vandyke Red, `warning #915604` (derived from Yellow Orange), `success #1A7444` Diamine Green, `learn #8F5891` (derived from Aconite Violet). The full list is in the tables above.
3. **Dark theme:** Slate-and-Black ground (`canvas #161A1C`, `surface #1F272A`, `surface-alt #263136`), Sulpher Yellow text `#F5ECC2`, `accent #97ACC8` Salvia Blue, `cat-flow #62C6BF` Venice Green, `cat-work #B5B1D8` Grayish Lavender - A, `cat-resource #EEB480` Pinkish Cinnamon, `error #F58E84` Coral Red, `warning #FCB315` Orange Yellow, `success #96D1AA` Cobalt Green, `learn #B984AF` Lilac.
4. **Charts:** a separate four-colour series order (Deep Lyons Blue, Raw Sienna, Benzol Green, Aconite Violet; dark: Salvia Blue, Pinkish Cinnamon, Venice Green, Lilac), with marker shapes and labels as now. This replaces "accent, cat-flow, cat-work, cat-resource" in `design-system.md`.
5. **Attribution, not branding:** credit Wada and the dataset with the line given under "Copyright and naming". No theme or feature is named after Wada.
6. **If the owner confirms:** a later change updates `tokens.json`, adds chart tokens if wanted, regenerates the contrast table with `python scripts/contrast.py`, adds the attribution line and a dated "Changes" line to `design-system.md`, and logs a DECISIONS entry. No new dependency is added: the values are copied, not the dataset.

## Tested

- Downloaded `README.md`, `LICENSE.md`, `package.json` and `colors.json` from the mattdesl repository, and `LICENSE` and `README.md` from `dblodorn/sanzo-wada`, into an empty scratch folder, treated as data only (Python run with `-I`). Confirmed the commit with `git ls-remote`, and the npm version and licence from the npm registry.
- Counted from `colors.json`: 159 entries; 348 combinations (120 of 2 colours, 120 of 3, 108 of 4); 6 chapters of 38, 49, 23, 23, 20 and 6 entries. Listed each combination's members to find combinations 247, 335, 38, 344, 269 and the dark-theme cross-links (92, 15, 281, 188).
- Derived colours: computed the mixes in sRGB, and the lightness-only variants in HLS (keeping hue and saturation), stepping until the target ratio was met (warning 5.0:1 on `warning-bg`, learn 5.0:1 on `surface`). Checked the hues: Yellow Orange 35.1° gives warning 34.9°, and Aconite Violet 298.0° gives learn 297.9°.
- Contrast: imported `ratio` and `shown` from `scripts/contrast.py` and computed every pair in `tokens.json` `pairs` for both proposed themes (56 rows, all pass), plus each chart colour on `surface` and `canvas`.
- Colour-vision check: CIE76 colour differences between chart colours and between category colours, for normal vision and simulated protanopia, deuteranopia and tritanopia (Machado 2009 matrices in linear RGB). The smallest is 8.1, for dark chart series 1 against 4 under deuteranopia. Category colours stay at 10.8 or more.
- Not tested: how the palette looks on screen next to the printed book. No interface exists yet (M9 has not started), and nothing was shown to users.
