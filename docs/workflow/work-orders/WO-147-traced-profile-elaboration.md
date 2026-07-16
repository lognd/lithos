# WO-147 -- `.rgp` schema + extern-profile elaboration; THE cycle-37 SCHEMA_VERSION bump (D261.4)

Status: open (Depends: WO-146 [ratified spec], the D256 hash window
  MUST have merged -- D256's own law: no other lithos code work
  lands until it closes, and this WO touches lowering + goldens.
  This WO OWNS the cycle-37 SCHEMA_VERSION bump: D211 discipline,
  one bump, one owner -- any other cycle-37 lithos WO that appears
  to need a schema change routes its passenger through THIS bump,
  see the flownet-payload note below, rather than opening a second
  bump.)
Language: Rust (`regolith-syntax` schemars types, `regolith-lower`
  elaboration pass, `regolith-diag` new diagnostic codes). No Python
  in this WO (consumption is WO-148).
Spec: WO-146's ratified spec section (the `.rgp` schema, calibration
  block, provenance requirements, accuracy/consistency diagnostic
  rules -- implement exactly what it specifies, do not re-derive);
  `docs/spec/hematite/02-language.md:155-159` and
  `08-lowering-architecture.md` sec. 4 (the extern seam this
  elaborates -- `extern` is already tokenized,
  `crates/regolith-syntax/src/syntax_kind.rs:848`, and the extern
  edge already gets one conformance obligation per INV-13,
  `crates/regolith-lower/src/claims/mod.rs:301-307`; NO
  profile-extern elaboration exists yet -- this WO is that
  elaboration); D211 (schema-bump discipline: one bump per cycle,
  one owning WO, `make schema` regenerates the committed Python
  mirror in the SAME change); `scratch_recon_graphite_cad.md` sec. 6
  (store raw in image space, derive mm at lowering time,
  deterministically, per INV-10 -- the fit itself NEVER runs inside
  the compiler, only closed-form application of already-fitted
  parameters); INV-9 (outward-rounded bracketing -- out-of-domain
  and tolerance-vs-accuracy-bound checks apply this posture).

## Goal

