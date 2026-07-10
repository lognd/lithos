# timber_pavilion -- flagship-5, the calcite civil pavilion

WO-74 (docs/workflow/work-orders/WO-74-flagship-pavilion.md), full
A->C arc in one dispatch per the WO-64 template. A timber
post+girder+purlin pavilion (`.calx`, the calcite flagship) built
end to end: contract-first structure -> feldspar-backed member
verdicts (real `civil.utilization`/`mech.deflection` discharge) ->
section-search optimization over `std.civil.timber_sawn` -> declared,
basis-cited loads running the tributary demand path (D183).

## Envelope targets (asserted givens)

- **6x9m footprint** (`program.calx`'s `Pavilion` space, `area:
  54m2`), modeled structurally as ONE representative 3m bay
  (`frame.calx`'s `grid width: A, B spacing 3.0m`) -- the WO-74
  ledger's wall notes explain why (a genuine two-axis row/column
  member endpoint is unverified against this toolchain; a 9m clear
  span is not feasible for the `std.civil.timber_sawn` family under
  the declared roof loads). The SAME "one frame line shown, the full
  [structure] repeats per grid line" scoping `pole_barn.calx`
  (calcite/02 sec. 1) already establishes as precedent.
- **Loads DECLARED at rung 1** (D183): `frame.calx`'s `snow`/`wind`
  lines are literal `kPa` values `on [Purlin]` with a `by
  catalog(...)` basis citation, the same rung-1 pattern already
  landed in `examples/systems/small_office/frame.calx`'s `live`/
  `roof_lv` lines -- NOT the `site.<x> -> std.civil.asce7.<model>`
  derivation chain, which stays a recorded residual. The load reaches
  the twin girders G1/G2 via the declared `Bearing(tributary=...)`
  transfers (`pur_g1`/`pur_g2`) -- the tributary demand path D183
  asks to exercise.
- **Two independently-searched member groups** over
  `std.civil.timber_sawn` (G1, G2 -- the twin girders), each with its
  own `regolith optimize`-shaped trace and a disclosed mass tie-
  breaker (WO-56 rule) -- the WO-74 "search on >= 2 member groups"
  requirement. The family was widened mid-dispatch from 2 to 11
  dressed sawn sizes (WO-74 ledger, coordinator ack); the search runs
  over the real, widened domain.

## File map

| file | contract |
|---|---|
| `site.calx` | site truth only (`site MeadowLot: boundary/soil`) |
| `program.calx` | the one occupied space + egress |
| `frame.calx` | grid/level + post+girder+purlin structure, transfers, declared loads, `require Structure` (also carries the full WO-74 wall-note trail as file-header comments) |

Note: `grid`/`level` live in `frame.calx`, not `site.calx` (WO-74
ledger wall 1: a landed cross-file grid/level length-computation gap,
now fixed on master mid-dispatch per the coordinator's ack -- the
split-file shape, grid/level back in `site.calx`, is legal again, but
this already-tested co-located shape was kept rather than reworked
for aesthetics per the coordinator's explicit instruction).

## Known residuals (WO-74 ledger, full detail in the WO file)

- `civil.bearing_pressure`/`civil.story_drift`/`mech.first_mode`
  stay `no_frame_model` deferrals (WO-48 deliverable 5 covers only
  `civil.utilization`/`mech.deflection` -- the same landed scope
  `small_office`'s own `require Structure` already lives with).
- `civil.embedment`/frost-depth-vs-footing-embedment is NOT a
  registered claim form in the landed toolchain (`translate.py`
  recognizes `civil.utilization`, `mech.deflection`,
  `civil.story_drift`, `civil.bearing_pressure`, `mech.first_mode`
  only) -- omitted rather than authored as a claim that cannot
  discharge OR defer honestly; queued as a cycle-33 design item per
  the coordinator's ack.
- Posts (`P_A`/`P_B`) and the purlin (`Purlin`) are fixed-section,
  not searched: a `column` has no resolvable demand in the landed
  harness (axial demand is pinned at 0, WO-48 deliverable 5 scope) so
  a search cannot even start; the purlin's own direct load is a `kPa`
  pressure fact (a tributary SOURCE only), and a `kN/m` direct line
  load on an `on [...]` target silently does not lower today (WO-74
  ledger wall 3) -- so a `beam`-role member with only a pressure load
  cannot resolve its own demand either. `civil.utilization`'s
  `.members.all` aggregate form is therefore not usable over the full
  `PavilionFrame` membership; `frame.calx` targets G1/G2 individually
  instead (the OTHER form `translate.py` supports), an honest
  narrowing, not a fabricated pass.
- Ship artifacts (plan/section sheets, member schedule,
  `civil_takeoff` cost estimate) are NOT realized in this dispatch --
  see the WO-74 ledger's honest-partial disposition.
