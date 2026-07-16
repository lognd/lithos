# WO-141 -- feldspar fluids pack bridge, LITHOS HALF (D258.4/F159)

Status: open (Depends: WO-139; the feldspar half is a SEPARATE,
  ALREADY-DISPATCHED work order in the feldspar repo, dispatched
  2026-07-16 ahead of the D256 window per D258 ruling 4 -- this WO
  is lithos-side wiring ONLY. Do not re-implement or re-plan the
  feldspar-side solver; it exists.)
Language: Python (lithos orchestrator/harness: claim-discharge
  wiring + integration tests). No Rust, no feldspar-repo changes.
Spec: F159 (feldspar's fluids core -- Colebrook/Haaland-seeded,
  laminar 64/Re, Darcy dp, K-factor dp, series/parallel composition,
  pump operating point, NPSHa, Joukowsky, and a Hardy-Cross network
  solver that ALREADY consumes the lithos `FlownetPayload` via
  `PayloadResolver` -- is complete and shipped
  `feldspar:python/feldspar/fluids/network.py`, but NOT ONE fluids
  model is wrapped into the regolith pack,
  `feldspar:python/feldspar/pack/__init__.py:21-49`; this is the
  single highest-leverage gap the recon found); AD-19 (external
  solver integration -- the plugin/pack seam this bridge rides);
  INV-28 evidence attribution (`docs/spec/regolith/
  13-invariants.md:391`: evidence carries pack name+version, never
  bare); `docs/spec/toolchain/20-solver-abstraction.md` sec. 7
  (feldspar-recorded asks) and sec. 8 (pack contract v2, WO-30); the
  F126.1 waiver family this WO burns (`fluids.mdot`,
  `fluids.flow_imbalance` across the fleet, named at
  `thermosiphon.fluo:94-96` and `hydronics.fluo:66`).

## Goal

The Hardy-Cross network solver that already exists in feldspar and
already consumes the lithos `FlownetPayload` becomes reachable from a
lithos build: `fluids.mdot`, `fluids.flow_imbalance`, and multi-path
`fluids.dp` discharge through a real regolith Model when the feldspar
pack is installed, and defer honestly when it is not.

## Deliverables (lithos half only -- the feldspar solver is done)

1. Regolith Model wrapper wiring: the harness/orchestrator side that
   discovers the feldspar pack's exposed fluids models (via the
   existing AD-19 pack discovery mechanism -- no new discovery
   mechanism), routes `fluids.mdot`, `fluids.flow_imbalance`, and
   multi-path `fluids.dp` claim kinds to them when the pack is
   present, and reads back signed evidence.
2. Claim-discharge routing: confirm/extend the existing claim-form ->
   model dispatch (WO-109's routing machinery) so these three claim
   kinds are ELIGIBLE for pack-backed discharge, not just the
   existing lithos built-ins.
3. Integration tests (Python-level, no subprocess) proving: (a) with
   the feldspar pack installed, a `FlownetPayload`-carrying fixture's
   `fluids.mdot`/`flow_imbalance` claims discharge with pack evidence
   attached; (b) without the pack installed, the SAME fixture defers
   with an honest `no_model` result -- never a silent fallback to a
   lesser tier.
4. Evidence attribution: every pack-backed discharge's evidence
   record carries the pack's name and version (INV-28/AD-19), visible
   on the calc sheet.
5. Burn the F126.1 waiver family: at least the `thermosiphon.fluo:
   94-96` and `hydronics.fluo:66` waivers convert to real discharges
   when the pack is installed (or, if small_office's supply-riser
   chain is not yet closed by WO-138/139/140 at this WO's dispatch
   time, name the exact residual and hand it to WO-144).

## Out of scope

- Any change to `feldspar:python/feldspar/fluids/network.py` or any
  other feldspar-repo file -- that work is dispatched separately in
  the feldspar repo; this WO consumes its output.
- The natural-circulation/buoyancy extension for thermosiphon-style
  loops (density-difference driving head) -- named in the recon as
  its own future feldspar slice (F159/D258 sec. 1.5 gap d3), NOT
  in-scope here.
- Any new pack-discovery or plugin-kind mechanism -- this rides the
  existing AD-19 seam exactly as it stands.

## Acceptance

- `uv run pytest tests/harness/ -k fluids_pack -q` (or the
  equivalent new integration-test path this WO adds) green, covering
  both the pack-installed and pack-absent cases.
- A build of a fixture with the feldspar pack installed shows
  `fluids.mdot`/`fluids.flow_imbalance` discharged, with the calc
  sheet's evidence naming the feldspar pack + version:
  `regolith build --release <fixture>` then grep the calc-book output
  for the pack name and a version string.
- The SAME fixture without the pack installed shows an honest
  `no_model` deferral for the same claims -- no default value, no
  silent tier substitution: a test asserts this directly.
- At least one F126.1-named waiver (thermosiphon or hydronics)
  converts to a real discharge, or the close-out states the exact
  residual blocking it and hands it to WO-144's dependency list.
- `make check` green (lithos side); no feldspar-repo files touched
  (`git diff --stat` shows only lithos paths).

## Escalation

If the pack's exposed model signature does not match what the claim
form expects (payload shape, unit convention), escalate to the
coordinator rather than reshaping either side unilaterally -- the
pack contract (sec. 8 of 20-solver-abstraction.md) is the shared
interface and edits to it are a cross-repo decision.
