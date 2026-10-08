---
name: Kalorien-Tagebuch
description: A warm, plain calorie and protein ledger for eating enough — cream paper, monospace numerals, one narrow column.
colors:
  bg: "#FAF8F3"
  surface: "#FFFFFF"
  border: "#E4DFD3"
  border-strong: "#BBB198"
  text-primary: "#2B2A26"
  text-secondary: "#6B6656"
  text-muted: "#787263"
  accent: "#4A7A64"
  accent-dark: "#2E5643"
  accent-bg: "#E7F0EA"
  danger: "#B5473C"
  danger-bg: "#FBEBE9"
  warn: "#976927"
  warn-bg: "#F7EFE0"
  on-accent: "#FFFFFF"
typography:
  display:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    fontSize: "22px"
    fontWeight: 600
    letterSpacing: "-0.01em"
  title:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    fontSize: "14px"
    fontWeight: 600
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    fontSize: "14.5px"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    fontSize: "12.5px"
    fontWeight: 400
  metric:
    fontFamily: "'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace"
    fontSize: "24px"
    fontWeight: 600
  code:
    fontFamily: "'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace"
    fontSize: "20px"
    fontWeight: 400
    letterSpacing: "0.28em"
  micro:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    fontSize: "11.5px"
    fontWeight: 400
rounded:
  hairline: "1px"
  bar: "3px"
  bar-top: "5px"
  sm: "8px"
  md: "12px"
  lg: "14px"
  pill: "15px"
spacing:
  xs: "4px"
  sm: "6px"
  md: "8px"
  lg: "12px"
  xl: "16px"
  section: "1.75rem"
  block: "2rem"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.on-accent}"
    rounded: "{rounded.md}"
    padding: "0 18px"
    height: "44px"
  button-primary-hover:
    backgroundColor: "{colors.accent-dark}"
    textColor: "{colors.on-accent}"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.text-secondary}"
    rounded: "{rounded.md}"
    padding: "0 18px"
    height: "44px"
  button-ghost-active:
    backgroundColor: "{colors.accent-bg}"
    textColor: "{colors.accent-dark}"
  button-icon:
    backgroundColor: "transparent"
    textColor: "{colors.text-muted}"
    rounded: "{rounded.sm}"
    height: "32px"
    width: "32px"
  button-small:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.on-accent}"
    rounded: "{rounded.md}"
    padding: "0 12px"
    height: "32px"
  chip:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-secondary}"
    rounded: "{rounded.pill}"
    padding: "0 11px"
    height: "30px"
  chip-hover:
    backgroundColor: "{colors.accent-bg}"
    textColor: "{colors.accent-dark}"
  input-text:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.md}"
    padding: "0 14px"
    height: "44px"
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.lg}"
    padding: "14px 16px"
---

# Design System: Kalorien-Tagebuch

## Overview

**Creative North Star: "The Warm Ledger"**

The atmosphere is plain, honest, and unhurried. Nothing is dressed up.

