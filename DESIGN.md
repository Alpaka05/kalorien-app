---
name: Kalorien-Tagebuch
description: A calm, near-black calorie and protein ledger — zinc neutrals, hairline cards, a sidebar on the desktop, monospace numerals, green only for a met goal.
colors:
  bg: "#FFFFFF / #09090B"
  surface: "#FFFFFF / #0C0C0E"
  muted-bg: "#F4F4F5 / #1C1C1F"
  sidebar-bg: "#FAFAFA / #111113"
  border: "#E4E4E7 / #27272A"
  border-strong: "#D4D4D8 / #3F3F46"
  text-primary: "#09090B / #FAFAFA"
  text-secondary: "#52525B / #A1A1AA"
  text-muted: "#6B6B74 / #8B8B94"
  primary: "#18181B / #FAFAFA"
  on-primary: "#FAFAFA / #09090B"
  accent: "#16A34A / #22C55E"
  accent-dark: "#15803D / #4ADE80"
  danger: "#DC2626 / #F87171"
  warn: "#B45309 / #FBBF24"
  ember: "#EA580C / #FB923C"
typography:
  hero:
    fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    fontSize: "40px (28px on phones)"
    fontWeight: 500
    letterSpacing: "-0.03em"
  page-title:
    fontSize: "34px (28px on phones)"
    fontWeight: 500
  section-title:
    fontSize: "15px"
    fontWeight: 700
  card-label:
    fontSize: "11.5px"
    fontWeight: 700
    letterSpacing: "0.06em"
    textTransform: uppercase
  body:
    fontSize: "14.5px"
    lineHeight: 1.55
  metric:
    fontFamily: "ui-monospace, 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace"
    fontSize: "26px"
    fontWeight: 600
rounded:
  sm: "6px"
  md: "8px"
  lg: "12px"
spacing:
  card-padding: "16px 18px"
  grid-gap: "16px 20px"
  sidebar: "248px (64px collapsed)"
  pagebar: "60px (56px on phones)"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    rounded: "{rounded.md}"
    height: "44px (52px for the food input on the desktop)"
  button-outline:
    backgroundColor: "{colors.surface}"
    border: "1px {colors.border}"
    hover: "{colors.muted-bg}"
  card:
    backgroundColor: "{colors.surface}"
    border: "1px {colors.border}"
    rounded: "{rounded.lg}"
    padding: "16px 18px"
---

# Design System: Kalorien-Tagebuch

## Overview

**North Star: "The Quiet Dashboard"**

The look follows a dark dashboard in the style of shadcn/ui (the reference was
eliteskyblock.com): a near-black ground, a slightly lighter sidebar, cards that are the
same color as the page and live only from a 1px zinc border, and white buttons with
black text. Nothing glows, nothing floats. Color is reserved for meaning — green for a
met goal, amber for caution, red for destruction, ember for streaks — and every other
pixel is a neutral.

The page opens on a centered hero: the title, one line of subtitle and the food input
with its quick chips beneath, like the search block on a landing page. Logging is the one
action the app is opened for, so it sits where the eye lands first. Below it the day's
numbers, entries, chart, weight and calendar each stand in their own card.

Numbers stay monospaced and exact. Sans reads, mono counts.

**Key Characteristics:**

- Zinc neutrals in both themes: `#09090B` ground in dark mode, white in light mode;
  OLED is an opt-in pure-black variant of dark.
- One primary action style — inverted text on `--primary` (white in dark, near-black in
  light). Green never marks a button.
- Every group is a card: `--surface`, 1px `--border`, 12px radius, `16px 18px` padding.
  The two stat cards carry a faint diagonal gradient from `--muted-bg` and an uppercase,
  letter-spaced label.
- A left sidebar from 960px (icons only up to 1280px, labels above that, collapsible from
  the header), a sticky header with a breadcrumb everywhere, a bottom bar on the phone.
- Monospace for every comparable number; system sans for all prose. No webfonts.

## Colors

### Neutrals (the whole interface)

- **Ground** (`--bg`): page background. Copied into the browser theme-color in
  `theme.js` and the manifest.
- **Surface** (`--surface`): cards, inputs, chips. In dark mode a hair above the ground
  (`#0C0C0E`), in light mode identical (white) — the border does the separating.
- **Muted** (`--muted-bg`): hover fills, the active sidebar item, the metric-switch track,
  empty bars and calendar cells, and the top-left tone of the stat-card gradient.
