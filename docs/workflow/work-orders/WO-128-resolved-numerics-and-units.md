# WO-128 -- Resolved numerics + units on the evidence surface (closes WO117-F2; F144)

Status: done
Language: Python (orchestrator translate/discharge evidence surface,
  backends/calc.py, backends/harness_pack.py); Rust ONLY if the
  claim's declared threshold genuinely loses its unit token in
  lowering (investigate first, report before touching crates).
Spec: F144 (the evidence: bring-up ships zero numbers); charter 41
  sec. 2 + D238.4 (every printed number carries its unit and traces
  to the payload); charter 40 sec. 3 + D224 (an expectation without
  a value is a named absence -- honest, but a value we COULD resolve
  and did not is a defect, not honesty); WO-114 (calc book -- the
  evidence source); WO117-F2 (the seed item this closes); WO-122
  (the bound-parse precedent: read-side qty crossing, ratified).

## Goal

Every discharged obligation's evidence carries the RESOLVED numeric
and its unit, so calc sheets print `14875.2 N` (not `14875.2`) and
the bring-up harness prints `expect 3.30 V +/- 0.15 V` (not a named
absence) wherever the toolchain genuinely knows the number.

## Why now (F144)

Cycle 36 shipped the bring-up machinery (WO-125/126) and the
professional sheet renderers (WO-123) -- and both landed on the same
wall: the values are there, the UNITS are not, so honest code either
prints a bare number (refused: a technician cannot act on `45`) or
degrades to `no_verified_expectation`. Today mainboard_mx's harness
pack has SIX taps and ZERO printed expectations. The machinery is
correct and the honesty is correct; the evidence surface is the gap.

## Deliverables

1. INVESTIGATE FIRST, then report before implementing: trace one
   discharged claim (mainboard's `refclk_z0.lo`, the calc book's
   `base_bolts` VDI-2230 sheet) end to end -- claim text -> lowered
   obligation (`rhs`, bound) -> model call -> `Evidence` -> calc
   sheet -- and record exactly WHERE the unit token is dropped and
   whether the resolved value is present. The fix belongs at the
   first surface that loses it, not downstream. Post the trace in
   your close-out ledger regardless of where it lands.
2. Units on the evidence surface: the discharged value, the margin,
   and the bound each carry their unit (the `regolith-qty` unit is
   already the ONE home -- reuse `Unit`/`si_magnitude`, never a new
   unit table, never a renderer-side lookup).
3. Calc sheets (`backends/calc.py`): Inputs rows, Result value, and
   margin print value + unit. Rows whose unit is genuinely
   unresolvable print an explicit `(unitless)` marker and are
   COUNTED in the sheet's own audit line -- no silent bare numbers.
4. Harness expectations (`backends/harness_pack.py`): every
   calc-sheet-backed tap prints its expected value + unit (+ window
   where the claim is a window claim). The WO-126 refusal rule
   (populated value implies units) stays; what changes is that rows
   now HAVE units. Rows still unresolvable stay named absences with
   their reason.
5. Regression tests at each surface; goldens regenerated (reviewed).
6. Census/verdict math UNTOUCHED (D206/D220.1) -- this WO adds no
   discharge, changes no verdict, and must prove it (census equality
   test before/after).

## Acceptance

- mainboard_mx's debug harness pack prints at least one REAL
  expected value with units, and every remaining absence names a
  reason that is not "unit_unresolved" (or, if some legitimately
  remain, they are enumerated with evidence in the close-out).
- demo15's calc sheets print units on every Inputs row, the Result
  value, and the margin (visually inspected; the coordinator
  re-inspects at integration, D238.3).
- Census golden byte-identical (no verdict moved).
- `make check` + `make health` green.

## Escalation

If the unit is dropped in RUST lowering (the claim's declared
threshold loses its unit token crossing into the obligation), STOP
and report with the trace from deliverable 1 -- the coordinator
adjudicates whether the fix is a Rust change and whether it needs
the D239 schema window (which is currently CLOSED and unspent).

## Close-out (WO-128 done)

### Deliverable 1: the trace (where the unit token is dropped)

Traced `mainboard_mx`'s `refclk_z0.lo` end to end:

