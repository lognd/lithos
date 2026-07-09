# Claims, Obligations, Evidence

> Regolith spec. The verification spine. Identical schema for both
> domains; only the model registries differ.

## 1. Claims

`require <Group>:` blocks hold named claims -- checkable statements in
quantity-core vocabulary. No solver names, no `fea.` / `spice.` prefixes
in claims; *what* must be true, never *how* to check it:

```
require Structural:
    max_stress: mech.max(stress.von_mises) < material.sigma_y(T_local) / 2.5

require Power:
    droop: elec.min(v(vdd_core)) > 3.0V during load_step
    life:  elec.energy(all, over=1yr) <= supply.capacity, sf=1.3

require Timing:
    deadline: info.latency(control_path) < 1ms, sf=2

require Survival:                    # time-domain claims (see 02, section 5)
    shock:   peak(mech.stress, during drop) < material.sigma_y, sf=1.5
    settle:  settles(v(out), to=+-1%, within 200us after load_step)
    seq:     stays_within(v(vdd_core), mask=power_up_seq, during startup)

require Noise:                       # frequency-domain claims, same family
    floor:    rms(v(out), band=[10Hz, 100kHz]) < 1mV
    firstmode: mech.first_mode > 120Hz
    emissions: stays_within(emissions, mask=CISPR_11_B)
```

- Claims may be individually named; ledgers, waivers
  (`--waive Group.claim`), and the lockfile cite the names.
- `forall <cfg> [in <domain>]:` quantifies a claim over a configuration
  domain (mech: a mechanism angle; elec: an operating mode, a data
  pattern class).
- `sf=` is the safety multiplier everywhere. `margin` means only the
  evidence value-to-limit distance.
- `@hint(...)` carries droppable guidance. **Droppable is defined**
  (INV-3): for a fixed resolved design, verdicts are hint-invariant --
  a hint may affect what is tried first, never domain validity or
  coverage; anything load-bearing must be a checked fact or an
  explicit `assume!`. Entity-DB symmetry is NOT a hint: it flows into
  obligations as a **checked fact** (computed conservatively, INV-4)
  and may be load-bearing.

## 2. Obligations

The compiler lowers every physical claim -- requirements, interface
promises `by analysis`, connection state claims, generated-load checks --
into self-contained obligations:

```
obligation housing.front_seat.stiffness_promise:
    claim:    mech.stiffness(frame=front_seat.frame, dir=radial) >= 80 kN/mm
    subject:  realization_ref(housing, snapshot=#a91f3c)     # content-addressed
    given:
        material: AlSi10Mg
        T_env:    [-20degC, 95degC]
        loads:    interface_envelope(front_seat)
        backing:  promises_only          # or measured(...) for opt-ins
    hints:    [symmetry=Cinf(z)]
```

Self-contained implies serializable implies remote/distributed discharge
for free. The harness never sees source; the compiler never sees physics.
One schema for both domains -- an elec obligation differs only in which
namespaces its claim and givens speak.

**Swept obligations** [SETTLED] (resolves the former mech SEAM-3): when a
claim ranges over a monomorphized integer domain or a config domain, the
compiler emits **one obligation carrying the domain** (`sweep: n in
[2, 6]`, `sweep: pivot.theta in [0deg, 95deg]`), not one per point. The
harness decides coverage: a model that declares monotonicity/convexity in
its metadata may discharge at extreme corners only; otherwise it sweeps.
Evidence must state the coverage achieved (`corners`, `grid(k)`,
`analytic`), and the cache stores per-point results internally so a
domain shrink reuses them. Rationale: the model knows the claim's shape
over the domain; the compiler does not. This vocabulary is now a
STRUCTURED, per-axis encoding (`regolith-oblig::Coverage`/`CoverageAxis`,
WO-30, D95, `../toolchain/20-solver-abstraction.md` sec. 8.2):
each axis names its domain (continuous interval or enumerated discrete
set) and its method (`corners`/`grid{k}`/`enumerated`/`analytic`/
`monotone`); the bare scalar fraction survives as the conservative
collapse (`Coverage::fraction`), never overstating the axes.