- **Sidebar** (`--sidebar-bg`): one step off the ground so the navigation reads as a
  frame, not content.
- **Hairline** (`--border`) and **Hairline Strong** (`--border-strong`): card borders and
  dividers; field strokes, the dashed goal line and the outline of unreached bars.
- **Ink**, **Ink Secondary**, **Ink Muted** (`--text-*`): text in three steps. Ink Muted
  must clear 4.5:1 on ground and surface in both themes — it carries timestamps, hints
  and placeholders.
- **Primary** / **On Primary**: the main button. White on black in dark mode, black on
  white in light mode.

### Signals

- **Signal Green** (`--accent`, `#16A34A` / `#22C55E`): a day that met its goal — bars,
  the goal bar, calendar and habit cells, the checked habit button. `--accent-dark` is
  the stronger sibling ("stronger", not "darker": in dark mode it is lighter).
- **Amber** (`--warn`): over the limit when losing, caution notes.
- **Red** (`--danger`): delete hover and errors only.
- **Ember** (`--ember`): streaks in the goals area only.

### Named Rules

**The Meaning-Only Color Rule.** Hue appears only where it says something. Buttons,
toggles, tabs, chips, links, focus rings and selection are neutral. A green surface
always means "goal met".

**The One Dark Block Rule.** `theme.js` resolves "Automatisch" to `data-theme="light"` or
`"dark"` before first paint; the stylesheet has exactly one dark block and no
`prefers-color-scheme` query. OLED is `data-oled` on top of dark and only overrides the
ground, surface, sidebar and hairlines.

## Typography

System sans (`system-ui` first) and system mono — no font files, so the app stays instant
on a phone. Headings are large and light at the top of a page (hero 40px/500, page titles
34px/500 on the desktop, both at −0.03em) and small and heavy inside cards (section
titles 15px/700). Card labels are 11.5px, 700, uppercase with 0.06em tracking. Body text
is 14.5px; hints and timestamps 12px in Ink Muted.

**The Mono Numeral Rule.** Every number the user might compare across days is
monospace with `tabular-nums`: card values, entry kcal and protein, chart totals,
day-detail totals, chip suffixes, the goal legend and numeric inputs.

**The 16px Zoom Guard.** On touch screens and below 420px every form field is 16px, or
iOS Safari zooms in on tap and never zooms back. Gesture zoom is switched off on purpose
(`user-scalable=no`, `touch-action`, `nozoom.js`), so type must be readable as shipped.

## Layout

### Frame

- **Phone (< 960px):** a sticky 56px header with the logo, the breadcrumb and the
  theme switch; the content in one 560px column; the area bar fixed at the bottom (icon
  over label, the active one on a Muted pill, hidden while a field has focus). The
  sidebar element dissolves (`display: contents`), only its bar stays.
- **Desktop (≥ 960px):** a fixed sidebar on the left — logo and title, the group label
  "Bereiche", the three areas as 38px rows (active and hover on Muted), and at the
  bottom CSV export and the account (click logs out). Up to 1280px it is a 64px rail with
  icons only; above that 248px with labels. The panel icon in the header overrides
  either default and is remembered per device (`data-sidebar`, set by `theme.js` before
  first paint so the bar never jumps). The narrow form is a container query on the
  sidebar, so it follows the real width rather than the viewport.
- **Header:** sticky, 60px, translucent ground with a backdrop blur and a hairline below.
  Panel toggle, then the breadcrumb `⌂ / Bereich / Seite` (home goes to Kalorien, the
  area crumb goes back to the goal list from a goal or the goal form), then the
  light/dark switch on the right.

### Calorie area

Below 960px the cards stack in the phone order: hero with input and chips, stat cards
(two columns, one below 420px), coach, entries, chart, weight, calendar, footnote.
`.dash-side` dissolves there (`display: contents`).

From 960px the view is a twelve-column grid (`16px 20px` gaps);
`.dash` and `.dash-history` switch to `display: contents` so their parts become grid
cells while the markup keeps the phone order. Chart and weight share one cell
(`.dash-side`, a flex column), so the left column's height never depends on the right:

```
            hero: title, input + quick chips (centered, ≤ 760px)
stat cards    |  coach
entries       |  history chart (fixed height)
calendar      |  weight
footnote
```

The chart is `clamp(200px, 30vh, 320px)` tall at every desktop width. It used to fill
the free window height next to entries, weight and calendar, and the bars became a wall.
Weight sits under the chart because the chart is also where the weight curve is read.

