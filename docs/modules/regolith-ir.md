# regolith-ir

Contract IR: interfaces, matings, ledgers, budgets, and the L2
numeric solves. This is the implementation-free contract graph and its
checks -- the level (L2) where a system verifies with zero artifacts,
before any impl or realizer exists (WO-12). Normative source:
`docs/spec/regolith/04-contracts.md`, `docs/spec/hematite/03`,
`docs/spec/cuprite/02` sec. 4a, and `docs/spec/regolith/13-invariants.md`
(INV-7/8/10/15); this doc indexes symbols against that design rather
than restating it.

## Contract graph nodes

<a id="nodes"></a>
### `nodes`

The implementation-free contract graph itself: interfaces carry
demands and promise slots (value sources); impls bind roles as queries
and may only narrow promises, never widen them (WO-12 / conformance);
matings name sides and remove/keep DOF; system/assembly nodes carry
budgets, reserves, targets, and config variables.

<a id="conformance"></a>
### `conformance`

T1 conformance and refinement checking: role-kind by construction,
parameter match, capability-vs-demand, and the promise-refinement
direction rule. Refinement is directional -- a refined interface makes
tighter demands on itself and stronger promises to consumers, so an
impl may only narrow a promise (WO-12 acceptance); widening is
rejected. Both failure families report as `E0410` CAPABILITY_VS_DEMAND.

## Budgets and system checks

<a id="budget"></a>
### `budget`

Budget arithmetic (L2): interval sums checked against a limit at the
worst-case corner, naming the worst contributors when a budget cannot
close (E0432). Sums run in source order with outward-rounded interval
arithmetic (AD-6); `locked:` entries are fixed contributions, reserves
are held back for targets. Unresolved value sources (`derived`,
`allocated`, `free`, bare `in [...]`) have nothing to compare against
yet at L2 (AD-6/INV-20: cheaper checks run first, resolution is a
later pass).

<a id="system"></a>
### `system`

System-node L2 checks: boundary subsumption (INV-7), target/reserve
additivity (INV-8), and the system-flow ledger (INV-15). Each check is
conservative -- it flags a violation only from data the source
actually declared and leaves anything it cannot compare (non-numeric
envelope, mismatched unit, nominal reserve draw) indeterminate rather
than asserting balance.

<a id="ledger"></a>
### `ledger`

One pluggable ledger interface, two domain packs: mech runs a
DOF/Gruebler ledger, elec runs driver/load + domain-crossing + flow
ledgers (`docs/spec/hematite/03` Gruebler, `docs/spec/cuprite/02` sec.
4a). Imbalances are E0420-family diagnostics; the trait keeps both
domains' bookkeeping behind one interface so the system node runs
whichever pack its domain provides.

## Lowering payloads

<a id="feature-program"></a>
### `feature_program`

The feature/stage program IR (WO-29 deliverable 3): a schema-versioned,
`BuildPayload`-carried record of the domain feature ops a part's
`then:` claim scopes construct, with resolved scalar parameters and
their `Cause` (INV-21). Scope note: this is the subset of the Python
`FeatureProgram` schema that `regolith-lower`'s current structured
surface can populate -- scalar measures only, never sketch/profile
outline geometry (that comes from a separate, still-opaque `walk:`
surface).

<a id="block-requirement"></a>
### `block_requirement`

The binding-requirement bridge IR (WO-29 deliverable 4): a
schema-versioned record of the raw capability demands a `.cupr`
`architecture for <Computer>:` declaration projects onto its abstract
resource blocks (cuprite/05 sec. 2, regolith/10 sec. 1's interface
promises/demands rows). Split note (Q3/D90): this is the Rust half
only, emitting raw un-unit-resolved demands; the Python side derives
the numeric `min_capabilities` screen from magnetite records.

<a id="sketch"></a>
### `sketch`

The typed sketch payload (WO-51): the closure-problem data types and
the Walk -> SketchClosure promotion over D150 name labels.
Unconditional (not behind the `solve` feature) because it is payload
data carried into `BuildPayload` (schemars single-sourcing, AD-11),
while the numeric residual solve over it stays behind `solve`.
Promotion covers straight cardinal walks; anything the surface cannot
express (arcs, revolve `close via axis`, non-cardinal lines, expression
constraints) comes back as a named `WalkPromotion::Unsupported` reason,
never a silent skip.

<a id="test-decl"></a>
### `test_decl`

`TestDeclPayload`: the design-test lowering surface (WO-83 deliverable
2, `docs/spec/toolchain/37-design-testing.md`, D190). Turns every
`test <name>:` declaration into a raw, un-elaborated structural record
(subject file, name, scenario entries, expect-block expectation
lines) -- nothing here solves anything or resolves a value; this is
only the structure the orchestrator's slice-B runner later consumes.

## L2 numeric solves

<a id="solve"></a>
### `solve` (mod, statics, stiffness, sketch closure)

The L2 numeric solves the compiler owns (WO-23), feature-gated
`solve`: rigid-body statics, the lumped stiffness network, and exact
sketch residual closure (`docs/spec/hematite/05-lowering.md`,
`docs/spec/hematite/03` sec. 4 items 1-3, INV-10/INV-15). These are
compiler passes with bit-reproducible outputs (AD-6), not harness
physics (AD-1): fixed source-order summation, no hash-map iteration,
outward-rounded bounds, and singular/ill-conditioned systems surface as
diagnostics, never a panic or an escaping NaN.

`solve::statics` covers the determinate free-body fast path only; a
statically indeterminate assembly defers to the stiffness network,
reported as a diagnostic. `solve::stiffness` assembles joint/member
stiffnesses into a scalar spring network per node -- a conservative
lower-bound estimate that can discharge a `>=` claim with fat margin
but never prove one violated; thin margins defer to the harness.
`solve::sketch` resolves free segment lengths of a closed straight-walk
via a small deterministic least-squares system, using exact direction
cosines on cardinal angles so cross-platform libm differences never
reach the lockfile (INV-10), and flags an exactly-constrained-but-
inconsistent walk as `E0441`.
