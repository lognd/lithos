# WO-92 -- Refinement-bound extraction + comparator-after-call parsing

Status: in-progress (deliverable 2 done; deliverable 1 escalated -- see
  the close-out ledger and design-log F116)

## Close-out ledger (cycle 33)

Deliverable 1 (conformance windows) -- ESCALATED, no fabrication. The
premise ("nothing in Rust emits the windows") was refuted on
verification: WO-26 D104 (commit 3d96812, two days before this WO was
drafted) already landed the both-scalar-bounds extraction end to end
(`conformance_windows` -> `given.loads` -> `_translate_conformance`,
both unit-tested). It fires on ZERO corpus bindings because the
flagships express conformance via generic-parameter instantiation
(`impl HeaterDrive<watts=50W>` vs `power: <= watts`, impl body
`= todo!`), geometric/role/`derived` promises, and whole-module
import/select edges -- none a both-scalar-bound refinement pair.
Baseline == post-change: printer_k1 54, uav_talon 20 residual
`conformance_windows_unresolved`, ALL genuinely unbounded. Spot-check
of three: (a) `impl:HeaterDrive` -- generic instantiation, no impl-side
scalar bound; (b) `impl:BuildPlatformMount` -- geometric-role interface,
no scalar comparator promise; (c) `import:std.mech.sheet` -- a
whole-module import edge with no scalar refinement. Inventing a window
for any of these violates INV-13/26 and this WO's own "never invent a
window" law, so deliverable 1 is escalated to F116 (OPEN owner
question: does generic instantiation count as a conformance window, and
with what second bound?). WO-12's recorded cut is annotated CLOSED in
mechanism there.

Deliverable 2 (comparator-after-call) -- DONE, structurally. The gap is
fluorite-local: only `regolith-lower::claims::push_fluid_obligation`
bypasses `split_general_comparison` and emits `op="require"` with the
comparator buried after the `fluids.*(...)` call. Routed that path
through `split_general_comparison` so the obligation carries a real
comparator op + the call as LHS; `fluids.mdot(duct) >= 0.0003` now
lowers to a scalar request instead of `unsupported_op`. Chose the
STRUCTURAL fix over extending the Python `_split_comparator` because a
balanced-paren `_split_comparator` would also fire on computed-field
projections (`max(wall_T) < 800K`) and break WO-33 D98's deliberate
`unsupported_op` deferral of them. Line 838 (the calcite frame path)
is WO-85's area and was left untouched.

Before/after (deferral histogram, both flagships):
- printer_k1: conformance_windows_unresolved 54 -> 54 (genuine);
  unsupported_op 9 -> 8; unresolved_limit 3 -> 3; translate-lowered
  2 -> 3. The newly-lowered `flow` claim discharges `no_model` (no
  fluid harness model yet) -- no new VIOLATED verdict.
- uav_talon: unchanged (no fluorite claims); conformance 20, unsupported
  5, unresolved_limit 1 -- all genuinely unbounded / out of scope
  (multi-line-truncated or `manufacturable(...)`).

Golden churn: four fluorite-bearing deferral goldens
(espresso_machine, cnc_router, dune_buggy, small_office); nine fluid
claims move deferred(`unsupported_op`) -> lowered, zero regressions,
zero new VIOLATED verdicts.

Language: Rust (regolith-lower/-ir/-oblig) + Python (translate)
Spec: F115 (this cycle's census); WO-12 (contract IR -- the
  recorded refinement-bound-extraction cut this closes);
  regolith/13 INV-13/INV-26 (the implicit `by spec` conformance
  guarantee); translate.py `_translate_conformance` (the consumer,
  already landed and tested -- it names the exact fields it wants);
  WO-48 close-out (`_split_comparator` gap).

## Goal

The two deferral clusters that gate more fleet discharges than the
rest of the queue combined (F115):

1. `conformance_windows_unresolved`: the core emits one conformance
   obligation per `impl`/extern/import binding (INV-13/26) but
   never threads the two refinement windows into `given.loads`.
   The Python consumer (`_translate_conformance`) already lowers
   `conformance_sense` / `spec_bound` / `impl_bound` fields when
   present -- the WHOLE gap is producing them in Rust when both the
   upper contract and the lower realization carry a resolved
   comparator bound. printer_k1 alone has 54 such deferrals.
2. `unsupported_op`: a frame/claim predicate whose comparator sits
   after a call expression defeats the translate-side
   `_split_comparator` string parse. Lower the comparator
   structurally (the CST knows where the comparison node is) OR
   extend the split to balanced-paren awareness -- prefer the
   structural fix if the obligation payload already carries enough
   CST-derived shape; escalate if it would need a schema change.

## Deliverables

1. Rust window extraction: for each conformance obligation, when
   BOTH sides' bounds resolved during lowering, emit
   `conformance_sense`/`spec_bound`/`impl_bound` into
   `given.loads` (text expressions, the existing channel -- NO
   schema change; the consumer parses text). When either side is
   genuinely unbounded, the existing honest deferral stands --
   never invent a window (the docstring's own law).
2. The comparator fix (structural preferred, per above).
3. Tests: Rust unit tests per extraction case (upper-only,
   lower-only, both, neither; interval vs point bounds); the
   printer_k1/uav_talon release builds as the integration net --
   record before/after discharge counts in the WO ledger; goldens/
   deferral corpus regenerated (expect large honest churn: dozens
   of obligations move from deferred to real verdicts, some may
   VIOLATE -- a violation is a correct outcome, do not tune it
   away, but DO report any violation loudly in your close-out so
   the corpus authors can inspect).
4. Docs: WO-12's recorded cut annotated closed; guide mention if
   any user-visible behavior text exists for conformance claims.

## Acceptance criteria

- printer_k1 `conformance_windows_unresolved` count drops to only
  the genuinely-unbounded bindings (report the residual number and
  spot-check three of them by reading the source bindings).
- No fabricated windows: a binding without both bounds still
  defers with the existing reason.
- No SCHEMA_VERSION bump (the given.loads text channel is the
  contract; if you conclude a bump is genuinely needed, STOP and
  escalate -- WO-85 owns this cycle's bump train).
- `make check` green.

## Dependencies

None hard. Serializes with WO-85 at integration if both touch
regolith-lower's pass driver (WO-85 is in flight -- rebase over
whatever it lands; your extraction rides claims/contract lowering,
not the frame pass, so overlap should be small).
