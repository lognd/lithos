# Verification harness -- Phase C status

Home: `python/regolith/harness/` (AD-1: the harness is Python; registry
and model versions are Python-side). Spec: regolith/07 (claims,
obligations, evidence, the model registry, margin-driven discharge);
roadmap `docs/hematite/06-roadmap.md` Phase C/D. This is TODO.md "PATH TO
DONE" section 6.

## What exists (this cycle)

The registry + matching spine and the FIRST closed-form model pack:

| module | role |
|---|---|
| `harness/quantity.py` | `Interval` (worst-case corner, INV-9) + exact `f64<->bits` for evidence serialization |
| `harness/signature.py` | `ModelSignature` (claim kind, `ClaimSense`, required inputs, domain tags) -- the harness-side match contract |
| `harness/evidence.py` | the ONE margin rule (`value +- eps` vs limit, sec. 4) + the evidence content hash |
| `harness/model.py` | `Model` ABC + `DischargeRequest`/`Prediction`; the shared discharge driver (no per-model duplication) |
| `harness/registry.py` | `ModelRegistry`: register / deterministic `candidates` / total `select` / `discharge`; `default_registry()` |
| `harness/models/buck_ripple.py` | the reference pack: CCM buck output-voltage ripple |
| `harness/models/bolted_joint.py` | VDI 2230 bolted-joint residual clamp (separation) |
| `harness/models/beam_bending.py` | Euler-Bernoulli cantilever tip deflection |
| `harness/models/link_budget.py` | RF decibel link margin (Kestrel downlink) |
| `harness/models/lame_cylinder.py` | thick-wall Lame bore von-Mises stress (torch igniter chamber) |
| `harness/models/sheet_bend.py` | sheet-metal minimum bend radius DFM check (sheet bracket flange) |
| `harness/attest.py` | evidence attestation (WO-21/INV-28): `sign_evidence` over the AD-18 content address, total three-valued `verify_attestation` (`Valid`/`Unsigned`/`Invalid`), `conferred_tier` |

Properties held:

- **Attributable evidence (INV-28).** A solver signs the evidence
  content address (an ENVELOPE, never a hash input), so a signed and an
  unsigned copy key identically; the consumer verifies against its quarry
  `TrustKeySet` at consumption time, mapping to the existing trust tiers
  (a designated key confers `certified`/`tested`, unsigned is
  `community`). A present-but-invalid signature is INDETERMINATE with its
  own `harness.attestation_invalid` family -- never violated, never a
  silent pass; the release gate refuses a claim whose `trust:` floor
  exceeds its evidence's conferred tier.

- **Total + honest selection.** `select` returns a typani `Result`; a
  no-match is `Err(NoModelMatch)`, and `discharge` maps it to an explicit
  `harness.no_model` **indeterminate** evidence value -- never a silent
  pass (regolith/07 sec. 4: indeterminate is not violated).
- **Deterministic (INV-10).** Same inputs -> byte-identical `Evidence`
  (hash + every bit field). Floats hash as exact `f64` bits; the model's
  `deterministic` flag and (for non-deterministic models) a settings
  digest are hash inputs.
- **Versioned keying (BE-1/INV-1).** The registry carries
  `harness.MODEL_REGISTRY_VERSION`, folded into every evidence hash;
  it aligns with the Rust core, which threads the same version into the
  obligation/evidence-cache key at discharge time. Bump invalidates
  cached evidence.
- **Corner conservatism (INV-9, harness-model side).** The buck pack
  evaluates the ripple formula at every interval-box corner in numpy and
  reports the worst -- sound for any input box, no hand-proved
  monotonicity.

## The reference pack

`elec.buck.output_voltage_ripple` discharges `require Regulation: ripple`
in `examples/elec/buck_converter.cupr`. Textbook CCM buck, ESR neglected
(the neglected term is charged into a conservative 5% `eps`):

    delta_i_L = v_out * (v_in - v_out) / (v_in * f_sw * L)
    v_ripple  = delta_i_L / (8 * f_sw * C_out)

