# WO-129 -- The engineer-injection channel (D243/AD-40, charter 42 secs. 1-5, 8)

Status: cut (D253, 2026-07-15). PARKED, not shipped, not abandoned.

  Why: F150 established that the channel landed by WO-129A was INERT --
  `apply_overrides_to_rows` had zero call sites, `orchestrate.py` never
  read the ledger, and no build or ship path consumed it. The "safety
  core" was a library + a CLI + unit tests; nothing in the real pipeline
  ever ran it. INV-33's green tests therefore proved a property of a pure
  function while reading, in the invariant ledger, as though the pipeline
  were protected -- the most dangerous artifact this project can produce
  (D252.3, D226).

  Owner directive D253: the engineer-injection design needs more thought,
  and configuration through a GUI is AESTHETIC ONLY (moving a component
  placement is an engineering change; rearranging a BDF block is a
  picture). So the whole channel is REMOVED from master and PRESERVED on
  the pushed branch `experimental/injection-channel`: the ledger, target
  resolution, the `engineer_override` cause, the `regolith override`
  verbs, and INV-33. Because the channel was inert, removing it changed
  no behavior.

  WO-129B was CANCELLED mid-flight (its drag-path deliverable was already
  broken at the seam, F149). INV-33 is withdrawn and its number RESERVED
  (regolith/13-invariants.md) -- never reused. Charter 42's secs. 3, 4, 5,
  7 and AD-40 are banner-marked PARKED in place rather than deleted; the
  thinking is kept for the rethink. If this is ever revived, it comes back
  with a proof that runs the REAL pipeline and a NEW invariant number.

Language: Python (orchestrator value sources, optimizer seam, CLI,
  gate/parity/acceptance reporting) + Rust ONLY if a value source
  cannot carry an override cause without a lowering change
  (investigate first; report before touching crates). No schema bump
  without coordinator adjudication (D239/D225).
Spec: charter 42 secs. 1-5 + 8 (NORMATIVE); AD-40; D243; D206/
  D220.1 (verdict math untouchable -- this WO's central constraint);
  INV-30 (optimization attribution); WO-55/56/57 (the optimizer and
  its choice points/causes); WO-98 (acceptance ledger); WO-63 (the
  parity report); WO-114 (calc-book audit index);
  regolith/13-invariants.md (INV-33 lands HERE with its proof
  argument, in the same change as its enforcing tests).

## Goal

A high-skill engineer can inject a decision at any intermediate step
-- pin a dimension, choose a component, supersede what the optimizer
picked, move a placement -- through ONE audited, diffable channel,
and the toolchain re-derives every obligation from that input
exactly as if it had been hand-authored. An injection can make a
design fail. It can never make a failing design pass.

## Deliverables

1. Override ledger (`overrides.toml`, charter 42 sec. 2): pydantic
   v2 frozen models, one home for the format; `author` + `reason`
   REQUIRED (missing -> constructive diagnostic, never a default);
   ledger content hash enters the build inputs (reproducibility,
   INV-10).
2. Target resolution against the SAME surfaces the census and
   optimizer read (choice points, bounded/minimize slots, sketch
   dimensions, section selects, placements, `@hint(...)`). An
   unresolvable target is a diagnostic naming the nearest valid
   paths -- never a silent no-op. Dotted `design.subject.slot` paths.
   THE D246 BOUNDARY IS PART OF THIS DELIVERABLE: a target naming
   claim semantics (`require`, `forall`, the transient/manufacturable
   claim forms, `all`, `during`/`within`/`until`, `event`/`mask`) or
   the evidence ladder (`trust:`, `by analysis|catalog|test`,
   `model=`, `assume!`, `todo!`, `waive`, `sf=`, `scatter_factor=`)
   is REFUSED with a constructive diagnostic telling the author to
   edit the source -- see charter 42 sec. 1a for why this is what
   makes INV-33 provable by construction.
3. Value-source integration: an override enters BEFORE lowering with
   `cause: engineer_override(author, reason)`, outranking
   `optimize(...)` in the provenance ladder. Obligations re-derive
   from it. No override may reach an evidence value, a margin, a
   verdict, or a waiver -- that is INV-33 and it is enforced, not
   assumed.
4. Optimizer interaction (charter 42 sec. 3): `mode = "pin"`
   (default) REMOVES the variable from the search and records that
   removal; `mode = "seed"` keeps it searchable from that start
   point. The optimization trace records the supersession (INV-30
   attribution holds).
5. Reporting -- an override is NEVER silent. Every one appears in:
   the parity report (`ship --explain`) as an `optimization_removed`
   / `input_overridden` row with author + reason; the shipped
   acceptance ledger; the calc-book audit index on every obligation
   whose inputs it touched.
6. CLI (charter 42 sec. 5, the ONE writer of the ledger):
   `regolith override list|set|clear|explain [--json]`. `explain`
   states what the override supersedes and what it costs (which
   variable left the search, which obligations re-derive).
7. INV-33 in `docs/spec/regolith/13-invariants.md` WITH its proof
   argument, in the SAME change as the enforcing tests: an override
   that satisfies a claim discharges it honestly; one that violates
   a claim VIOLATES it and the gate refuses; one on a waived claim
   neither un-waives nor re-waives it.
8. Guide `31-injecting-decisions.md`: when to inject, the ledger
   format, pin vs seed, what the gate will and will not let you do,
   worked from a real fleet example (printer_k1's carriage span or
   arm_a6's pinned section).

## Acceptance

- A real fleet override end to end: pin a slot the optimizer
  searched, ship, and see the value honored, the search recorded as
  removed with author+reason, and the obligations re-derived.
- The refusal case PROVEN: an override that violates a claim yields
  VIOLATED and a refused gate (test asserts the gate cannot be
  talked into passing).
- Unexplained override (no author/reason) refused with a
  constructive diagnostic.
- Census/verdict math untouched when no override is present (byte
  equality); determinism per override set.
- `make check` + `make health` green.

## Escalation

If a value source genuinely cannot carry the override cause without
a Rust/lowering change, STOP and report the trace -- the coordinator
adjudicates (D239 window is CLOSED and unspent; opening it is a
coordinator decision, not an agent one).
