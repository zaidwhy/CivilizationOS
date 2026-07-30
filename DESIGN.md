# CivilizationOS - Design Language

This documents the visual language that already exists in `web/src/index.css`, `App.tsx`,
`panels/*.tsx`, `components/Onboarding.tsx`, and `city/CityStage3D.tsx` (the Three.js
renderer actually mounted by `App.tsx` - see "Two city renderers" below). It is written
from the code as it stands - every token, scale, and convention below is something
actually in use today, not an aspiration for a future redesign. Treat this as the source
of truth for future UI changes: if a new rule needs a color, radius, or motion, it should
reach for something on this page before inventing a new one-off value.

## Principles

- **Dark-only, "mission control" panel look.** There is no light theme and no
  `prefers-color-scheme` handling anywhere - `body` hardcodes `var(--bg)` plus a faint
  radial glow. The layout is a fixed two-pane grid (`.layout { grid-template-columns: 1fr
  360px; }`): a full-bleed 3D city stage on the left with a vignette overlay
  (`.city::after`), and a scrolling sidebar of stacked instrument panels on the right -
  Inspector, Relationship Graph, Event Feed, Council Chamber, Timeline, Chronicle, Stats.
  This reads as an observation deck over a simulation, not a form-based app.
- **Status is communicated through pills.** The topbar is a horizontal strip of `.pill`
  capsules (connection state, clock, phase, citizen count, active crises, tension meter,
  stability badge, spend counter) - a single reusable shape for "small piece of live
  status," styled per-instance via inline `color`/`borderColor` rather than semantic pill
  variants (see "Ad hoc color usage" below).
- **Semantic hue per state, reused by convention rather than by code sharing.** Blue
  (`--accent`) = primary/informational/live, green (`--good`) = calm/positive/thriving,
  amber (`--warn`) = caution/tension, red (`--danger`) = crisis/danger/negative, purple
  (`#a78bfa`, not tokenized - see below) = council/social/faction. This mapping is
  consistent in *meaning* across the app, but - unlike the root `:root` block promises -
  it is almost entirely re-declared as literal hex per file rather than consumed via
  `var()`. That is the biggest honest gap this document surfaces.

## Color tokens (`:root`, `web/src/index.css`)

