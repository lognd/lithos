# WO-63: the parity report (attribution ledger in ship --explain)

Status: done (literal source-position attribution is an escalated
AD-22 gap, not this WO's to close -- see design-log addendum D170-a
and `python/regolith/backends/parity.py`'s module docstring; every
other deliverable/acceptance criterion is met and tested)
Depends: WO-50 (--explain audit surface, landed), WO-14 (lockfile
causes), WO-55 (optimize causes/traces, landed). NO SCHEMA_VERSION
bump (WO-62 owns cycle-31's; if a report field genuinely needs
schema, escalate for folding there per the D167/D168 pattern).
Language: Python (orchestrator/backends report assembly; CLI flag
surface). Rust none expected.
Spec: docs/spec/toolchain/31-flagships.md sec. 1 (NORMATIVE),
00-architecture.md AD-33 (+ AD-30's honesty non-goal), design-log
2026-07-09-cycle-31 D170; regolith/03 sec. 2 (causes), regolith/12
(the ladder -- rungs are the assertion classes).

## Goal

`regolith ship --explain` gains the parity ledger: per subject,
every resolved value counted by provenance class, every
decision-shaped value shown engine-pinned or ladder-asserted, all
demands' discharge/deviation state, and the attention list of bare
asserted literals -- the D170 bar as ONE report, no new mechanism.

## Deliverables

1. **Provenance classifier**: over the lockfile rows + evidence
   ledger + source spans the build already emits (artifact-only
   inputs, AD-22): classes `optimize(trace)`, `dfm/drc/rule`,
   `budget`, `planner`, `derived`, `process`, `asserted(literal,
   source position)`, `assumed/waived(basis)`. Anything
   unclassifiable is a REPORT ERROR (the bar's own honesty check)
   -- loudly listed, never silently bucketed.
2. **The parity ledger** in `ship --explain` (extending the WO-50
   renderer, one report): per-subject class counts, the decision
   table (free/select/allocated values with their pins), the demand
   table (discharged/indeterminate/violated/deviation), and the
   attention list (asserted literals, sorted by subject) -- ASCII
   tables on stdout-as-data, plus `--json` structured form via
   existing report models.
3. **A `parity` gate summary line**: clean / attention(n) /
   failing(n) -- consumed by flagship phase acceptance; no new
   verdict semantics (it summarizes, never relabels; INV-2).
4. **Tests**: a fixture project covering every class; an
   unattributable-value injection proving the report error path; a
   deviation-carrying release run rendering its basis.
5. **Docs**: guide section ("reading the parity report"), charter
   cross-refs, WO ledger.

## Acceptance criteria

- On the corpus flagship-precursor designs (pillow_block,
  coolant_gallery, ebi_decode, duct_vane): report renders with zero
  unclassifiable values; ebi_decode's select shows its optimize
  pin + trace digest; duct_vane's dims show optimize causes.
- The injection test yields the loud report error; the summary line
  matches the ledger; `--json` round-trips.
- No schema bump; `make check` green; Status flipped.