| stage | carrier | unit present? |
|-------|---------|---------------|
| claim text (`si.cupr:25`) | `elec.impedance(refclk, ...) within [45ohm, 55ohm]` | YES (`ohm`, twice) |
| Rust lowering (`claims.rs::push_impedance_window_obligations`) | splits the window into `.lo`/`.hi` halves, each bound through `resolve_unit_suffix(bound)` | **DROPPED HERE** |
| lowered obligation (`ClaimForm1`) | `lhs="elec.impedance(refclk, ..., w=0.00036)"`, `op=">="`, `rhs="45"` | NO -- `rhs` is a bare SI magnitude |
| model call (`translate._translate_si_impedance`) | `DischargeRequest(claim_kind="elec.si.microstrip_z0.lo", limit=45.0, ...)` | NO -- `limit` is a bare float |
| `Evidence` | `value_bits`/`margin_bits` (f64 bit channels) | NO -- the schema has no unit field |
| calc sheet | `value="50.1737"`, `unit=""` (pre-fix) | NO |

**The first surface that loses it is Rust `resolve_unit_suffix`**
(`crates/regolith-lower/src/claims.rs:3938`). It is not a window-only
quirk: it is applied to EVERY claim's `lhs`/`rhs` (14 call sites), so a
claim's declared threshold is SI-normalized to a bare magnitude before
Python ever sees it. `45ohm` -> `45`; the `Unit` is parsed
(`Unit::parse_expr`), used for the scale factor, and thrown away.

`demo15`/`arm_a6`'s `base_bolts` is the CONTRAST case and it explains why
that sheet was already half-working: its bound (`>= 1.5`) is genuinely
dimensionless, and its Result unit (`N`) comes from `BoltedJointModel.
output_unit` -- the WO-123 model-declared-port-unit channel. That channel
covers every in-tree model but reaches NO feldspar-pack model (none of
the 32 override `output_unit`), which is exactly why every SI claim fell
through to the empty string.

### Escalation outcome (reported, not taken)

Fixing `resolve_unit_suffix` to preserve the unit token would change the
lowered obligation's text and therefore its content hash (INV-10) --
every waiver hash, acceptance ledger, and census golden in the fleet
moves. That is a genuine Rust-lowering change requiring the D239 schema
window, which is CLOSED and unspent. Per the WO's escalation clause it is
REPORTED here and left to the coordinator, not landed.

### What landed instead

`translate.si_output_unit` -- the unit read off the claim SHAPE, not its
text. `elec.impedance`/`elec.termination` are a fixed, closed SI
vocabulary (charter 35 sec. 1.2/1.3) whose output dimension is a physical
fact of the claim form itself: impedance is always ohms; every
termination sizing route resolves a resistor except the ac_shunt
capacitor leg (`part=c` -> farads). This is the SAME closed vocabulary
`si_sheet_fields` already owns for `call_name`/`geometry` -- one home,
read by both `backends.calc` (sheet `unit`) and `backends.harness_pack`
(row `units`). It is not a guessed value (D224) and not a second unit
table (AD-1).

### Acceptance

mainboard_mx `harness/expected_signals.json`, channel 0:

    {"channel": 0, "target_path": "CarrierSi.refclk", "kind": "clock",
     "quantity": "impedance", "expected": "45", "units": "ohm",
     "provenance": {"kind": "calc_sheet",
       "ref": "local-blake3:0ca720a73531a50b...", "reason": ""},
     "note": ""}

`harness/bringup.md` line 11:

    - Probe TP0 / channel 0 (connector pin 1), target `CarrierSi.refclk`
      (clock): expect 45 ohm (calc sheet `local-blake3:0ca720a73531...`).
      [REGOLITH-TAP ch=0 target=CarrierSi.refclk]

All three mainboard SI calc sheets now carry `ohm` (`refclk_rs` 28 ohm,
`refclk_z0.hi`/`.lo` 50.1737 ohm). arm_a6's `base_bolts` sheet prints
`14875.2 N` with every Inputs row united (`f_preload 14900 N`,
`k_bolt 6.3e8 N/m`, ...).

### Rows that legitimately still have no reachable unit

Five of mainboard_mx's six taps -- channels 1-4 (`Rail1V1/1V8/3V3/5V.out`)
and channel 5 (`CarrierSi.usb_dp_dm`). These are NOT unit failures: they
are `provenance.kind == "claim"` rows, i.e. their obligations never
DISCHARGED (the rails defer `no_model`; usb_dp_dm defers
`si_differential_unexposed`, feldspar's own named cut). WO-126's rule is
unchanged and correct here: no discharge means no verified number, unit
or not. Zero rows now carry `unit_unresolved`.

### Census equality (D206/D220.1)

No discharge added, no verdict moved. Post-change audit summaries match
the COMMITTED `tests/golden/data/fleet_census.json` field for field:

| project | obligations | discharged | accepted_deviation | violated |
|---------|-------------|------------|--------------------|----------|
| mainboard_mx | 39 | 3 | 36 | 0 |
| arm_a6 | 54 | 10 | 34 | 0 |

Locked by `test_units_on_the_evidence_surface_move_no_verdict`.