Known-answer (v_in=12V, v_out=5V, f_sw=500kHz, L=22uH, C_out=47uF):
~1.4104 mV, discharged with ~18.5 mV margin under the 20 mV limit.

## Three more closed-form packs (this cycle)

Each conforms to the reference contract exactly (signature -> worst-corner
numpy sweep -> `Prediction` -> the shared discharge rule), charges its
neglected term into `eps`, and ships a known-answer + verdict +
determinism test in `tests/harness/`:

- **`mech.bolt.joint_separation`** (`bolted_joint.py`, LOWER bound) --
  the VDI 2230 preload diagram. Load factor `phi = k_bolt/(k_bolt+k_clamp)`,
  residual clamp `F_KR = F_M - (1-phi)*F_A`; the joint must keep
  `F_KR >= F_Kreq`. Serves the corpus's clamp-dependent joints
  (`torch_igniter.hem` flange `require Seal`, cubesat `StackMate` cards).
  Neglected embedding / preload relaxation charged as 10% of preload.
  Known answer: F_M=10kN, F_A=4kN, k_bolt=1e8, k_clamp=4e8 -> phi=0.2,
  F_KR=6800 N; discharged over a 2 kN demand (eps 1 kN).
- **`mech.beam.cantilever_deflection`** (`beam_bending.py`, UPPER bound) --
  Euler-Bernoulli end-loaded cantilever `delta = F*L^3/(3*E*I)`, serving
  `sheet_bracket.hem`'s `sag: mech.deflection(...) < 0.2mm`. Neglected
  shear (Timoshenko) deflection charged as 5% eps. Known answer:
  F=200 N, L=0.05 m, E=200 GPa, I=1e-8 m^4 -> 4.1667 um; discharged
  under the 0.2 mm limit.
- **`elec.link.margin`** (`link_budget.py`, LOWER bound) -- decibel power
  balance `P_rx = pa_out + gain - path_loss`, `margin = P_rx - sensitivity`,
  serving `kestrel.cupr`'s `require Link: margin >= 6dB`. Neglected
  implementation / pointing / polarization losses charged as a fixed 2 dB.
  Known answer: pa=30 dBm, gain=12 dBi, path_loss=140 dB, sens=-110 dBm ->
  P_rx=-98 dBm, margin=12 dB; discharged over the 6 dB demand.

## Two more closed-form packs (this cycle)

Same reference contract; each ships a known-answer + verdict + corner +
domain-guard + determinism test in `tests/harness/`:

- **`mech.cylinder.lame_bore_stress`** (`lame_cylinder.py`, UPPER bound)
  -- the thick-walled-cylinder Lame stresses, serving
  `torch_igniter.hem`'s `require Structural: hoop:
  peak(mech.stress.von_mises, during boundary.chamber_pressure) <
  material.sigma_y(T_local)/2`. At the bore `r=a` (open ends,
  `sigma_z=0`): `sigma_theta = p*(b^2+a^2)/(b^2-a^2)`, `sigma_r = -p`,
  and `sigma_vm = sqrt(sigma_theta^2 - sigma_theta*sigma_r + sigma_r^2)`.
  Neglected capped-end axial stress and bore stress concentration charged
  as 5% eps. Known answer: p=3 MPa, a=10 mm, b=20 mm -> sigma_theta=5 MPa,
  sigma_r=-3 MPa, sigma_vm=7 MPa; discharged under the ~145 MPa (sigma_y/2)
  limit.
- **`mech.sheet.min_bend_radius`** (`sheet_bend.py`, UPPER bound) -- the
  eager sheet-metal DFM min-bend-radius rule, serving
  `sheet_bracket.hem`'s `dfm(min_bend_radius)` on `flange =
  Bend(radius=free)`. The press pack's minimum inside radius `r_min =
  ratio*thickness` must not exceed the design's specified radius (the
  limit). Neglected springback / grain-direction allowance charged as 10%
  eps. Known answer: thickness=1.5 mm, ratio=1.6 -> r_min=2.4 mm (the
  corpus's resolved value); discharged under a 3.0 mm specified radius.

## The conformance-refinement pack (INV-13 discharge half)

`conformance.py` ships the equivalence model behind INV-13's test ("a
spec contradicted by its hand-written impl must fail equivalence"). It is
NOT a physics model: it is a PROMISE comparison (INV-19). Given an UPPER
contract (the interface/spec's demanded bound, carried as the request
`limit`) and a LOWER realization (the impl's declared bound, the
`impl_bound` input), it checks the impl is a sound REFINEMENT of the spec
-- a bound no *weaker* than the spec's -- and folds the check onto the one
margin rule with `eps = 0` (the comparison is exact):

- `harness.conformance.upper_bound` (upper sense) -- refines iff the
  impl ceiling is no higher than the spec's (`impl_bound <= spec_bound`);
  worst corner of the impl bound is its MAX.
- `harness.conformance.lower_bound` (lower sense) -- refines iff the impl
  floor is no lower than the spec's (`impl_bound >= spec_bound`); worst
  corner is its MIN.

One `ConformanceRefinementModel(upper=...)` class, registered once per
direction. A contradicting impl (a wider window than the spec promised)
-> `violated`, never a silent pass; a non-finite / non-comparable bound
-> honest `indeterminate` (SOUND: never a false pass). Known answer: spec
`Q <= 20`, impl `Q <= 14` -> discharged; impl `Q <= 25` -> violated.

The compiler already emits the `conforms` obligation by construction
(green half of `test_inv_13_no_dead_uppers.py`); the discharge half now
drives this model end-to-end through the registry. The bridge -- resolving
the `conforms` claim form's two windows into a `DischargeRequest` -- is
CLOSED (cycle 16, TRIAGE C16): `claims.rs` threads the upper contract's
and lower realization's leading comparator bounds into the obligation's
`given.loads`, and `orchestrator.translate` lowers them into this model's
request. INV-13's discharge half and INV-26's implicit-`by spec` default
now discharge REAL lowered obligations end-to-end. Honest cut: the
compiler extracts the FIRST comparator-bound field per side (positional,
not name-matched); a side with no literal bound leaves the windows absent
and the orchestrator defers the obligation honestly, never a silent pass.

## WO-26 landed this cycle: two claim-form lowering steps

`regolith-lower::claims` now performs two of the WO-26 claim-form
lowering steps ahead of the orchestrator:

- **Unit-suffix bound resolution (deliverable 1).** Every comparator
  bound's unit-suffixed numeral (`<= 0.2mm`, `>= 6800 N`, `<= 85degC`)
  resolves through `regolith-qty::Unit` into its SI-base magnitude
  BEFORE the predicate text reaches `orchestrator.translate`, which
  parses only bare numerals. Offset units (`degC`) resolve through
  their additive offset, not just their scale, so a temperature bound
  compares correctly against SI-base Kelvin quantities elsewhere in the
  corpus. A bound whose suffix `regolith-qty` does not recognize (`6dB`,
  a bare `%`, an entity reference) passes through UNCHANGED -- the
  orchestrator defers it exactly as before, never an invented number.
- **`within [lo, hi]` two-sided windows (deliverable 2).** A `within
  [lo, hi] ...` demanded window (`batt_window: thermo.temperature(...)
  within [0degC, 45degC] forall op` in `kestrel.cupr`) now splits into
  TWO one-sided obligations (`<subject>.lo >= lo`, `<subject>.hi <=
  hi`) over the same subject, each independently unit-resolved and
  lowered through the EXISTING scalar-comparison path -- no new
  two-sided request type needed in the harness. This also required
  fixing `Field`'s predicate-text extraction: a continuation predicate
  parses as more than one CST child under the field, and the previous
  `Field::value()`-based read silently dropped everything after the
  first child (so the `within` clause was never even seen). Claims
  lowering now reads the field's full source text past its `name:`
  separator (`full_predicate_text`), fixing this for every multi-node
  predicate, not just `within`.

Net effect on the corpus deferral list (`tests/golden/data/deferral_*.json`,
new this cycle): the cubesat corpus's `batt_window.lo`/`batt_window.hi`
Thermal claims now LOWER to a `DischargeRequest` (`no_model` indeterminate
today, since no thermal reference pack is registered yet -- but no longer
an `unsupported_op` deferral, the literal WO-26 acceptance bar). 11 of 95
cubesat obligations now lower.

## Not yet built (tracked TODOs, WO-26 residual)

Genuinely out of reach this cycle, recorded as open cuts (not silently
dropped -- see `docs/implementation/WO-26-harness-completion.md`'s own
"Cuts recorded this cycle" section for the full reasoning):

- **Temporal/containment typed payloads** (`peak`/`settles`/`overshoot`/
  `rms(band=)`/`stays_within(mask)`). `regolith_oblig::ClaimForm` already
  has typed variants for these (`Peak`, `Settles`, `Overshoot`, `Rms`,
  `StaysWithin`), but none carries a comparator/limit field, and every
  corpus instance of these forms embeds its bound OUTSIDE the temporal
  call (`rms(v(out), band=...) < 20mV`, `peak(sig, during w) <
  material.sigma_y(T)/2`) while some have NO trailing bound at all
  (`settles(...)`, `stays_within(..., mask=...)`, `overshoot(...)`).
  Wiring `claims.rs` to emit these variants requires resolving how a
  bound attaches to each form -- a real spec ambiguity, escalated here
  rather than invented; see the WO-26 doc.
- **dB term resolution for `require Link`.** The Kestrel margin claim's
  comparator sits MID-EXPRESSION (`comms.pa_out + antenna.gain -
  path_loss(...) >= gs_uhf437.sensitivity + 6dB during op = downlink`),
  not leading a bound the way every other require-line claim in the
  corpus does, and every term but the trailing `6dB` is an entity-field
  reference (`comms.pa_out`) or a function call (`path_loss(...)`) with
  no numeric value threaded through the obligation today. This needs
  expression-level splitting AND entity-value threading, both beyond
  this cycle's scope; the link-budget pack (`link_budget.py`) stays
  FUNCTIONAL but unreachable from the real corpus claim, an honest
  tracked gap (not a fake pass).
- **Name-matched (not positional) conformance bound extraction.**
  `conformance_windows` in `claims.rs` still extracts the FIRST
  comparator-bound field per side (a WO-19-era cut); matching promised
  bounds by NAME across interface/impl bodies needs the WO-12 contract
  IR's field identity, not yet built.
- **Buck efficiency + transient packs.** Blocked upstream: `eta` is a
  `forall i(out) in [...]:` sweep-domain claim (claims.rs's documented
  "every obligation here is a single-point obligation" limitation) and
  `transient`/`softstart` are the same temporal-form gap above. No new
  pack can be usefully wired until one of those two upstream gaps
  closes.
- **Numeric reduced-tier base class + lumped thermal reference pack,
  planner-model base class, INV-12 match-set-growth lockfile diff.**
  Not started this cycle; each needs its own design pass (the reduced-
  tier contract's worst-corner-sweep API, the planner artifact's
  content-addressed evidence shape, and the lockfile schema extension to
  carry waiver match sets across builds) beyond the time this dispatch
  had -- recorded as open, not invented under time pressure.

## Invariant tests

The harness makes the INV-09 (corner) / INV-10 (determinism) guarantees
reachable on the model side, exercised directly in `tests/harness/`. The
`tests/invariants/` INV-09/10/16/19 modules stay as they are: their
xfail stubs assert deliberate-violation fixtures against the Rust
mechanisms (WO-03/11/12) and the end-to-end ladder/release layers, which
are out of this scope -- flipping them needs those layers, not the model
pack.