- **960–1399px:** five to seven columns; switch and range stack above the chart, the
  selected day sits under the chart behind a hairline.
- **From 1400px:** four to eight. Switch (300px) and range share a row, the selected day
  stands in a `clamp(300px, 22vw, 420px)` column beside the chart behind a vertical
  hairline, so picking a day never shrinks the bars.
- **From 1800px:** three columns of cards — stat cards, coach and calendar on the left;
  entries in the middle; chart, selected day and weight on the right. The page ends with its content.
- **Zoom:** `zoom` 1.15 from 1800px, 1.4 from 2400px, 2 from 3400px, applied to sidebar
  and `.shell` alike so the sidebar width and the content's left margin grow together.
  `app.js` measures the chart with `clientWidth`/`clientHeight`, which ignore zoom.

The chart carries `contain: size` so its height comes from CSS alone — otherwise bars
computed from that height would feed back into it.

### Other areas

Goals use up to 1040px (cards in an auto-fill grid of ≥ 300px, a goal split 5:7 into
streak and history); the goal form and settings stay at 560px, because a form only gets
harder to read when its fields grow. Page titles are left-aligned, large and light, with
a muted subtitle — like a tools index page.

### Named Rules

**The Three Areas Rule.** Kalorien, Ziele, Einstellungen — no fourth area. Every level
below an area is a history entry, so the back gesture walks back and finally to
Kalorien. The sidebar holds navigation and account only, never content that the phone
lacks.

## Elevation & Depth

Flat. Cards do not cast shadows; they are separated by a 1px hairline and, in dark
mode, a one-step tonal lift. The only translucency is the sticky header and the phone's
bottom bar (ground at ~90% with a blur), so content scrolling beneath them stays legible
without a hard cut. Nothing else floats.

## Shapes

`6px` for small controls (icon buttons, chips, metric segments), `8px` for inputs and
buttons, `12px` for cards and the desktop food input. History bars are rounded only at the
top (`4px 4px 0 0`). Borders are always exactly 1px.

**The 44px Thumb Rule.** Primary controls — inputs, selects, buttons — are 44px tall
(the desktop food input 52px). Secondary controls (icon buttons, range toggles, chips)
drop to 32px or 30px.

## Components

### Buttons

- **Primary:** `--primary` fill, `--on-primary` text, 500 weight, 8px radius; hover
  mixes 12% of the ground in. Pressed moves down 1px. Disabled at 0.6 opacity.
- **Outline (`.ghost`):** Surface fill, Hairline border, Ink text; hover Muted. Its
  `.active` state (range toggles 7/14/30) inverts to the primary look.
- **Icon:** 32px, transparent, Ink Muted; hover Muted with Ink. `.danger` hovers red.
- **Link:** Ink, underlined in Hairline Strong; the underline turns Ink on hover.

### Chips

Surface fill, Hairline border, 6px radius, 30px tall, secondary text with the kcal in
11.5px mono. Hover: Muted fill, Hairline Strong border, Ink text. A chip is an action,
never a selected state.

### Cards

Surface, 1px Hairline, 12px radius, `16px 18px`. Inside, a 15px/700 section title, then
content; list dividers are hairlines and the last row has none. The stat cards add the
Muted→Surface gradient and an uppercase label above a 26px mono value. The selected day
belongs to the chart card and is separated by a hairline, never a card in a card.

### Inputs / Fields

Surface fill, Hairline Strong stroke, 8px radius, 44px, 15px text. Focus: the border
goes to Ink Muted and a soft 3px ring of 14–16% Ink appears around it. Selects are fully
custom (`appearance: none`) with a drawn chevron declared once per theme, because `var()`
cannot be used inside `url()`. The weight field is `type="text"` with
`inputmode="decimal"` so Safari keeps a comma decimal.

The **backfill bar** is the one tinted row: `--accent-bg` with an `--accent` border while
logging for a past day, so nobody books today's lunch on yesterday by accident. The
**photo attach** row sits above the input as a surface card with a 52px thumbnail.

### Metric Switch

Segmented control in the shadcn tabs style: Muted track, 3px padding, 36px segments; the
chosen one is a raised Ground tab with a Hairline border and 600 weight, carrying
`aria-pressed`.

### Settings View

- **Style:** An area of its own, reached from the area bar, in a 560px column on the
  same page ground with no scrim, border, or shadow, under the same sidebar and header
  as every other area. It always opens scrolled to the
  top; the calorie area keeps its scroll position.
