# WO-150 -- no bare dimensioned values in artifacts: enforcement by unreachability (D262)

Status: open (Depends: the D256 hash window, merged -- this WO builds
  on the repaired unit channel D256 lands; PRECEDES WO-143, the Moody
  calc-sheet figure, which must render its quantities through THIS
  WO's enforced interfaces rather than being migrated to them later)
Language: Rust (`regolith-qty` Qty/Interval types already exist;
  `regolith-diag`/renderer signature changes to require them) +
  Python (the sweep-half health check, `tools/health/` or
  `tools/stdlib/organization.py`-adjacent, coordinator's placement
  call).
Spec: D262 (`docs/workflow/design-log/2026-07-16-cycle-37.md`: the
  owner directive -- "no dumb mistakes should EVER be possible to
  make" -- and the two-half ruling: STRUCTURAL (every
  artifact-rendering interface that accepts a dimensioned value
  accepts a unit-carrying quantity type, never a bare
  float-plus-hope; genuinely dimensionless values pass an EXPLICIT
  dimensionless unit, never an absent one) + SWEEP (a
  health-consistency sweep over emitted artifacts flagging
  dimensioned-looking bare numerals, report-only at first landing,
  promoted to error only once the fleet is clean, per the F154
  lesson: a gate promoted before it is satisfiable gets waived); F156
  (the observed bare-value family -- `resolve_unit_suffix` discarding
  the unit token -- whose ROOT FIX is the D256 hash window itself;
  this WO is the SECOND half, making bare-ness structurally
  impossible rather than currently-absent); D246 ("cannot forge a
  pass" unreachability doctrine, the same shape this WO applies to
  units); D257 ruling 2 (uncited values unrepresentable -- the
  precedent this WO's structural half follows for dimensioned
  values); `crates/regolith-lower/src/claims/comparison.rs:378`
  (`resolve_unit_suffix`, the repaired channel this WO's structural
  half builds on); charter 41 rule 6 (axis-unit discipline, already
  required for the ONE renderer -- this WO generalizes the same
  discipline to every artifact-rendering interface, not just chart
  axes).

## Goal

Every interface across the toolchain that renders a dimensioned
value into an artifact (calc sheets, bring-up packs, drawings, BOM
views) is typed so that passing a bare float where a unit-carrying
quantity is required is a compile-time/constructor error, not a
runtime possibility -- proven both by the type-level refusal
(structural half) and by a sweep over the real emitted corpus finding
zero remaining bare-looking numerals it can detect (sweep half) --
and the guarantee is recorded in the invariant ledger with its proof
argument in the same change.

## Deliverables

1. STRUCTURAL HALF: audit every artifact-rendering interface
   (calc-sheet renderer, bring-up/harness pack emitter, drawing
   backend, BOM view backend -- the ONE renderer per AD-7/charter 41)
   and change any signature that currently accepts a bare
   `f64`/`float` for a dimensioned quantity to accept a
   `regolith-qty` `Qty`/`Interval` (or the schema-mirror equivalent
   on the Python side) instead. Genuinely dimensionless quantities
   (counts, ratios, dimensionless coefficients) pass an EXPLICIT
   dimensionless unit marker, never an absent/omitted unit field --
   absence stops being an expressible state at all.
2. SWEEP HALF: a health-consistency sweep (new check, coordinator's
   placement call: `tools/health/` sibling to the existing
   consistency checks, or a new mode of
   `tools/stdlib/organization.py`) that scans emitted artifacts
   (calc sheets, bring-up packs, drawings, BOM views) for
   dimensioned-looking bare numerals the type system cannot reach
   (prose strings, freeform text fields) and flags them. REPORT-ONLY
   at first landing -- per the F154 lesson (a gate promoted before it
   is satisfiable is a gate that gets waived), this sweep does NOT
   fail `make check` on its first landing; promotion to a hard error
   is a LATER, separate decision made once the fleet corpus is
   observed clean under it.
3. Invariant-ledger entry: draft a new invariant (`INV-34`, the next
   free number after `INV-33` RESERVED per
   `docs/spec/regolith/13-invariants.md:615` -- confirm the number is
   still free at implementation time and use the coordinator-assigned
   number if it has moved) in `docs/spec/regolith/13-invariants.md`,
   with a PROOF ARGUMENT composed of: (a) the structural half's
   unreachability (a bare float cannot reach a rendering interface
   because the interface's own type refuses it -- the same shape as
   INV-28's evidence-attribution proof and D257's uncited-value
   proof), and (b) the sweep half's empirical evidence (the report-only
   sweep's clean-corpus result, once obtained, as the discharge
   evidence for the surfaces the type system cannot reach). This
   ledger entry landing in the SAME change as the code is itself an
   acceptance criterion, not a follow-up.
4. Seam coordination notes (per D262 ruling 4, do not re-implement,
   only confirm compatibility): the signal-design axis-unit
   discipline (D260, WO-151/152) already carries the same discipline
   for authored waveforms; WO-145's `Cited` models carry units inside
   cited values already; WO-147's `.rgp` schema declares `mm`
   explicitly already. This WO does not touch those files; it
   confirms (by test or by reading) that none of them regress once
   the structural half's renderer-signature changes land.

## Out of scope

- WO-143's Moody-figure implementation itself (that WO consumes
  this one's enforced interfaces; it is not touched here beyond
  confirming its dependency ordering).
- Any change to `regolith-qty`'s core `Qty`/`Interval` types
  themselves -- they already exist; this WO changes CALLERS
  (rendering interfaces) to require them, not the types.
- Promoting the sweep from report-only to error -- named explicitly
  as a LATER decision, not this WO's acceptance bar.
- Re-fixing `resolve_unit_suffix` itself -- that is D256's own
  window, already executing/executed separately.

## Acceptance

- Every artifact-rendering interface identified in the audit has a
  unit-carrying signature: a reviewer-checkable grep shows no
  remaining bare `f64`/`float` parameter named for a dimensioned
  quantity in the renderer entry points
  (`grep -rn 'fn render' crates/regolith-diag/src crates/*/src` or
  the project's equivalent renderer-entry-point search, manually
  reviewed against the audit list from deliverable 1).
- A negative test proves the refusal is real: attempting to construct
  a bare-float call site against the changed signature is a
  compile error (Rust) or a constructor/type error (Python) --
  `cargo build` / `uv run pytest -k unit_enforcement -q` demonstrates
  the refusal, not merely documents it.
- The sweep runs and reports (report-only, non-gating):
  `uv run python -m tools.health.<sweep-name> --report` (or the
  chosen entry point) exits 0 regardless of findings at first
  landing, with findings printed, not silently swallowed.
- `docs/spec/regolith/13-invariants.md` has the new `INV-34` (or
  coordinator-reassigned number) entry with a proof argument
  referencing both halves, landed in this same change.
- `make check` green with the sweep wired in as report-only (does not
  fail the gate).
- WO-143's dependency line names this WO as a precedent it builds on
  (checkable in WO-143's own file once both exist in the same
  cycle's queue).

## Escalation

If the structural-half audit finds a rendering interface whose
existing callers cannot be migrated without a wider refactor than a
signature change (e.g. a call site that generates dimensioned text
procedurally with no single conversion point), name that surface as a
SWEEP-HALF-ONLY residual in the close-out rather than silently
skipping it or forcing an oversized refactor into this WO's scope.
