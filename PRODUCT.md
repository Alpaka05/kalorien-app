# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

The owner is the primary and effectively only user: one person tracking their own
intake on their own server. A small number of explicitly invited people (via
`ALLOWED_EMAILS`, typically a partner) may have their own accounts; each account
sees only its own entries.

There is no public user base and none is planned. The audience is not "anyone who
self-hosts" — the README's deployment documentation exists so the owner and an
invited person can set the app up again, not to recruit strangers. Future work
should optimize for a returning daily user who already knows the app, not for a
first-time visitor who must be convinced or taught.

The usage scene is a phone, held one-handed, immediately after eating. Entries
happen in seconds, several times a day, often while distracted or in a kitchen.
Reviewing history and weight trend is a rarer, calmer act.

## Product Purpose

A calorie and protein diary whose job is to make logging food fast enough that it
actually happens every day, and then show plainly whether the day's intake reached
the goal.

The user writes what they ate in ordinary German prose ("2 Scheiben Toast mit
Butter"); Claude estimates kcal and protein; the app shows how far the day is from
the target. Success is a long unbroken streak of honest daily entries and a visible
answer to "did I eat enough today" — not precision nutrition analysis.

## Positioning

The product was built around eating *enough*, not eating less, and that remains
the default: a new account is set to gaining, where the daily target is a floor to
reach or slightly exceed rather than the ceiling nearly every other tracker
assumes. Since the goal-direction setting, losing is a real second mode rather than
a tolerated edge case — the same target read as a ceiling, with the assessment,
the chart colors, and the estimator's rounding bias all inverted.

The two modes are deliberately not symmetrical in tone. Gaining is the one the
interface was designed for and the one the owner uses; losing must be correct and
complete, but it does not get its own hints, its own onboarding, or a place in the
default view. A setting is where it belongs.

The second differentiator is the entry method: free-text estimation instead of a
food database with search, portions, and barcode scanning. There is no catalogue to
navigate, which is what makes logging survivable day after day.

## Operating Context

- Self-hosted on the owner's own hardware (a Proxmox LXC / VM in a home lab), run
  via Docker Compose, reachable over a personal domain through a Cloudflare Tunnel
  or a reverse proxy. Often publicly reachable, which is why registration is closed
  by default.
- Data lives in a single SQLite file under `data/`, persisted across container
  rebuilds; backup is a tarball of that directory.
- Anthropic's API is the only external dependency. One API call per free-text
  entry, plus one per day for the assessment. Quick-entry chips cost nothing.
- Login is passwordless: an emailed 6-digit code, or the code printed to the
  container log when no SMTP server is configured.
- Days are user-defined: `day_start_hour` lets a day begin at, say, 04:00 so late
  night eating counts toward the previous day. Entry timestamps stay real; only the
  day bucket shifts, retroactively as well.
- Timezone is configured application-wide (`APP_TZ`, default `Europe/Berlin`).

## Capabilities and Constraints

Confirmed capabilities: free-text entry with AI-estimated kcal and protein, all
values correctable afterward; a fixed quick-pick row of common meals and drinks
with hard-coded values; a daily kcal goal read as a floor or a ceiling depending on
the account's goal direction, with a progress bar and remaining-kcal note; an
optional protein goal; a daily AI assessment of the last 14 days, cached per day
and manually refreshable; a 7/14/30-day history chart that pages
arbitrarily far back, with per-day detail on tap; weight logging with a 30-day
trend; CSV export of all entries; light/dark/system theming stored per device;
multiple isolated accounts.

Technical constraints future work must respect: Flask with server-rendered static
HTML pages and hand-written vanilla JS and CSS — no build step, no framework, no
bundler, and asset cache-busting done by substituting `__ASSET_V__`. SQLite with
idempotent, forward-only migrations that must survive several Gunicorn workers
starting at once. Structured Outputs on the Anthropic API for both AI calls.
`claude-haiku-4-5` is the default model, and the AI request budget must stay well
under a Cloudflare Tunnel's 100-second timeout.

The interface is German-only, permanently. There is no i18n layer and none is
wanted: copy may be written inline in German, and layouts should be designed for
German word lengths.

Estimates are explicitly approximate — based on typical portion sizes, not a
nutrient database — and the AI assessment is explicitly not medical advice. Both
disclaimers are load-bearing product facts, not boilerplate.

## Brand Commitments

Name: *Kalorien-Tagebuch*. Existing favicon, app icon, and logo assets live in
`static/`.

Voice: German, informal *du*, matter-of-fact and concrete. The coach names real
numbers from the user's own data instead of giving generic advice, flags days
without entries as unknown rather than scoring them as zero, and gives no medical
recommendations or diagnoses. Copy in the app explains consequences before they
surprise the user.

The existing visual character is warm and quiet — a cream-toned light palette and a
deliberately warm-tinted dark mode rather than pure black, a muted green accent, a
single narrow column, system sans with monospace reserved for numeric fields.

## Evidence on Hand

Real content available for design work: the running app and its own database of
entries, the German UI copy already written, and the deployment documentation in
`README.md`.

There are no customers, testimonials, case studies, press mentions, benchmarks,
pricing, or usage statistics, and there is no marketing surface of any kind. None
of these may be invented. The only meaningful "proof" this product can show is the
user's own logged data.

## Product Principles

1. Logging must stay faster than the excuse not to log. Any addition that lengthens
   the path from "I ate something" to "it's recorded" is a regression.
2. The goal has a direction and every surface obeys it. On a gaining account it is
   a floor and progress, assessment, and copy read as "enough yet?"; on a losing
   account it is a ceiling and the same surfaces read as "still under?". A mixture
   is the failure case: never a green bar next to a warning about the same day.
3. Estimates are shown as estimates and stay correctable. Never imply a precision
   the numbers don't have.
4. One person's private server, one person's data. No third-party services beyond
   the Anthropic API, no telemetry, and closed registration by default.
5. Every AI call must have a free fallback path, because the API can fail, cost
   money, or time out — and the diary still has to work.

## Accessibility & Inclusion

No specific requirement or standard has been established. Existing practice worth
preserving: real `aria-label`s and dialog roles on icon-only controls and the
settings modal, `inputmode` hints so phone keyboards match the field, both color
schemes declared so browser-native controls follow the theme, and a resolved
`data-theme` written before first paint to avoid a flash.