- **Head:** A page heading "Einstellungen" (28px, 34px at weight 500 on the desktop), with the same `1.75rem` gap to the
  content as the main subtitle.
- **Navigation:** Opening pushes a history entry, so the phone's back gesture returns
  to Kalorien instead of leaving the app. "Abbrechen" and Escape discard the fields and
  go back; a successful save stays and confirms with "Gespeichert.". A reload keeps the
  area open.
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
  (mouse only, `hover: hover`), Signal Green when selected. The gap is what keeps
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
the chart's content changes, so it does not break the One Column Rule. A Muted
track with a Hairline border, 44px tall from 36px segments inside 3px of padding, so
the outer height matches the primary controls. The chosen segment uses the active
range-toggle look (Muted, accent border, Signal Green Strong text, 600 weight)
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

### Goals (Ziele)

Something done `n`× per day, week (Monday to Sunday) or month. A period counts as met
when enough entries fall into it; week and month goals count each day at most once.
The streak counts met periods in a row — the running period never breaks it, it only
adds once met.

- **Card:** an icon tile, name and frequency, a 44px round check-in button on the right
  (plus at rest, filled green with a check once today is entered; hovering turns a
  checked button solid brick with a cross and a click takes today's entry back out —
  on touch the first tap arms it, the second removes; right after checking in it stays
  green until the pointer has left it, so a double click cannot undo), the running period
  as one segment per unit in green, and a streak row under a hairline: ember flame,
  number in mono, and the last periods as 9px squares (the running one outlined).
- **Adding:** one 44px square plus in the page head, always. With no goals yet the
  six suggestions fill the card grid as dashed tiles (icon tile dashed too), each
  opening the form already filled in. Their plus is small and borderless so it never
  reads as the round check-in button; hover draws the border in Ink Muted
  over a Muted fill. Once a goal exists the suggestions live only as chips in
  the form.
- **Streak card:** a 48px flame tile in `--ember-bg`, the streak as the largest number
  on the page (34px mono, ember), the record on the right, then one continuous ember
  bar to the next milestone (days 3·7·14·30·60·100·180·365, weeks 4·8·12·26·52, months
  3·6·12·24). The running period flows into the bar proportionally, so every check-in
  moves it; the flag chip at its end fills when a milestone is reached. Below, the
  running period as pills labelled with the day (or time) of each entry. The bar's
  gloss stripe is the one concession to Duolingo.
- **History:** a GitHub-style grid, one column per week, Monday on top, as many weeks as
  fit. Green means entered (half green: part of a multi-per-day goal); weekly goals add
  a 4px Signal Green Strong stroke under each week that was met. Tapping a day opens a
  small panel to back-fill or delete.
- **Celebration:** the flame hops and the number rolls in on every completed period.
  Completing a week or month additionally throws confetti from the bottom edge of the
  screen (ember, green, gold; about two seconds, pointer-transparent canvas). Daily goals
  get no confetti — it would turn into daily noise. Reduced motion shows the new state
  only.

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

- **Do** put every comparable number in mono and every sentence in sans.
- **Do** take colors only from the custom properties on `:root`; a data-URI SVG is the
  one exception and is declared once per theme.
- **Do** keep interactive chrome neutral — inversion (primary) or Muted fills — and let
  hue speak only for met, caution, error and streak.
- **Do** put every group in a hairline card and separate sub-sections inside a card with
  a hairline, not another card.
- **Do** give primary controls 44px of height and mobile fields 16px of type.
- **Do** draw icons as SVG paths at `1.75` stroke on a 24-unit grid.
- **Do** theme the browser's own surfaces: selection, caret, scrollbars, `accent-color`,
  focus rings, tap highlight.
- **Do** keep motion as response (120–180ms); the goal and streak bars and the confetti
  are the only authored moments. Honor `prefers-reduced-motion`.

### Don't:

- **Don't** add shadows, glows, colored gradients or blobs. The stat-card gradient is
  neutral and stays the only one.
- **Don't** color a button, tab or toggle green. Green means a met goal.
- **Don't** add a `prefers-color-scheme` block; `theme.js` owns the theme state.
- **Don't** add a fourth area or put content into the sidebar.
- **Don't** add breakpoints casually: 420px, 960px, 1280px (sidebar), 1400px, 1800px,
  plus the zoom steps.
- **Don't** use a Unicode glyph or emoji as an icon, and never encode status with color
  alone.