| Token | Value | Role |
|---|---|---|
| `--bg` | `#0a0d13` | Page background |
| `--panel` | `#131926` | Declared but not referenced by any rule in `index.css` today (panels are styled via the `.panel` class's own rules and gradients, not this token) |
| `--panel2` | `#0e131d` | Sidebar background gradient start |
| `--line` | `#1f2937` | Default 1px hairline border/divider (panel separators, bars, tracks) |
| `--line-bright` | `#2d3a4f` | Brighter border variant: pill borders, scrollbar thumb |
| `--text` | `#e8eef5` | Primary body text |
| `--muted` | `#8b97a7` | Secondary/label text |
| `--accent` | `#6ea8fe` | Primary blue: brand wordmark glow, live/info pill text, focus outline, "now" callout, range-input thumb |
| `--accent-soft` | `rgba(110, 168, 254, 0.12)` | Accent tint background (`.now` callout) |
| `--good` | `#4ade80` | Positive/calm: live-connection pill, positive relationship bar fill |
| `--warn` | `#fbbf24` | Caution: fear-bar gradient endpoint |
| `--danger` | `#f87171` | Crisis/negative: crisis pill, fear-bar gradient endpoint |
| `--shadow-panel` | inset highlight + soft drop shadow | Declared, not referenced by any rule in `index.css` today |
| `--font-mono` | `"JetBrains Mono", ui-monospace, ...` | Reserved for data/numeric display via the `.mono` utility class - in practice `.mono` is defined but not applied anywhere in the four files that were checked for it (`App.tsx`, `panels/*.tsx`); tabular/numeric UI (tick counters, percentages, spend figures) currently renders in the default Inter body font instead |

Two tokens (`--panel`, `--shadow-panel`) and one utility class (`.mono`) are defined but
currently unused - reserved-for-later rather than dead code to delete outright, in the same
spirit as `recall`'s unused `--panel-hover`/`--accent-glow` tokens.

### Ad hoc color usage (the real, honest state)

`--good`, `--warn`, `--danger`, and `--accent` are consumed via `var()` in `index.css`
itself, but every panel component (`panels/*.tsx`, `App.tsx`, `components/Onboarding.tsx`)
re-declares the *same* hex values as inline-style literals instead of importing the
tokens - there is no shared TS/JS constants module bridging CSS custom properties into
component code. Counting exact-value duplicates across `web/src/**/*.tsx`:

| Hex literal | Matches token | Occurrences outside `index.css` |
|---|---|---|
| `#f87171` | `--danger` | 19 |
| `#fbbf24` | `--warn` | 21 |
| `#4ade80` | `--good` | 13 |
| `#6ea8fe` | `--accent` | 7 |
| `#8b97a7` | `--muted` | 6 |

On top of that, several *additional* colors are used consistently for their own semantic
roles but were never promoted to `:root` tokens at all: purple `#a78bfa` (council/social,
~10 uses across `CouncilChamber.tsx`, `Chronicle.tsx`, `RelationshipGraph.tsx`, `Timeline.tsx`),
slate `#475569`/`#64748b` (secondary/timestamp text, ~18 uses), and a family of
institution-specific colors (see below).

This is real, widespread ad hoc duplication - not a single typo. Fully tokenizing it would
mean touching six-plus files and hundreds of lines, which is a deliberate future refactor,
not a one-night polish pass (same judgment call `recall`'s DESIGN.md made about its unwired
glow tokens). This pass fixes one small, fully contained instance of it (see "Polish pass"
below) and documents the rest honestly rather than pretending the app is more tokenized
than it is.

### Institution colors: a real but partially-drifted shared palette

`city/CityStage3D.tsx`'s `LOCATION_TYPES` map defines an `accent` hex per building type
(home `#4b7fa8`, workplace `#b07d3a`, commons `#3a8a5c`, institution `#6b5db8`).
`panels/CouncilChamber.tsx`'s `INST_COLORS` reuses those exact four values for
`inst_media`, `inst_economy`, `inst_health`, `inst_gov` respectively, plus a fifth,
`inst_police: #c96060`, with no location-type equivalent. This cross-file, cross-format
(Three.js `0xRRGGBB` numbers vs. CSS `"#RRGGBB"` strings) color agreement looks deliberate
and is a real shared design decision, just not backed by a shared constant anywhere.
`panels/StatsPanel.tsx`'s `CouncilScorecard`, however, defines its *own* `INST_COLORS` for
the same five institutions using an entirely different palette (`inst_gov: "#6ea8fe"`,
`inst_economy: "#fbbf24"`, etc.) that does not match `CouncilChamber.tsx` or
`CityStage3D.tsx` at all. This is a genuine, visible inconsistency - the same institution
gets a different badge color depending which panel you're looking at - but reconciling it
would change on-screen colors in one of the two panels, which is out of scope for a
zero-visual-change polish pass. Flagged here for a future, deliberate pass rather than
silently fixed.

### Two city renderers

`city/CityStage.tsx` (Pixi.js, 2D isometric) and `city/CityStage3D.tsx` (Three.js) both
exist and both implement a full renderer with their own hardcoded palettes. Only
`CityStage3D` is imported by `App.tsx` (`import CityStage from "./city/CityStage3D"`) -
`CityStage.tsx` is currently dead code, not mounted anywhere. Left alone here; removing an
unused file is a reasonable future cleanup but isn't a "design language" change.

## Typography

- **Inter** (400/500/600/700/800, loaded via Google Fonts `@import` at the top of
  `index.css`) is the UI font, set globally on `:root`.
- **JetBrains Mono** (`--font-mono`) is reserved for numeric/data display via the `.mono`
  utility class, though as noted above it is not currently applied by any of the panels
  checked - actual tick counters, percentages, and dollar figures render in Inter.
- No formal type-scale tokens exist; sizes are per-rule `px` values (this codebase does not
  use `rem` for type at all, unlike `recall`). Reading across `index.css` and the panels,
  sizes cluster loosely: `13px`-`15px` for panel titles/headers, `11px`-`13px` for body/
  label text, `9px`-`10px` for micro-labels and timestamps. This is a real, workable
  hierarchy but it is informal - the same "10px muted timestamp" role is independently
  re-declared in nearly every panel file rather than sharing one utility class (`.xsmall`
  exists in `index.css` at `10px` and is used in exactly one place, `Inspector.tsx`).
- The topbar wordmark (`CIVILIZATION OS`) uses `letter-spacing: 3px` plus a colored
  `text-shadow` glow on the `OS` span - the one deliberately "logotype" treatment in the
  app, not reused elsewhere.

## Layout and spacing

- **Two-pane app shell**, fixed proportions: `.app` is a `display: grid` with `auto 1fr`
  rows (topbar, then body); `.layout` is `1fr 360px` columns (city stage, then a
  fixed-width sidebar). Nothing is responsive - there is no media query anywhere in
  `index.css`, and `360px` is a literal, not a token, appearing exactly once.
- **No spacing scale.** Padding/margin/gap values are chosen per rule in raw `px` with no
  custom properties and no consistent step (`index.css` alone has panel padding of
  `13px 14px`, topbar padding of `8px 16px`, pill padding of `2.5px 10px` - three different,
  unrelated paddings within one file). This is ad hoc, not a hidden 4px/8px grid - flagged
  honestly rather than implying a system that isn't there.
- **Panels stack vertically in the sidebar**, each wrapped in `.panel` (padding + bottom
  hairline via `--line`), with an internal `.section` label style (uppercase, letter-spaced,
  trailing gradient rule fading into `--line`) used to break up content within a panel
  (relationships, memory stream, etc.).

## Border radius

No `--radius` token exists (unlike `recall`'s explicit two-token scale). Reading the
literal values actually used across `index.css` and every panel, there is a real but
informal graduation by element size:

| Radius | Used for |
|---|---|
| `999px` | Pills, progress bars/tracks/fills, badges - every "capsule" shaped element |
| `50%` | Round elements: memory dots, event-timeline node circles |
| `6px`-`8px` | Standard card/box radius: panel callouts, toast messages, tooltips, buttons, canvas backgrounds - the single most common non-pill value |
| `4px`-`5px` | Small controls: selects, textareas, small buttons, badges-with-borders |
| `3px` | Sparkline/histogram canvas corners |
| `12px` | The one outlier: `Onboarding.tsx`'s modal card |

This scale is consistent enough to be a real (if unwritten) convention - `6px`-`8px` for
"card," `4px`-`5px` for "control," `999px` for "capsule" - even though nothing enforces it
as a token.

## Motion / transitions

All animation lives in two places: `@keyframes` in `index.css`, and ad hoc inline
`transition` strings in component code.

| Keyframe / transition | Communicates | Used on |
|---|---|---|
| `crisis-pulse` (`index.css`) | "This crisis is active right now" | `.crisis-pill`, the tension-meter pill above 85% pressure |
| `fade-in` (`index.css`) | "New content just appeared" | Panel `<h3>` on mount, expanded timeline entries, the Chronicle dispatch body |
| `toast-slide-in` (`index.css`) | "A notification just arrived" | The bottom-left toast stack over the city view |
| Inline `transition: width ...` (several panels) | A stat/bar is animating toward a new value | Relationship bars, fear bars, council-effectiveness bars, memory-count bars - each panel re-declares its own duration (`0.4s`, `0.5s`, `0.6s`) rather than sharing one |
| Inline `transition: background/border-color ...` | Hover/selection feedback | Pills, buttons, feed rows, the debate accordion border |

There is no shared "duration scale" - `0.15s`/`0.2s`/`0.3s`/`0.4s`/`0.5s`/`0.6s` all appear
as one-off literals depending on which panel was written when. This is informal but not
broken; nothing about it produces visibly clashing motion.

## Component conventions actually in use

- **`.pill`** - the one true shared component class. Base style (capsule border, muted
  text) plus two modifier classes (`.live`, `.off`) and one variant class
  (`.crisis-pill`); every other pill state in the topbar (`StabilityBadge`,
  `TensionMeter`, `SpendCounter`) reuses the base `.pill` class but overrides color via
  an inline `style` prop rather than adding a new modifier class - functionally fine,
  but means "add a new pill color" today means writing inline styles, not extending CSS.
- **`.panel` / `.panel-head` / `.panel-title` / `.section`** - the shared sidebar-panel
  chrome (padding, divider, title row, section labels). Every panel in `panels/*.tsx` uses
  these, though several panels *also* apply an extra inline `borderTop: "1px solid
  var(--line)"` on top of the class's own `border-bottom` (`Timeline.tsx`, `Chronicle.tsx`,
  `StatsPanel.tsx`, `CouncilChamber.tsx`) - each panel independently re-adds a divider the
  base class doesn't provide, rather than the base class handling it once.
- **Bars/tracks** - `.bar`/`.fill` (relationships) and `.fear-track`/`.fear-fill` are two
  near-identical but separately-declared track+fill pairs in `index.css` - both are a thin
  rounded track with a colored, width-animated fill; no shared base class exists for
  "progress bar," so `StatsPanel.tsx`'s council-effectiveness and memory-count bars build a
  third copy of the same pattern from scratch in inline styles.
- **Badges** - small pill-shaped `<span>` tags for crisis names, custom crises, and
  faction names (`EventFeed.tsx`, `CouncilChamber.tsx`, `Chronicle.tsx`) all hand-roll the
  same `fontSize: 10, padding: "2px 7px", borderRadius: 999, background: <color>15,
  border: 1px solid <color>30` shape independently in three files rather than sharing one
  `Badge` component.
- **Onboarding modal** (`components/Onboarding.tsx`) is a one-off full-screen overlay with
  its own local palette (`#141a24` card background, `#232c3b` borders) that doesn't
  reference `:root` tokens at all, plus two values that happen to exactly duplicate
  `--muted` and `--accent` (see "Polish pass" below).

## Polish pass (this change)

`components/Onboarding.tsx` hardcodes `#8b97a7` twice (the tour-body copy color and the
"Back" button text color) and `#6ea8fe` twice (the active step-dot fill and the primary
button background) - both values are exact, byte-for-byte matches for `--muted` and
`--accent` already defined in `index.css`. This is the same category of issue as the
broader ad hoc duplication documented above, but contained to a single file and a single,
small, mechanical fix: swap the four literals for `var(--muted)` / `var(--accent)`. Zero
visual change (identical resolved colors), no component restructuring, no other value
touched. The other colors in this file (`#141a24`, `#232c3b`, `#e6edf3`, `#0b0e14`,
`#475569`) do not match any existing token and were left as-is rather than inventing new
tokens for them, consistent with this being a polish pass, not a redesign.

No other single-file, exact-token-match duplication of this size was found; every other
instance surfaced above spans multiple files and/or lacks a byte-identical existing token
to fall back to, which is why they are documented rather than changed.
