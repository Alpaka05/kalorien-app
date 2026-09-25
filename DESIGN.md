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
  backdrop: "rgba(43, 42, 38, 0.4)"
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
  xl: "18px"
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
  modal:
    backgroundColor: "{colors.bg}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.xl}"
    padding: "20px"
    width: "420px"
---

# Design System: Kalorien-Tagebuch

## Overview

**Creative North Star: "The Warm Ledger"**

The atmosphere is plain, honest, and unhurried. Nothing is dressed up.

This is bookkeeping of a body without the coldness that usually comes with it.
Surfaces are warm — a cream paper ground (#FAF8F3), a dark mode tinted brown rather
than black. Numbers are monospaced and exact. Sans reads, mono counts.

The interface is one 560px column with no navigation and no second place to look. It
is used one-handed on a phone, seconds after eating. Estimates read as estimates and
stay correctable. The page does not rush, congratulate, or celebrate.

Components should feel warm and tactile: 44px targets, softly rounded surfaces. This
runs slightly ahead of current code, which is more restrained than tactile — push
radii, surface warmth, and micro-interaction further. The one bound is firm: no
consumer-app maximalism.

**Key Characteristics:**

- Cream-paper ground with white surfaces; a warm-brown dark mode, never pure black (only the opt-in OLED scheme uses a #000000 ground).
- One accent — a desaturated garden green — carrying every affirmative signal.
- Monospace for every comparable number; system sans for all prose.
- A single 560px column, no navigation, one settings modal.
- Hairline 1px borders and tonal layering; one shadow, reserved for the overlay.
- Motion as response, not animation: one authored moment, everything else under 200ms.

## Colors

A warm, low-saturation palette built from a single green accent against cream and
brown-tinted neutrals; the only other hues are a muted brick for destructive actions
and an amber for caution.

### Primary

- **Quiet Garden Green** (`#4A7A64` light, `#66A385` dark): Desaturated and domestic,
  a grown thing rather than a brand color — deliberately not a vivid app-accent green.
  It fills primary buttons, fills history bars for days that met the goal, draws the
  goal-progress fill, and draws focus rings. It is the system's only affirmative
  voice.
- **Deep Garden Green** (`#2E5643` light, `#8AC2A4` dark): The stronger sibling. Used
  for primary-button hover, selected chart bars, link text, and "good" notes.
- **Garden Wash** (`#E7F0EA` light, `#23332B` dark): The faint accent field behind
  hovered chips and icon buttons, active range toggles, and the 3px focus glow.

### Secondary

- **Muted Amber** (`#976927` light, `#D2A25C` dark): Caution, not alarm. Marks a goal
  bar pushed past target, history bars over the ceiling in losing mode, and "warn"
  notes. Paired with **Amber Wash** (`#F7EFE0` / `#332A1B`) and, for the hover and
  selected states of an amber chart bar, **Strong Amber** (`#6F4C1B` / `#E8C089`) —
  the same role `accent-dark` plays for green.

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
- **Label** (400, 12.5px): Card labels and modal field labels. Drops to 11.5px for
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

A single centered column, `max-width: 560px`, with `2rem 1.25rem 4rem` of body
padding — one destination, no navigation, no sidebar, no tabs. The login page uses a
narrower 380px column offset `8vh` from the top; the settings modal caps at 420px.

Vertical rhythm is built from a small set of repeated gaps rather than a strict
baseline grid: `8px` between paired controls, `1rem` after a message or chip row,
`1.75rem` after the stat cards, and `2rem` closing each major block (entry list,
chart, coach panel). Horizontal gaps are tighter — `6px` between chips and chart
columns, `4px` between icon buttons.

The stat cards are the only grid: two equal columns (`1fr 1fr`, 12px gap) collapsing
to one below 420px. The edit form's three-up field grid (`1fr 1fr 1fr`) collapses to
two at the same breakpoint. There is exactly one breakpoint in the entire stylesheet.

### Named Rules

**The One Column Rule.** Everything lives in one 560px column in a fixed vertical
order: input, quick chips, stats, coach, today's entries, history chart, weight,
disclaimer. Never introduce a sidebar, a tab bar, or a second column — the whole
interface is meant to be thumbed through in one scroll.

**The 16px Zoom Guard.** Below 420px every form field goes to 16px. Anything smaller
makes iOS Safari zoom into the page on tap and never zoom back out. Heights stay
unchanged. Never ship a mobile field under 16px.

## Elevation & Depth

The implemented system is entirely flat: there is not one `box-shadow` on a resting
surface anywhere in the stylesheet. Depth comes from two devices only — a tonal step
between the page ground and the surface above it (`#FAF8F3` → `#FFFFFF` in light,
`#191817` → `#222120` in dark), and a 1px hairline border on every raised element.
Even the modal, the most elevated thing in the app, separates itself with a
translucent scrim (`rgba(43, 42, 38, 0.4)`) and a stronger border rather than a lift.

One shadow exists, and only one: the settings modal. Depth is spent where depth means
something — an overlay is genuinely on a different plane than the page — and nowhere
else. Cards, panels, chips, and buttons stay flat at rest and always will.

### Shadow Vocabulary

- **Overlay** (`--shadow-overlay`, two warm layers: `0 12px 32px -8px` at 20% plus
  `0 2px 8px -2px` at 10% of the ink color): The settings modal only. Tinted from
  `--text-primary` rather than pure black, so it stays in the warm family, and carries
  a real offset with a soft blur. The dark-theme variant deepens to 64%/40% black,
  because a warm shadow is invisible on a warm-dark ground.
- **Focus ring** (`box-shadow: 0 0 0 1px var(--accent)`): Paired with a border shift
  to `--accent` on focused inputs and selects, so border and ring read as one solid
  2px line — the same weight as the `:focus-visible` outline everywhere else.
- **Today marker** (`box-shadow: inset 0 0 0 1px var(--accent-dark)`): An inset
  hairline on today's chart bar — deliberately quiet so it doesn't outshout the
  selected bar.

### Named Rules

**The Flat-At-Rest Rule.** A surface that sits in the page does not cast a shadow. Only
something that floats above the page does, and today exactly one thing floats. Adding a
shadow to a card, chip, or button to make it "pop" is the decorative use this system
rejects.

## Shapes

Softly rounded rectangles throughout, on a scale that increases with the size of the
surface: `8px` on 32px icon buttons, `12px` on 44px inputs and buttons (the `--radius`
default), `14px` on cards and panels, `18px` on the modal. Chips are the one fully
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

### Modal / Settings

- **Style:** The only overlay. A translucent scrim over the page, top-aligned with
  `2rem 1.25rem` padding and its own scroll, so a tall settings panel works on a short
  phone. The panel itself uses the *page* ground (`--bg`) rather than Card White,
  inverting the usual figure/ground relationship so it reads as a surface you moved to
  rather than one floating above.
- **Corner:** 14px, with a Hairline Strong border.
- **Structure:** Title row with a close icon button, stacked 14px-spaced fields each
  with a label and an optional 12px muted hint, a message line, two equal-width
  actions, then a hairline divider and a column of link-style secondary actions.

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

Bars are full-height buttons in a flex row (140px tall, 6px gaps), each column
bottom-aligned so all bars share a baseline. On a gaining account the bar is Hairline
Strong when the day fell short and accent when it reached the goal; on a losing
account accent means the day stayed under the ceiling and Muted Amber means it went
over, with days that have no entries left Hairline Strong rather than counted as a
day held. Either way the chart is readable as "did I make it" without a legend.
Three details carry the craft:

- Focus is moved off the column and onto the bar (`:focus-visible .week-bar`), because
  a ring around a full-height column highlights empty space.
- Bars carry `flex-shrink: 0`, without which tall days compress to equal heights.
- The total and label slots hold a fixed minimum height even when empty, so the
  30-day view — which labels only every fifth day — keeps a common baseline.

A dashed Hairline Strong goal line crosses the chart with its value in 10px mono,
backed by the page color so the line doesn't run through the digits. Its label names
what the line is in that mode — "Ziel" when gaining, "Grenze" when losing.

### Icons

Every icon is drawn, never typed. All paths live in one `ICON` map in `app.js` and render
through a single helper at a fixed `1.75` stroke width on a 24-unit grid, with round caps
and joins — the same stroke as the select chevron, so a field arrow and a delete button
look like they came from one hand. The set is deliberately small: pencil, trash, check, up,
down, dash, warning, and the two chart chevrons plus the close X inlined in the markup.
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
- **Do** keep the whole interface in one 560px column in its established order.
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
- **Don't** widen the container past 560px or add a second column, sidebar, or tab bar.
- **Don't** use accent green as a decorative tint on surfaces, headings, or borders
  that carry no affirmative meaning.
- **Don't** add a second breakpoint casually. The system has one (420px); a new one
  should be justified by a real layout failure.
- **Don't** use a Unicode glyph or emoji as an icon (`×`, `✎`, `‹`, `›`). They arrive in a
  foreign weight and baseline on every other device. Draw the path instead.
- **Don't** encode status with color alone, and never with a colored border heavier than
  1px. Status gets a shape — an icon or a word — that survives being seen once.
- **Don't** let an interactive element rely on the browser's default focus ring. Every
  control has a `:focus-visible` treatment; the chart column moves its ring onto the bar
  because a ring around a full-height column outlines empty space.