This is bookkeeping of a body without the coldness that usually comes with it.
Surfaces are warm — a cream paper ground (#FAF8F3), a dark mode tinted brown rather
than black. Numbers are monospaced and exact. Sans reads, mono counts.

On a phone the interface is one 560px column with no navigation and no second place to
look. It is used one-handed, seconds after eating. On a desktop the same groups spread
across the width instead of leaving it empty. Estimates read as estimates and
stay correctable. The page does not rush, congratulate, or celebrate.

Components should feel warm and tactile: 44px targets, softly rounded surfaces. This
runs slightly ahead of current code, which is more restrained than tactile — push
radii, surface warmth, and micro-interaction further. The one bound is firm: no
consumer-app maximalism.

**Key Characteristics:**

- Cream-paper ground with white surfaces; a warm-brown dark mode, never pure black (only the opt-in OLED scheme uses a #000000 ground).
- One accent — a desaturated garden green — carrying every affirmative signal.
- Monospace for every comparable number; system sans for all prose.
- A single 560px column on phones and tablets, the same groups in two or three columns
  on a desktop; no navigation, and settings replace the page as a view of their own.
- Hairline 1px borders and tonal layering; no shadows, because nothing floats.
- Motion as response, not animation: one authored moment, everything else under 200ms.

## Colors

A warm, low-saturation palette built from a single green accent against cream and
brown-tinted neutrals; the only other hues are a muted brick for destructive actions
and an amber for caution.

### Primary

- **Quiet Garden Green** (`#4A7A64` light, `#66A385` dark): Desaturated and domestic,
  a grown thing rather than a brand color — deliberately not a vivid app-accent green.
  It fills primary buttons, fills history bars for days that met the goal, draws the
  goal-progress fill, and draws focus rings and the selected chart bar's ring. It is the system's only affirmative
  voice.
- **Deep Garden Green** (`#2E5643` light, `#8AC2A4` dark): The stronger sibling. Used
  for primary-button hover, link text, and "good" notes.
- **Garden Wash** (`#E7F0EA` light, `#23332B` dark): The faint accent field behind
  hovered chips and icon buttons, and active range toggles.

### Secondary

- **Muted Amber** (`#976927` light, `#D2A25C` dark): Caution, not alarm. Marks a goal
  bar pushed past target, history bars over the ceiling in losing mode, and "warn"
  notes. Paired with **Amber Wash** (`#F7EFE0` / `#332A1B`).

### Tertiary

- **Soft Brick** (`#B5473C` light, `#E08B7F` dark): Destructive and error only —
  delete-entry hover, error messages. Paired with **Brick Wash**
  (`#FBEBE9` / `#38211E`). Never decorative.

### Neutral

- **Warm Paper** (`#FAF8F3` light, `#191817` dark): The page ground. Also copied into
  the browser theme-color bar so the OS chrome matches the page.
- **Card White** (`#FFFFFF` light, `#222120` dark): Every raised surface — cards,
  inputs, chips, the coach panel, day detail.
- **Hairline** (`#E4DFD3` light, `#302E2A` dark): Card borders, row dividers, and the
  empty track of the goal bar.
- **Hairline Strong** (`#BBB198` light, `#4D4A43` dark): Input and chip strokes, the
  dashed goal line, and unreached chart bars — the darkest neutral that is still
  structure rather than text.
- **Ink** (`#2B2A26` light, `#EDEAE2` dark): Primary text and all numerals.
- **Ink Secondary** (`#6B6656` light, `#ABA598` dark): Supporting prose, card labels,
  chart totals.
- **Ink Muted** (`#787263` light, `#918B7C` dark): Timestamps, hints, footnotes, the
  disclaimer, and icon-button glyphs at rest.

### Named Rules

**The Quiet Accent Rule.** Green marks exactly three things: the primary action, a
day that met its goal, and focus. It is never used to decorate a surface, tint a
heading, or distinguish one card from another. Its scarcity is what makes a met day
legible at a glance in a 30-bar chart. What counts as met depends on the account's
goal direction — reaching the target when gaining, staying under it when losing —
but green never means two things at once within one account.

**The Warm Dark Rule.** Dark mode is warm-tinted (`#191817`, not `#000000` and not a
neutral gray). The stated reason is in the stylesheet itself: a cool dark makes the
cream original read as a different app. Any new dark value must keep the same brown
cast.
The single exception is the opt-in **OLED** scheme (`data-oled` on top of
`data-theme="dark"`): its page ground is `#000000` so OLED pixels switch off. It is
only ever an explicit choice in settings, never what "Automatisch" resolves to, and
its raised surfaces (`#11100F`) and hairlines still carry the brown cast.

**The Readable Muted Rule.** `--text-muted` is a text color, not a decoration: it
carries timestamps, hints, placeholders, and the disclaimer. It must clear 4.5:1
against both `--bg` and `--surface` in whichever theme it lives in. The light value was
darkened from `#9A9484` (2.9:1) to `#787263` (4.5:1) for exactly this reason; a future
"softer" muted that fails the ratio is a regression, not a refinement.

**The Role-Not-Shade Rule.** `accent-dark` means "stronger than `accent`", not
"darker". In light mode it is darker (`#2E5643`); in dark mode it is *lighter*
(`#8AC2A4`). It serves as both hover surface and text color, and both need more
contrast against their own ground — so never resolve this token by literal darkness.

## Typography

**Body Font:** system sans (`-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
sans-serif`)
**Numeral / Code Font:** system mono (`'SFMono-Regular', Consolas, 'Liberation Mono',
Menlo, monospace`)

**Character:** No webfonts at all — the type is whatever the device already renders
best, which keeps the app instant on a phone and native to its OS. The expressive
decision is not the family but the split: sans reads, mono counts. Sizes sit on a
deliberately fine-grained scale with half-pixel steps (14.5px, 13.5px, 11.5px), tuned
by eye for a narrow column rather than snapped to a ratio.

### Hierarchy

- **Display** (600, 22px, letter-spacing −0.01em): The app title only, once per page.
- **Metric** (600, 24px, mono): The two headline numbers — today's total and the
  rolling average. The largest type in the app is a number, which is the point.
- **Title** (600, 14px): Section headings ("Heutige Einträge", "Gewicht") and the
  coach headline at 14.5px.
- **Body** (400, 14.5px, line-height 1.55): Entry descriptions. Supporting prose and
  coach messages run at 13.5px in Ink Secondary.
- **Label** (400, 12.5px): Card labels and settings field labels. Drops to 11.5px for
  inline field labels in the edit row.
- **Code** (400, 20px, mono, letter-spacing 0.28em): The six-digit login code, spaced
  wide and centered so digits are countable.
- **Micro** (400, 10–11.5px): Chart totals and day labels, chip kcal suffixes,
  timestamps, the goal-line value, footnotes.

### Named Rules

**The Mono Numeral Rule.** Every number the user might compare across days is
monospace: card values, entry kcal and protein, chart totals, day-detail totals, chip
kcal suffixes, the goal-line label, and numeric inputs. Prose is always sans. Mono is
not a stylistic accent here — it is what makes a column of figures scannable and
keeps digits from reflowing as values change.

**The No Webfont Rule.** The app loads zero font files. A new face would cost a
network round trip on the exact interaction that must feel instant.

## Layout

Below 960px: a single centered column, `max-width: 560px`, with `2rem 1.25rem 4rem` of
body padding — one destination, no navigation, no sidebar, no tabs. The login page uses
a narrower 380px column offset `8vh` from the top; the settings view keeps the 560px
column at every width, because a form only gets harder to read when its fields grow.

From 960px the main view drops its width cap and becomes a twelve-column grid
(`24px` gaps, `2.5rem` side padding) that fills the window's height as well as its
width — on a large monitor there is no empty band below the content. The markup keeps
the phone's order; on the desktop the wrappers `.topbar`, `.dash` and `.dash-history`
switch to `display: contents`, so their parts become cells of that grid, while below
960px the groups stay plain blocks without spacing of their own and the phone layout is
untouched:

```
logo + title  |   input + quick chips (centered)   |  menu
stat cards    |  coach
today's list  |  history chart (grows with the window height)
weight        |
disclaimer
```

- **The input sits in the middle of the header**, 52px tall and at most 760px wide,
  with the quick chips centered beneath it: logging is the one action the page is
  opened for. The logo (`logo-96.png`, 48px) appears to the left of the title.
- **960–1399px:** cards, entries and weight take five of twelve columns, coach and
  chart seven. The metric switch stands above the range controls as on the phone, and
  the selected day's detail sits below the chart.
- **From 1400px:** the split becomes four to eight. Switch and range share one row,
  and the selected day's detail stands in a 320px column beside the chart, so picking
  a day never shrinks the bars. With no day selected that column is empty and 0 wide.
- **From 1800px, three columns of cards:** with two columns a large monitor only made
  everything wider — four entries spread over 1200px, a chart the height of the window,
  a coach panel with 200-character lines. Instead the page becomes three columns, three,
  four and five twelfths wide, and every group sits in a card as tall as its content:

  ```
  stat cards     |  today's list   |  history chart (fixed height)
  coach          |                 |  selected day
  weight         |                 |
  disclaimer
  ```

  The left column is `.dash-today` plus the weight card in the row below it; the entry
  list and the history span into the `1fr` row, so they do not stretch the coach's row.
  Switch and range stack again, as they do not fit side by side in five twelfths. The
  chart is `clamp(240px, 34vh, 380px)` tall instead of filling the window, and the
  selected day is a section of the history card under a hairline, not a card of its
  own. The page ends with its content rather than filling the window height.
- **Zoom from 1800px:** both views grow as a whole — `zoom: 1.15` from 1800px, `1.4`
  from 2400px, `2` from 3400px — because phone-sized type looks lost on a 27-inch or
  4K screen. The steps keep the unzoomed width between about 1560 and 1920px, so the
  grid looks the same on every large monitor. Zoom instead of per-element sizes,
  because every measure is tuned in px for the narrow column; `app.js` measures the
  chart with `clientWidth`/`clientHeight`, which ignore the zoom, so the bars are not
  scaled twice.

The last content row is `1fr` and absorbs the remaining window height. The chart spans
into it and stretches (at least 220px); `app.js` reads its real size and redraws
whenever it changes. The chart carries `contain: size`, so its height comes from the
grid alone — otherwise the bars, which are computed from that very height, would count
towards it and the chart would grow with every redraw. Anything spanning into the `1fr`
row is left out when the browser sizes the `auto` rows, so the entries close up under
the cards no matter how tall the chart gets. The coach is stretched to the height of
the two stacked stat cards, with its footer pinned to the bottom.

Vertical rhythm is built from a small set of repeated gaps rather than a strict
baseline grid: `8px` between paired controls, `1rem` after a message or chip row,
`1.75rem` after the stat cards, and `2rem` closing each major block (entry list,
chart, coach panel). Horizontal gaps are tighter — `6px` between chips and chart
columns, `4px` between icon buttons.

The stat cards are a grid of two equal columns (`1fr 1fr`, 12px gap) collapsing to one
below 420px. The edit form's three-up field grid (`1fr 1fr 1fr`) collapses to two at the
same breakpoint. There are four breakpoints in the stylesheet: 420px for phones,
960px and 1400px for the desktop columns, 1800px for the three-column card layout,
plus two zoom-only steps at 2400px and 3400px.

### Named Rules

**The One Column Rule.** On phones and tablets everything lives in one 560px column
in a fixed vertical order: input, quick chips, stats, coach, today's entries, history
chart, weight, disclaimer. The whole interface is meant to be thumbed through in one
scroll. The desktop columns redistribute these same groups and keep the order inside
each group; they never add a sidebar, a tab bar, navigation, or content that exists only
on the desktop. The one exception is the logo beside the title, which is branding, not
content.

**The 16px Zoom Guard.** On touch screens (`pointer: coarse`) and below 420px every
form field goes to 16px. Anything smaller makes iOS Safari zoom into the page on tap
and never zoom back out. Heights stay unchanged. Never ship a mobile field under 16px.
Gesture zoom is switched off on purpose, at the owner's request: the viewport sets
`user-scalable=no`, `html` carries `touch-action: pan-x pan-y`, and `nozoom.js`
cancels the pinch gesture iOS Safari would otherwise still allow. Because nothing can
be zoomed, text size has to be readable as shipped.

## Elevation & Depth

The implemented system is entirely flat: there is not one decorative `box-shadow`
anywhere in the stylesheet. Depth comes from two devices only — a tonal step between
the page ground and the surface above it (`#FAF8F3` → `#FFFFFF` in light,
`#191817` → `#222120` in dark), and a 1px hairline border on every raised element.

Nothing floats above the page. The settings used to be a modal with a scrim and the
system's only shadow; they are now a view that replaces the main one, so there is no
second plane left to separate. Cards, panels, chips, and buttons stay flat at rest and
always will.

### Shadow Vocabulary

- **Focus ring** (`box-shadow: 0 0 0 1px var(--accent)`): Paired with a border shift
  to `--accent` on focused inputs and selects, so border and ring read as one solid
  2px line — the same weight as the `:focus-visible` outline everywhere else.

### Named Rules

**The Flat-At-Rest Rule.** A surface that sits in the page does not cast a shadow. Only
something that genuinely floats above the page may, and today nothing does. Adding a
shadow to a card, chip, or button to make it "pop" is the decorative use this system
rejects.

## Shapes

Softly rounded rectangles throughout, on a scale that increases with the size of the
surface: `8px` on 32px icon buttons, `12px` on 44px inputs and buttons (the `--radius`
default), `14px` on cards and panels. Chips are the one fully
rounded form — `15px` on a 30px height, a true pill, marking them as taps rather than
fields.

The scale is deliberately one notch warmer than a purely functional one would be: this
is the "warm and tactile" direction spent on form rather than on ornament, which is the
only place it can be spent without crossing into maximalism.

Three shapes are deliberately partial: the goal bar is a `3px` capsule, history bars are
rounded only at the top (`5px 5px 0 0`) so they read as growing from a shared baseline,
and the menu icon's three strokes take a `1px` cap. Borders are always exactly 1px,
everywhere, with no exceptions.

### Named Rules

**The 44px Thumb Rule.** Primary interactive controls — text inputs, selects, buttons
— are 44px tall. Secondary controls (icon buttons, range toggles, chips) drop to 32px
or 30px. This is a one-handed phone app; the primary path never gets a small target.

**The Hairline Rule.** Structure is 1px. Where more separation is needed, change the
border color (`--border` → `--border-strong`) or the surface tone, not the width.

## Components

### Buttons

- **Shape:** Softly rounded (10px), 44px tall, 18px horizontal padding, no border.
- **Primary:** Solid Quiet Garden Green with `--on-accent` text at 500 weight. Note
  that `--on-accent` is white in light mode but a very dark green (`#10201A`) in dark
  mode — the accent is light enough there that white text would fail.
- **Hover / Focus:** Background shifts to Deep Garden Green. There is no transition
  declared on buttons; the change is immediate. Disabled drops to `opacity: 0.6`.
- **Ghost:** Transparent with a Hairline Strong border and secondary text; hovers to a
  white surface with primary text. Its `.active` state (used by the 7/14/30 range
  toggles) fills with Garden Wash and switches border and text to accent.
- **Icon:** 32px square, transparent, muted text, 6px radius, hovering to Garden Wash.
  A `.danger` modifier hovers to Brick Wash instead. The settings trigger draws its
  three lines from one element plus two pseudo-elements, using `currentColor` so it
  inherits the hover state for free.
- **Link:** Height-free, underlined, 13px, Deep Garden Green — used for "Neu
  einschätzen", logout, and CSV export.

### Chips

- **Style:** White surface, Hairline Strong border, secondary text, 30px pill.
- **Suffix:** Each chip carries its kcal in mono at 11.5px in Ink Muted, separated by
  5px — the quick-entry chip states its own value before you tap it.
- **State:** Hover fills Garden Wash and switches border and text to accent. There is
  no selected state; a chip is an action, not a filter.

### Cards / Containers

- **Corner Style:** 12px.
- **Background:** Card White on the Warm Paper ground.
- **Border:** 1px Hairline. No shadow (see Elevation & Depth).
- **Internal Padding:** `14px 16px`.
- **Contents:** A 12.5px secondary label, a 24px mono value, and an optional 12px
  muted note that can take `.good` (accent) or `.warn` (amber) coloring.

### Inputs / Fields

- **Style:** White surface, 1px Hairline Strong stroke, 10px radius, 44px tall, 15px
  text, full width.
- **Focus:** Border shifts to accent plus a 3px Garden Wash glow.
- **Selects:** Fully custom — `appearance: none` (the native rendering ignores the
  height and clips the text) with a hand-drawn chevron as an inline SVG data URI,
  positioned right 13px. Because a CSS custom property cannot be interpolated inside
  `url()`, the chevron is declared a second time in the dark block with a lighter
  stroke. Options get explicit surface and text colors, or some browsers render the
  open list in OS colors.
- **Numeric fields:** `input[type="number"]` switches to mono. The weight field is
  deliberately `type="text"` with `inputmode="decimal"` — with `type="number"`, Safari
  silently discards a comma decimal ("68,5") while still displaying it.

### Settings View

- **Style:** Not an overlay but a place you move to. The menu button swaps the whole
  main view for the settings view in a 560px column, on the same page ground,
  with no scrim, border, or shadow. It always opens scrolled to the top; going back
  restores the main view's scroll position.
- **Head:** A back-arrow icon button in front of a 22px display heading
  "Einstellungen", with the same `1.75rem` gap to the content as the main subtitle.
- **Navigation:** Opening pushes a history entry, so the phone's back gesture and the
  browser's back button return to the main view instead of leaving the app. The back
  arrow, "Abbrechen", Escape, and a successful save all go back the same way. A reload
  while the settings are open keeps them open.
- **Structure:** Stacked 14px-spaced fields each with a label and an optional 12px
  muted hint, a message line, two equal-width actions, then a hairline divider and a
  column of link-style secondary actions.

### Coach Panel

The system's signature component, and the one place the app speaks in sentences. An
ordinary hairline card whose status is carried by a drawn 18px icon sitting left of the
headline: a check when on track, an up arrow when above goal, a down arrow when behind,
a dash when there is not enough data, a warning triangle when the estimate failed. The
icon takes the status color (accent, amber, or brick); the panel's own surface and border
never change.

The shape carries the meaning and the color reinforces it — a bare color could not be
decoded without a legend, which is why this replaced an earlier 3px colored left edge.
Inside: a 14.5px semibold balanced headline, a 13.5px secondary message at 1.55
line-height with `text-wrap: pretty`, an optional bulleted tip list, and a footer pairing
a muted timestamp against a link-style refresh action.

### History Chart

Bars are full-height buttons in a flex row (140px tall, on the desktop filling the free window height, 6px
gaps), each column bottom-aligned so all bars share a baseline. On a gaining account the bar is Hairline
Strong when the day fell short and accent when it reached the goal; on a losing
account accent means the day stayed under the ceiling and Muted Amber means it went
over, with days that have no entries left Hairline Strong rather than counted as a
day held. Either way the chart is readable as "did I make it" without a legend.
Three details carry the craft:

- Focus is moved off the column and onto the bar (`:focus-visible .week-bar`), because
  a ring around a full-height column highlights empty space.
- Hover and selection never recolor a bar, so its own color — the answer to "did I make
  it" — stays readable. Both draw a 2px outline 2px off the bar: Ink Secondary on hover
  (mouse only, `hover: hover`), Quiet Garden Green when selected. The gap is what keeps
  a green ring visible around a met (green) bar; flush, it merged into it. Today gets
  no bar marker at all, only the bold day label. The column must also cancel the
  generic `button:hover` fill, which otherwise paints the whole column.
- Bars carry `flex-shrink: 0`, without which tall days compress to equal heights.
- The total and label slots hold a fixed minimum height even when empty, so the
  30-day view — which labels only every fifth day — keeps a common baseline.

A dashed Hairline Strong goal line crosses the chart. The current goal is not labeled
on the line — there it always covered the total of a day close to the goal — but in a
small legend (the value in 10.5px mono) at the right end of the note
row under the chart, so the bars keep their full width. Older goals within the range
keep an inline label on their own stretch of line, backed by the page color. The label
names what the line is in that mode — "Ziel" when gaining, "Grenze" when losing.

### Metric Switch

A three-part control above the history chart — Kalorien · Eiweiß · Gewicht — that
changes what the chart draws. It is not navigation: the page stays the same, only
the chart's content changes, so it does not break the One Column Rule. A Hairline
Strong track on Card White, 44px tall from 36px segments inside 3px of padding, so
the outer height matches the primary controls. The chosen segment uses the active
range-toggle look (Garden Wash, accent border, Deep Garden Green text, 600 weight)
and carries `aria-pressed`. On the phone it spans the column; from 960px it stops at
360px. Switching keeps the range, the page and the selected day, so one day can be
read across all three charts, and the choice is remembered per device in
`localStorage`, like the color scheme.

- **Protein** uses the calorie bars unchanged, in grams against the protein goal that
  applied on each day. That goal is always a floor, even on a losing account, so a
  protein bar is never amber. Without a protein goal no bar turns green, there is no
  goal line, and the legend says "kein Eiweißziel". The day detail lists the same
  entries with grams on the right.
- **Weight** is a line, not bars: there is no weight goal, so nothing is green. The
  line is Ink Secondary at 1.75 stroke, each weighed day an Ink dot ringed in the page
  color; days without a measurement have no dot. The scale does not start at zero but
  spans at least 2 kg, so a 100 g wobble never reads as a fall; hairline grid lines
  at whole kilograms carry mono labels backed by the page color. Hover and selection
  ring the dot exactly as they ring a bar. Values sit above the dots when columns are
  wide enough, otherwise only on the last measurement and the selected day. The
  legend shows the change across the range, the detail the previous measurement and
  the difference.

### Icons

Every icon is drawn, never typed. All paths live in one `ICON` map in `app.js` and render
through a single helper at a fixed `1.75` stroke width on a 24-unit grid, with round caps
and joins — the same stroke as the select chevron, so a field arrow and a delete button
look like they came from one hand. The set is deliberately small: pencil, trash, check, up,
down, dash, warning, and the two chart chevrons plus the settings back arrow inlined in
the markup.
Icons inherit `currentColor`, so an icon button's hover state needs no icon-specific rule.

Size is 16px inside 32px icon buttons and 18px for the coach status. The one non-path
mark is the settings menu, drawn from an element plus its two pseudo-elements.

### Entry Row

A flex row on a 1px Hairline divider: description at 14.5px with a 12px muted
timestamp beneath, then a right-aligned group holding mono kcal, optional smaller mono
protein, and edit and delete icon buttons. Editing replaces the row in place with a
stacked form — a three-up numeric grid above a full-width description — rather than
opening a dialog, so a correction never leaves the list.

## Do's and Don'ts

### Do:

- **Do** put every comparable number in mono (`var(--mono)`) and every sentence in
  sans. This is the system's most load-bearing rule.
- **Do** take colors only from the custom properties on `:root`. The one sanctioned
  exception is an inline SVG data URI, where `var()` cannot be interpolated — in that
  case declare the asset twice, once per theme, as the select chevron does.
- **Do** keep the warm cast in dark mode. New dark values follow `#191817`/`#222120`,
  never neutral gray and never pure black.
- **Do** give primary controls 44px of height and mobile fields 16px of type.
- **Do** convey depth with a tonal step plus a 1px hairline first, before reaching for
  a shadow.
- **Do** treat `accent-dark` as "stronger than accent", resolving it lighter in dark
  mode.
- **Do** keep phones and tablets in one 560px column in its established order, and
  let the desktop only redistribute the same groups.
- **Do** draw icons as SVG paths at `1.75` stroke on the 24-unit grid, added through the
  `icon()` helper so a new symbol cannot drift in weight.
- **Do** theme the surfaces the browser supplies: `::selection`, `caret-color`,
  scrollbar thumb and track, `accent-color`, focus rings, underline offset, and
  `-webkit-tap-highlight-color`. These ship with defaults that belong to no design
  system, and they are the cheapest signal that a page was built rather than assembled.
- **Do** give every comparable figure `font-variant-numeric: tabular-nums`, so a column
  of numbers does not shift width when a value changes.
- **Do** keep motion as response: state feedback at 120–180ms, and exactly one authored
  moment — the goal bar advancing over 620ms on an exponential ease-out. Honor
  `prefers-reduced-motion`.

### Don't:

- **Don't** add vivid gradients, glassmorphism or backdrop blur, blurred color blobs,
  oversized rounded cards, or illustrated mascots. Consumer-app maximalism is the one
  confirmed rejection; warmth is expressed through material and touch instead.
- **Don't** add a `prefers-color-scheme` block to the stylesheet. `theme.js` resolves
  system preference to a literal `data-theme` before first paint, so there is exactly
  one dark block and one unambiguous state — a media query would reintroduce the
  mixed state that was deliberately removed.
- **Don't** introduce a second accent hue. Amber and brick are reserved for caution
  and destruction; a fourth hue would break the Quiet Accent Rule.
- **Don't** widen the container past 560px below 960px, and never add a sidebar, a tab
  bar, or desktop-only content (the header logo is the one piece of desktop-only
  branding).
- **Don't** use accent green as a decorative tint on surfaces, headings, or borders
  that carry no affirmative meaning.
- **Don't** add another breakpoint casually. The system has four (420px for phones,
  960px and 1400px for the desktop columns, 1800px for large screens); a new one should
  be justified by a real layout failure.
- **Don't** use a Unicode glyph or emoji as an icon (`×`, `✎`, `‹`, `›`). They arrive in a
  foreign weight and baseline on every other device. Draw the path instead.
- **Don't** encode status with color alone, and never with a colored border heavier than
  1px. Status gets a shape — an icon or a word — that survives being seen once.
- **Don't** let an interactive element rely on the browser's default focus ring. Every
  control has a `:focus-visible` treatment; the chart column moves its ring onto the bar
  because a ring around a full-height column outlines empty space.
