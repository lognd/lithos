# WO-143 -- Moody calc-sheet figure: `diagram.moody` through the one renderer (charter 41 rule 6/AD-39)

Status: open (Depends: WO-139)
Language: Python (`python/regolith/backends/drawings/producers.py`
  family -- a new producer beside the existing optimization-trace
  chart producer).
Spec: F158 sec. a5 (the recon's verdict: build the Moody chart as a
  calc-sheet FIGURE, not a new artifact family); charter 41 rule 6
  (`docs/spec/toolchain/41-artifact-presentation.md:39-42`: "CHARTS
  ARE CHARTS: axes with ticks and unit-labeled titles, gridlines at
  the minor emphasis level, a legend when more than one series,
  annotated points labeled without collision. A bare polyline is not
  a chart" -- GATING via the drafting audit, INV-31); AD-39
  (`00-architecture.md:1128`, one artifact-presentation standard,
  gating, WITH VISUAL PROOF -- the coordinator inspection this WO's
  acceptance requires at integration); D224 (every plotted number
  traces to the payload/record it came from); the existing chart
  precedent this producer follows structurally:
  `python/regolith/backends/drawings/producers.py:745-798`
  (objective-vs-candidate trace, winner marked ON the chart); the
  calc book itself, `python/regolith/backends/calc.py` (WO-114/D221)
  -- one sheet per discharged obligation; this figure is an ADDITION
  to that family, not a new mechanism.

## Goal

An engineer opening the dp calc sheet for a discharged `fluids.dp`
obligation sees a real Moody chart: log-log f-vs-Re curves for the
pinned eps/D family, the laminar line, the transition band honestly
shaded as indeterminate, and the discharging obligation's own
operating point marked on the chart with its obligation id -- every
number on it traceable to a real payload or record.

## Deliverables

1. `diagram.moody` DrawingModel producer
   (`python/regolith/backends/drawings/producers.py` or a sibling
   module in the same package): renders, for a pinned family of
   eps/D ratios drawn from the WO-138 roughness record + the claim's
   own pipe diameter:
   - log-log axes: f (y, log) vs Re (x, log), both WITH ticks and
     unit-labeled titles (charter 41 rule 6 -- no bare polyline).
   - the laminar line (f = 64/Re, Re < 2300).
   - one curve per eps/D value in the pinned family, computed via
     WO-139's Haaland model (never an inline fitted curve this
     producer invents).
   - the transition band (2300 <= Re <= 4000) SHADED and labeled as
     indeterminate -- the D97 regime-tag honesty from WO-139 carried
     onto the figure, not silently interpolated across.
   - the operating point of the discharging obligation marked ON the
     chart, labeled with its obligation id (the winner-mark
     precedent at `producers.py:795`).
2. Wiring into the dp calc sheet: the figure renders on the SAME
   sheet as the `fluids.dp` discharge it illustrates, through the
   ONE DrawingModel renderer -- no second renderer, no bespoke
   plotting path.
3. Drafting audit coverage: the new producer passes the existing
   gating drafting audit (INV-31) -- nothing clips, nothing overlaps,
   the legend appears when more than one eps/D curve is drawn.
4. AD-39 visual proof at integration: the coordinator inspects a
   rendered instance of the figure (not just its data), logs the
   content hash and a pass/fail verdict, per the standing AD-39
   ruling-3 practice.

## Out of scope

- Any new artifact family or renderer -- this is a producer inside
  the existing calc-book/DrawingModel machinery.
- The friction-factor model itself (WO-139) and the roughness record
  (WO-138) -- this WO consumes them, does not define them.
- Demo wiring / fleet enrollment (WO-144).

## Acceptance

- `diagram.moody` producer exists and is invoked from the dp calc
  sheet for at least one discharged `fluids.dp` fixture (WO-139's new
  corpus fixture, or small_office once WO-138/139/140/141 land):
  checkable by rendering that fixture's calc book and confirming the
  figure is present in the output artifact.
- The drafting audit passes on the new figure: `uv run pytest
  tests/backends/drawings/ -k moody -q` (or the equivalent audit
  invocation this WO adds) green, with an explicit assertion that
  axes carry ticks + unit-labeled titles and the transition band is
  shaded.
- The operating point's label matches the discharging obligation's
  id exactly -- a test asserts the label string equals the claim's
  obligation id.
- AD-39 visual-proof log entry exists for this figure (coordinator
  inspection, hash + verdict recorded) before this WO closes.
- `make check` green.

## Escalation

If the drafting audit cannot express "shaded indeterminate band" as
a chart element with the existing style-record vocabulary, escalate
to charter 41 rather than inventing a one-off styling hack outside
the ONE renderer.
