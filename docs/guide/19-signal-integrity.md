# Signal integrity: calculated impedance, sized termination, chosen stackups

WO-78 (charter `docs/spec/toolchain/35-signal-integrity.md`, D186)
makes board-level SI a calculated, auditable discipline: controlled
impedance is a discharged claim over fab-published stackup records,
termination is sized by cited formulas with the arithmetic in
evidence, and the layer count is a `by select` decision the discrete
engine takes under your cost policy. The models are feldspar's WO-25
set (Hammerstad-Jensen microstrip, Cohn exact stripline, exact-algebra
termination sizing), memo-calibrated with narrow validity predicates;
regolith routes to them and never re-implements the physics.

## 1. Stackups are records

`stdlib/std.elec.stackups` carries the fab's own published stackups
(JLCPCB controlled-impedance page, transcribed verbatim, AD-34
citation per row): one 2-layer, six 4-layer, and three 6-layer
classes, each with its outer prepreg span, material Dk, core span,
and copper weights. A stackup a fab does not publish is not a record.

```
[[stackup]]
key = "jlc04161h_7628"
outer_prepreg_mm = 0.2104   # the microstrip dielectric height h
outer_prepreg_dk = 4.4      # its er
outer_copper_mm  = 0.035    # the trace thickness t
...
evidence = { method = "catalog", trust_tier = "community", reference = "..." }
```

## 2. Impedance is a claim

```
require SignalIntegrity:
    clk_z0: elec.impedance(clk, role=microstrip, stackup=jlc04161h_7628, layer=outer, w=0.36mm) within [45ohm, 55ohm]
    dq_z0:  elec.impedance(dram_dq, role=stripline, w=0.382mm, b=1mm, er=3.66) within [55ohm, 65ohm]
```

The window lowers to two one-sided obligations (`.lo`/`.hi`); each
half discharges against the matching feldspar model with h/er/t
resolved FROM THE NAMED RECORD (microstrip, outer layer) and `w` from
the claim. Both the computed Zo and the model's declared accuracy
enter the margin math -- at `w=0.28mm` the same claim's `.hi` half is
honestly VIOLATED at 56.1 ohm, never rubber-stamped. Stripline claims
state `b`/`er` explicitly: no fab publishes the per-layer role table a
cavity derivation would need (a recorded residual, in the record
file's own notes).

Pre-layout, the trace width is an ordinary `in [lo, hi]` slot the
optimizer solves against the claim (D184 boundary-finding):
`tests/orchestrator/test_wo78_si_width_pin.py` pins `w` at the
window's ceiling crossing, `optimize(...)`-caused -- the pinned width
IS the calculated design rule.

## 3. Termination is sized, not folklore

```
    clk_rs:      elec.termination(clk, scheme=series, z0=50ohm, ro=15ohm) >= 33ohm
    bus_r1:      elec.termination(bus_en, scheme=thevenin, leg=r1, z0=50ohm, vcc=5V, vbias=1.5V) >= 160ohm
    clk_shunt_r: elec.termination(clk, scheme=ac_shunt, part=r, z0=50ohm) >= 47ohm
    clk_shunt_c: elec.termination(clk, scheme=ac_shunt, part=c, rise_time=1ns, r=50ohm) >= 0F
```

Each claim routes to the exposed sizing model (`Rs = Z0 - Ro`, the
Thevenin pair, `R = Z0`, `C = tr/4R`) and the sized value lands in
evidence. The ac-shunt C direction's declared accuracy is the
quarter-rise-time heuristic's own +100% band, so the only floor it
can honestly certify is 0 -- the claim documents the computed size
rather than pretending the heuristic guarantees an E24 window.
`scheme=parallel` and differential pairs (`role=diff`) DEFER with
named reasons: feldspar exposes no model for either (its own recorded
cuts), and regolith never invents physics to fill a gap.

Rule-side presence (supply-pin bypass, clock-net termination schemes)
is `std.board_correctness` content (guide 15) -- WO-78 adds no
duplicate rules, only the sizing claims and the fixture pair
(`examples/negative/72_si_ac_shunt_bypass_missing.cupr` fires;
`examples/tracks/cuprite/si_board.cupr` passes with sized values).

## 4. Layer count is a `by select`

```
    impl SiStackup by select(jlc04161h_7628, jlc06161h_7628, jlc04161h_1080)
```

Candidates are stackup record keys; feasibility = every impedance
claim achievable on the candidate (the cheapest candidate above is
screened OUT at 26.9 ohm); the objective is cost, and flipping the
declared cost order flips the 4-layer/6-layer winner with the full
`optimize(cost, trace=...)` audit trail
(`tests/test_wo78_stackup_select.py`). The selection evidence says
"impedance-feasible + screen-passed", never "routable" -- routability
stays post-layout evidence, honestly.

## 5. The SI sheet

`regolith preview`/`ship` derive a per-board SI table sheet (the
AD-27 schedule mechanism, track `si`): claim / net / target / stackup
/ layer / geometry / computed value / margin / status / model id /
cause, one row per SI obligation, derived from the build's own
obligations + evidence (`ship.si_rows_from_report`) -- an
unattributable number on the sheet is unrepresentable, and the parity
classifier accounts every row's cause.

## 6. Exemplars

- `examples/tracks/cuprite/si_board.cupr` -- every claim form, the
  select, and the rule packs on one board.
- `examples/flagships/mainboard_mx/si.cupr` -- the carrier's refclk
  discipline plus the honestly-deferring USB differential window.
- `examples/flagships/riscv_hart_rv1/package.cupr` -- the package
  clock input's impedance + sized series termination.
