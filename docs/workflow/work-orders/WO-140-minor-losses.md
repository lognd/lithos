# WO-140 -- minor losses: Hooper/Darby/Borda-Carnot records + component-dp chain (D258.2/F158)

Status: open (Depends: WO-139)
Language: records (TOML) + Python (harness built-in extension).
Spec: F158 (no K-factor/fitting-loss data exists anywhere in the
  tree despite `stdlib/README.md:54` implying it does; the F132.3
  refusal at `examples/flagships/espresso_machine/
  brew_water.fluo:169`, "needs the component-dp record chain",
  which this WO exists to close); D258 ruling 2 (LICENSING HONESTY:
  Crane TP-410 and Idelchik are proprietary commercial publications;
  bulk transcription of their K/f_T tables is LICENSE-BLOCKED pending
  an explicit owner decision, exactly as the DigiKey question was
  handled -- OUT OF SCOPE here, see below; Hooper 2-K, Darby 3-K, and
  Borda-Carnot textbook geometry laws cover the demo set at the same
  tier=community transcription posture the repo already applies to
  NEC tables); D250 (citation discipline); AD-37 ruling 1 (closed
  form + record split, same as WO-139); `docs/spec/fluorite/
  03-lowering.md` sec. 2 (`FlownetPayload` per-edge params/component
  binding); `feldspar:crates/feldspar-library/src/fluids/
  incompressible.rs:108` (the existing K*rho*v^2/2 minor-loss form,
  the WO-94-pattern twin this WO's lithos side follows).

## Goal

A path's pressure drop can include real fitting and component losses
-- elbows, tees, valves, entrances, exits, expansions, contractions --
each K value cited, so the F132.3 flowmeter/check-valve refusal
converts to a real discharge or a strictly narrower named residual.

## Deliverables

1. `stdlib/std.fluid/records/fittings.toml`:
   - Hooper 2-K constants (Hooper, W. B., "The two-K method predicts
     head losses in pipe fittings", Chemical Engineering, Aug 24
     1981, pp. 96-100): elbows, tees, valves as (K1, K_inf) pairs.
   - Darby 3-K constants (Darby, R., Chemical Engineering, July 1999;
     consolidated in Darby, Chemical Engineering Fluid Mechanics, 2nd
     ed., 2001, Table 7-3): the modern re-fit adding size scaling.
   - Geometry closed-form K laws with textbook lineage (White, Fluid
     Mechanics, 8th ed., Table 6.5 / sec. 6.9): Borda-Carnot sudden
     expansion K = (1 - A1/A2)^2, sudden contraction, sharp entrance
     K ~ 0.5, exit K = 1.0.
   - Each row's `evidence` table cites method/trust_tier/reference
     per the D250/D258 shape (e.g. `reference = "Hooper, Chem. Eng.,
     1981-08-24, pp. 96-100, 2-K table"`).
2. Extend the `fluids.dp` input chain so a path's total dp = Darcy
   segment terms (WO-139) + sum(K_i)*rho*v^2/2 over its declared
   fittings + declared component `crack_dp` (valves etc., using the
   Cv rows that already exist at `stdlib/std.fluid/records/
   components.toml:19`, converted to an equivalent K/dp). This is a
   chain WIDENING: existing single-segment `fluids.dp` fixtures keep
   discharging unchanged when they declare no fittings.
3. Byte-check test against feldspar's existing
   `dp_minor = K*rho*v^2/2` form (`incompressible.rs:108`) -- same
   WO-94 both-sides precedent as WO-139.
4. Convert the F132.3 refusal at `brew_water.fluo:169` (flowmeter +
   check-valve span) to a real discharge, OR to a demonstrably
   NARROWER named residual (state exactly what remains undischarged
   and why).

## Out of scope (owner-gated, D258 ruling 2)

- Crane TP-410 K/f_T(L/D) bulk tables -- proprietary commercial
  publication, licensed sale at tp410.com; NO bulk transcription
  without an explicit owner purchase/licensing decision. The existing
  single Crane-cited value (`components.toml:32`, sharp-edged orifice
  Cd=0.61) stays as-is; do not add more Crane-sourced rows.
- Idelchik, Handbook of Hydraulic Resistance -- same LICENSE-BLOCKED-
  BULK posture; not needed given Hooper/Darby cover the demo set.
- Filter/strainer dp curves beyond the existing honest "not
  published, omitted" note (`components.toml:22`) -- stays a named
  absence unless a manufacturer publishes the curve; no action here
  beyond keeping the note.

## Acceptance

- `stdlib/std.fluid/records/fittings.toml` exists with Hooper, Darby,
  and Borda-Carnot-family rows, each with a non-empty `evidence`
  table: `grep -L 'evidence' stdlib/std.fluid/records/fittings.toml`
  returns empty.
- `uv run python -m tools.stdlib.organization --check
  prefix|one_family|citations` passes, zero new issues.
- `brew_water.fluo:169`'s D224.1 refusal either discharges (grep the
  build report / calc book for a resolved verdict on that claim) or
  the close-out states the exact narrower residual in prose,
  cross-referenced by claim id.
- The byte-check test passes: `uv run pytest <new test path> -q`.
- Zero Crane/Idelchik rows added beyond the pre-existing single
  orifice citation: `grep -c 'Crane\|Idelchik' stdlib/std.fluid/records/fittings.toml` returns 0.
- `make check` green.

## Escalation

If the demo (WO-144) turns out to need a Crane-sourced K value to
close, escalate to the owner as a licensing decision -- do not
transcribe from Crane TP-410 or Idelchik under any framing (a
"reference-only" citation without the value is fine; the value
itself is blocked).