A `.rgp` file is a first-class schemars-single-sourced payload;
`profile X: extern("path.rgp", rgp)` elaborates deterministically
into the existing resolved-outline sketch-layer shape
(`resolve_extrusion_outline`'s output shape, `python/regolith/
compiler.py:335-348` / `programs.py:482-516`), with every
accuracy/consistency/provenance check WO-146 specified emitting a
real diagnostic with an explain entry, and this is the ONE schema
bump cycle 37 lands.

## Deliverables

1. schemars-derived Rust types for the `.rgp` payload (geometry:
   vertices/arcs/hole loops/datums in image space; `[calibration]`
   block for all three rungs -- `scale`/`homography`/
   `homography+radial`, WO-147 accepts and applies all three even
   though rung C's FIT (WO-G14) is v1.1, application is closed-form
   arithmetic regardless of which rung produced the parameters;
   `[provenance]` per WO-146's ratified schema), landed in
   `regolith-syntax` alongside the existing extern-format registry
   (the ONE place extension strings live, per CLAUDE.md tripwire).
2. Extern-profile elaboration in `regolith-lower`: parses `.rgp`,
   applies the recorded calibration transform deterministically
   (mm_per_px scale, or the 3x3 homography, or homography+radial
   distortion correction -- closed-form in every case, no iterative
   solve inside the compiler) to the image-space trace, producing
   the sketch-layer/resolved-outline payload the realizer already
   consumes; runs the full static checks (closed loop, unit sanity,
   one-level nesting depth, arc validity, provenance completeness).
3. New diagnostic codes + `regolith explain` entries (WO-131 law:
   every diagnostic has an explain entry) for: tolerance tighter
   than `accuracy_bound_mm`; `accuracy_bound_mm < residual_max_mm`;
   `capture_kind = photo` with `model = scale`; missing/incomplete
   provenance fields.
4. `make schema` regeneration: the committed Python mirror under
   `python/regolith/_schema/` updated in this SAME change (CI's
   `schema-check` diffs against the committed file).
5. The cycle-37 SCHEMA_VERSION bump itself, landed here and ONLY
   here -- see the flownet-payload passenger note below for the one
   other candidate this bump must adjudicate.
6. Rust unit tests: valid `.rgp` fixtures elaborate to the expected
   resolved outline for each calibration rung; each new diagnostic
   fires on its designed negative fixture; INV-13's extern
   conformance obligation is exercised end to end for `rgp` the same
   way it already is for `dxf`.

### Schema-bump passenger: the FlownetPayload/DischargeRequest claim-target gap (escalation carried from WO-141)

WO-141 (the feldspar fluids pack bridge, lithos half) surfaced a
real schema gap while wiring claim-discharge routing: `FlownetPayload`
and `DischargeRequest` have no claim-target field -- there is no way
to say WHICH claim (or which role within a multi-path network) a
given discharge result answers, so today's convention is a 0.0/1.0
presence-flag direction encoding folded into an existing numeric
field. This strains the Unambiguous-first mantra (a flag value doing
double duty as a direction AND a presence signal is exactly the kind
of "two meanings, one representation" the project's naming/schema
discipline forbids elsewhere). Because D211 says one bump, one
owner, and this WO already owns the cycle-37 bump, THIS is where
that gap gets adjudicated:

- At implementation time, evaluate folding a proper `claim_target:
  ClaimRef` (or equivalent role/target field) into `FlownetPayload`/
  `DischargeRequest` as part of this bump, replacing the presence-flag
  convention, OR explicitly decline with a recorded reason if the
  fold turns out to be larger than a schema-bump passenger should be
  (in which case it becomes its own future-cycle WO, named in this
  WO's close-out, not silently dropped).
- This is a DECISION FOR IMPLEMENTATION TIME, not resolved by this
  document -- the WO body's job is to guarantee the question rides
  the bump instead of being missed or requiring a second bump later.
  Do not implement WO-141's lithos-half claim-discharge wiring against
  the OLD presence-flag shape if this WO's bump has already landed a
  replacement; coordinate ordering with WO-141 at dispatch time if
  both are in flight together.

## Out of scope

- Python realizer/artifact-index/citation consumption of the
  elaborated payload -- WO-148.
- Native-walk fitting / promotion-surface extension to non-cardinal
  lines -- WO-149 (v1.5, unscheduled).
- Any graphite-side code.
- Re-deriving the calibration math itself (the fit) -- WO-G11/G14
  own the fit; this WO only APPLIES already-fitted parameters,
  closed-form.
- Any other schema-bump candidate not named above -- if a second
  independent bump need surfaces during this WO, escalate rather
  than open a second bump this cycle (D211).

## Acceptance

- `cargo test -p regolith-syntax -p regolith-lower -k rgp` green,
  covering all three calibration rungs' elaboration and every new
  diagnostic's positive/negative fixture.
- `make schema` run, committed diff shows the new `.rgp` types
  mirrored into `python/regolith/_schema/`; CI's `schema-check`
  passes: `uv run python -m tools.schema_check` (or the project's
  named schema-check entry point) exits 0.
- `regolith explain <code>` prints a real entry for every new
  diagnostic code this WO adds (no placeholder text).
- `grep -rn 'SCHEMA_VERSION' crates/regolith-syntax/src` shows
  exactly one cycle-37 bump, and no other cycle-37 lithos WO's
  close-out claims a second one.
- The flownet-payload passenger question is EXPLICITLY answered in
  this WO's close-out: either the fold landed (with the new field
  named) or it is explicitly declined with a reason and a named
  future WO -- not left unaddressed.
- `make check` green.

## Escalation

If the pack contract shape WO-141 depends on (sec. 8 of
`20-solver-abstraction.md`) needs a change beyond what the
flownet-payload passenger note above scopes, escalate to the
coordinator before reshaping the shared interface unilaterally --
same rule WO-141 itself states.