**Computed-field obligations** (D98, WO-33, `02-quantity-core.md` sec.
4a): a `compute <name>: <quantity kind> over <index domain>` claim
lowers to ONE obligation whose evidence carries a `field` payload
instead of a scalar -- the discretized values over the index domain
plus its `CoverageAxis` encoding. The produced name enters the datum
ledger; sibling projection claims (`max`/`min`/`<name> at ...`/
`slope`) lower to ordinary obligations whose givens reference the
producing obligation by name and content-hash digest slot (the same
promise-chain mechanism dissipation uses). A producer's indeterminate
evidence makes every consuming projection indeterminate in turn --
the chain rule of the ledger, never a silent discharge.

**Orbit extension soundness** (INV-4): extending one instance's result
across a symmetry orbit is legal only when the obligation's *givens*
are also invariant under the orbit's group -- a geometrically perfect
bolt circle under a bending moment does not license verify-one. The
discharging model checks givens-invariance, or uses the
orbit-worst-case envelope instead; otherwise it falls back to
per-instance discharge.

## 3. The model registry

The harness holds models, each declaring: inputs/outputs (quantity-core
typed, via signatures), validity `domain:`, error model, cost.

| tier | mech examples | elec examples |
|---|---|---|
| closed-form | beam theory, Lame, joint diagrams, VDI 2230 | Ohm/RC, IPC-2221 current capacity, static timing arithmetic, worst-case DC analysis |
| reduced | shell FEA, component-mode synthesis | IBIS signal integrity, lumped thermal, switching-loss models |
| full | volumetric nonlinear FEA, contact | transistor-level SPICE, EM field solve, gate-level timing simulation |

## 4. Margin-driven discharge

> A model discharges a claim iff the claim holds **after charging the
> model's worst-case error against the margin** (`value + eps_model <=
> limit`), with the model inside its validity domain.

Consequences:

- **Accuracy is automatic; there are no fidelity knobs.** Fat margins
  discharge via closed-form models in microseconds; thin margins force
  expensive models because nothing cheaper can close them. Healthy safety
  factors make verification cheap -- the right incentive.
- **Best-path search** over the model graph finds the cheapest in-domain
  path that closes the margin.
- **Evidence** is the only return type:

```
evidence: status: discharged | violated | indeterminate
          value: 94.2 kN/mm (eps <= 3.1)   margin: 11.1 after error
          model: shell_fea_v2 (domain: thin_wall ok, linear ok)
          cost: 4.2s    hash: #e77c01
```

- **Indeterminate is not violated.** "No in-domain model is accurate
  enough" gets its own diagnostic family: which models were considered,
  why rejected, what would resolve it (refinement budget, `measured`,
  more margin).
- Evidence is content-addressed and cached: unchanged (snapshot, contract,
  registry-version) means already discharged. Promise-backed system
  obligations survive artifact edits untouched -- incremental verification
  falls out of the contract architecture.

## 5. Corner discipline

Interval inputs (tolerances, scatter, environment, PVT) are evaluated at
each check's own worst-case corner: part stress at max interference,
transmitted torque capability at min; setup timing at the slow corner,
hold at the fast corner; press-fit retention at the hot corner. The
"which corner is worst" mapping is part of the model, not the user's job.

## 6. Planning as evidence

[SETTLED] Some claims are about *making*, not physics: manufacturability,
unit cost, cycle time (mech: machining, forming; elec: assembly,
programming). These follow the same discharge rule with **planner
models**: eager rule packs (DFM/DRC) are the cheap conservative tier; a
full planner (CAM: toolpath generation with reach/collision/fixturing
analysis; elec: feeder/assembly planning) is the expensive tier, forced
only when rule-pack margins are thin (deep pockets, tight corners, odd
fixturing). The planner's output -- the plan itself (setups, ops, times,
cost) -- is an **evidence artifact**, content-addressed and cached like
any evidence.

Two consequences:

- `require Manufacture: makeable: manufacturable(milled)` and
  `cost: mfg.unit_cost(qty=100) <= 30 USD` are ordinary claims;
  `--release` refuses assumed manufacturability like any other
  assumption.
- **Backends serialize evidence; they never decide.** G-code emission at
  L6 is a serialization of the CAM plan evidence; pick-and-place files
  serialize the assembly plan. Anything decision-shaped that used to
  live in a backend is a planner model whose plan is pinned
  (lockfile cause: `planner`).
- **Production multiplication is planner territory** [SETTLED,
  cycle 2]: PCB panelization, sheet-metal nesting, casting trees,
  build plates. The designer declares the *product* artifact; the
  process pack + planner decide the multiplication; the panel/nest/
  tree is plan evidence, serialized at L6. It is never a language
  artifact (intent, not mechanism -- and the defaults test holds:
  conservative, local, lockfile-caused).

## 7. The orchestrator: verification loop and allocation search

**The lazy loop** -- only for physics-resolved free variables, and only
after the eager candidate fails verification:

```
1. compiler: eager-resolved candidate -> snapshot + obligations
2. harness:  discharge all -> evidence set (+ sensitivities on request)
3. all discharged -> lockfile, done
4. else: propose next assignment (sensitivity-guided; constrained to
   eager-feasible AND structure-preserving domains), goto 1 incrementally
```

**Allocation search** -- for *discrete* derived decisions (mech: process
planning, setup/fixturing choices; elec: intent-to-block partitioning,
component binding, bus mapping, pin-mux), the orchestrator runs
**conflict-driven greedy search with lazy verification**:

1. **Greedy descent.** At each decision point, take the policy-best
   candidate (cost/power/availability), screened only by the cheap tier:
   capability arithmetic, budget sums, conservative closed-form models.
2. **Lazy verification.** Full obligation discharge waits for a complete
   candidate (or declared milestone gates, e.g. verify budget-closure
   claims at binding time, layout-dependent claims post-route).
3. **Conflict-driven backtracking.** A violated obligation carries a
   blame set -- the decisions its inputs depend on, via constraint-graph
   provenance. Backjump to the most recent blamed decision
   (non-chronological), and record a **nogood** ("this MCU family +
   BLE-active power budget: infeasible") so the search never retries the
   combination. Nogoods are solver state, not lockfile content; only
   final choices are pinned.

Fail-fast is structurally hard here (some failures are only visible
post-realization: noise needs layout). Three mitigations, all existing
machinery: conservative cheap models double as search-time screens
(margin-driven hierarchy = pruning order); staged verification gates
catch what they can early; conservative defaults and reserves (defaults
test) make early decisions robust to late surprises.

Compiler and harness stay pure; iteration, caching, scheduling, search
state, and the lockfile live in the orchestrator. Its API is what CLI,
CI, and any future UI consume.

## 8. Honest deferral

- `impl ... = todo!` -- defers **conformance proof**, not contract.
  System solves run normally on the promises. Ledgered; refused by
  `--release`.
- `assume!(expr, basis=...)` -- accepts an **obligation** without
  evidence (assumed loads, assumed flux, assumed benchmark). First-class,
  ledgered, refused by `--release` except per-item acknowledgment.
- `waive <target> [on <scope>]: basis: ... [by <evidence>]` -- accepts
  a specific **violated or indeterminate result**, in source, scoped,
  attributed. With an evidence clause it is a *deviation* (permitted in
  `--release`, listed); without one it is release-gated like `assume!`.
  Full rules: `12-overrides-and-hints.md` section 3.

All three make uncertainty and accepted risk visible state instead of
optimistic lies -- and none of them can convert `violated` into
`discharged` (the ladder's safety property, `12` section 1).
