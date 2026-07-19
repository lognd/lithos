# py-harness

The model harness: adapter/registry/plugin machinery that lets a
design declare an engineering claim (bearing life, buck efficiency,
beam bending, CAM/DFM/HDL checks, ...) and get back model-backed
evidence with attestation and numeric/quantity discipline. See
`docs/spec/toolchain/00-architecture.md` for the harness's place in
the pipeline and the model-authoring contract; individual physics
models below are grouped by source file/subpackage rather than
restated symbol-by-symbol.

## init

<a id="init"></a>

`MODEL_REGISTRY_VERSION` (WO-14/15/16, AD-1): the harness model-registry
version constant, a string (not int -- it is opaque hash input, and a
human-readable id survives review). Threaded into `compile` so it folds
into every evidence-cache key (BE-1/INV-1): bumping it whenever a
discharge model is fixed/upgraded invalidates all cached evidence,
forcing re-verification under the new models.

## adapter

<a id="adapter"></a>
### `python/regolith/harness/adapter.py`

The ONE subprocess adapter wrapping non-Python solvers (WO-20/AD-19).

Design: `docs/spec/toolchain/20-solver-abstraction.md` sec. D-C. A
non-Python solver is a normal :class:`regolith.harness.model.Model`
whose physics runs out of process: the adapter serializes the
:class:`DischargeRequest` to schema-versioned JSON on the child's
stdin, reads ONE ``SolverResponse`` JSON document from its stdout, and
maps it into the shared margin rule. stderr is logs (bridged to this
module's logger); exit code 0 covers ALL computed outcomes including a
violated claim. Every infrastructure failure arm is an
:data:`regolith.harness.errors.AdapterError` VALUE the registry maps to
the explicit ``harness.adapter_error`` INDETERMINATE evidence -- never
a pass, never an exception. This wire protocol is deliberately the
Phase E harness-as-separate-process seam and the future remote
transport: one protocol, three deployments.

## attest

<a id="attest"></a>
### `python/regolith/harness/attest.py`

Evidence attestation: sign at discharge, verify at consumption (INV-28).

The signing half of INV-14 extended to computed evidence
(``20-solver-abstraction.md`` D-E/D-G). A solver signs the evidence it
produces over the evidence's AD-18 content address -- an ENVELOPE, never
a hash input, so a signed and an unsigned copy of the same evidence key
identically. Verification is a CONSUMER-side act against the local magnetite
:class:`~regolith.magnetite.TrustKeySet`: signing carries trust, storage does
not (regolith/11 sec. 10.6 rule 4).

``verify_attestation`` is TOTAL and three-valued -- ``Valid(tier)`` /
``Unsigned`` / ``Invalid(reason)``. A present-but-invalid signature is
INDETERMINATE with its own diagnostic family (``ATTESTATION_INVALID_ID``):
never violated (the result might be fine; we cannot trust it), never
silently accepted. Absence of a signature is not an error -- it is the
``community`` tier. Every fallible primitive returns a value; exceptions
stay for programmer bugs (house rule / AD-7).

## converter_topology

<a id="converter_topology"></a>
### `python/regolith/harness/converter_topology.py`

Buck-family topology derived from a compiled ``ConverterGraph``.

WO-88 deliverable 3 (F112, INV-16): WO-36 builds the continuous/discrete
converter graph for an elec behavioral ``spec:`` body Rust-side and
acyclicity-checks it (INV-16); WO-88 exposes it across the FFI on
``BuildPayload.converter_graphs``. This module is the ONE reader that
turns that graph into the switching-converter topology a buck model
consumes -- the switch (drive) node(s), the sensed feedback node(s), and
the switching clock domain -- so a model derives a design's topology
FROM the compiled graph instead of taking it hand-supplied. Shared by
the buck model family (``harness/models/buck_*.py``); the derivation
lives here, once (NO DUPLICATION).

The graph's own vocabulary carries the topology unambiguously (see
``crates/regolith-sem/src/converter.rs``): a ``Converter`` edge is a ZOH
delta crossing the continuous/discrete boundary, so

- a ``Converter`` edge from a clock domain INTO a continuous node is a
  ``dac``/``pwm`` drive -- its target is a SWITCH node driven by the
  loop; and
- a ``Converter`` edge from a continuous node INTO a clock domain is an
  ``adc``/``comparator`` sample -- its target is a SENSED node.

A design carrying at least one of each is a closed-loop switching
converter (:attr:`BuckTopology.is_switching_converter`): the graph
confirms the buck topology structurally, without the model assuming it.

## errors

<a id="errors"></a>
### `python/regolith/harness/errors.py`

Harness error VALUES (AD-7 / house style).

Every fallible harness API returns a typani ``Result[T, E]`` whose ``E`` is
one of these frozen models -- never a bare exception. A missing model, a
missing input, or an out-of-domain request is recoverable data the
orchestrator reasons about (it may pick another model, widen a margin, or
record an indeterminate result); only programmer bugs raise.

## evidence

<a id="evidence"></a>
### `python/regolith/harness/evidence.py`

The margin-driven discharge rule and evidence hashing, in one place.

Regolith/07 sec. 4: a model discharges a claim iff it holds after
charging the model's worst-case error against the margin
(``value +- eps`` vs ``limit``), inside the model's validity domain.
Indeterminate is NOT violated (sec. 4): out-of-domain or short-coverage
is its own status. This module is the single implementation of that rule
so every model shares it (NO DUPLICATION), and the single producer of an
``Evidence`` value's content hash.

Determinism (INV-10): the evidence hash folds every input that could move
the value -- crucially the model's ``deterministic`` flag and, when a
model is non-deterministic, a settings/seed digest -- plus the harness
model-registry version (BE-1/INV-1), so identical inputs give a
byte-identical hash and a model upgrade invalidates cached evidence.

## model

<a id="model"></a>
### `python/regolith/harness/model.py`

The model protocol and the generic discharge driver.

A model is a closed-form (or, later, numeric/planner) predictor for one
claim kind. Every model shares ONE discharge path: it estimates the
claim's quantity at its worst corner (INV-9), declares its worst-case
error and coverage, and the base :meth:`Model.discharge` turns that into
an ``Evidence`` value via the single margin rule in
:mod:`regolith.harness.evidence`. Subclasses implement only the physics
(:meth:`Model.estimate`); the discharge/hashing/status logic is not
theirs to reimplement (NO DUPLICATION).

## harness/models (single-file physics/engineering models)

<a id="models"></a>
Each file in this cluster is one self-contained engineering model
(bearing life/pressure, beam bending/deflection/utilization, bolted
joint, buck efficiency/ripple/transient, cost estimators, friction
factor, fluid pressure drop, lame cylinder, link budget, lumped
thermal, NPSH margin, post embedment, sheet bend, shaft torsion,
tolerance stack, workload realization) registered into the harness
via `harness/registry.py`. Each model's pydantic I/O schema and
governing equations are documented in its own module docstring;
this entry indexes the whole cluster to one doc anchor rather than
duplicating per-file prose (WO-1xx model-pack work orders and
`docs/spec/toolchain/00-architecture.md` cover the harness
model-authoring contract these all follow).

`power.py` (WO-135, `docs/spec/toolchain/43-power-distribution.md`
sec. 3/5, AD-42/D248.3) is the lithos closed-form half of the facility
power-distribution charter: NEC Art. 220 demand load, conductor
voltage drop, NEC 310.15 ampacity derating, transformer %Z
single-source fault-current SCREENING estimate, motor-starting
voltage dip, transformer loading, and power factor -- seven `Model`
subclasses (`elec.power.*` claim kinds), each citing its governing
standard/edition (D250.1) and requiring every safety-critical input
(nameplate %Z, locked-rotor kVA, ...) as a plain required signature
port with no fallback anywhere in the module: an author who has not
declared a real value for one simply cannot supply that port, so the
shared `Model.discharge` path refuses with a named `InputError`
(D250.3 -- an unverifiable input is a named absence, never a default).
The certified/numeric half of the charter (load flow, IEC 60909/ANSI
short circuit with motor contribution, IEEE 1584 arc flash,
protective-device coordination, IEEE 519 harmonics) is feldspar's, in
its own repo (AD-37's boundary rule); this module registers no model
for `elec.power.arc_flash`/`coordination`/`harmonics` so those claims
cannot reach release trust through a lithos built-in (D250.4,
verified by `tests/harness/test_power_models.py`).

## harness/models/cam

<a id="models-cam"></a>
CAM manufacturability models: IR (`ir.py`), machinability/DFM-style
checks (`checks.py`), the pydantic request/response models
(`models.py`), and supporting records (`records.py`). Feeds the
CAM realizer's evidence surface; see the harness model-authoring
contract in `docs/spec/toolchain/00-architecture.md`.

<a id="models-cam-init"></a>
### package marker

`harness/models/cam/__init__.py` re-exports the cam model surface
for `harness/registry.py` registration; no logic lives here.

## harness/models/dfm

<a id="models-dfm"></a>
Design-for-manufacturability checks and their pydantic models/
records (`checks.py`, `models.py`, `records.py`), registered the
same way as the CAM cluster. See
`docs/spec/toolchain/00-architecture.md` for the DFM staging
pipeline (`orchestrator/dfm_staging.py` is the consumer).

<a id="models-dfm-init"></a>
### package marker

`harness/models/dfm/__init__.py` re-exports the dfm model surface
for registration; no logic lives here.

<a id="models-dfm-process"></a>
### `harness/models/dfm/process_records.py` + `process_seeds.py`

The `std.process` record schema + DFM check-set CONTRACT (WO-168,
`docs/spec/toolchain/45-process-record-schema.md`): `ProcessRecord`
(materials, `DimensionedValue`-carrying size limits/tolerance grades/
surface finish/min features, cost drivers, lead class, a REQUIRED
non-empty `provenance` tuple of `ProvenanceNote` -- the D269 amendment
owner-visible posture marker, one of `pd_gov`/`gek`/`named_refusal`)
and `DfmCheckSet` (a non-empty tuple of `DfmCheckEntry`, each its own
module-qualified `check_id` plus its own `ProvenanceNote`), both
schema-and-contract only -- no process DATA population and no check
IMPLEMENTATIONS here (that is WO-169/170/171). `process_seeds.py`
carries two seed records (wire EDM, quench+temper) exercising every
schema branch end to end, including a `named_refusal` entry each,
transcribed from the process-research recon dossiers with provenance
preserved. Both wire into `regolith.backends.capabilities.
RealizerCapability.process_records`/`.dfm_checks` (WO-164) as plain
string cross-links.

WO-169/170/171 population waves add per-family seed modules
(`process_seeds_wave1_*.py`, `process_seeds_wave2_pcb_elec.py`,
`process_seeds_wave3_casting.py`/`_molding.py`/`_powder.py`/
`_additive.py`/`_joining.py`/`_bulk_forming.py`), each a
`ProcessRecord`+`DfmCheckSet` pair per procres/*.md dossier entry.
Wave 3 (the long tail, ~D269 sec.4 tier 3) adds the entirely-new
casting/molding/powder/additive/joining/bulk-forming families (44
records) plus four GENERIC `checks.py` callables reused across many
families rather than duplicated per family (NO-DUPLICATION):
`check_value_window` (declared value within a declared [min,max] band
-- wall thickness, joint gap, bond-line thickness), `check_draft_angle_
min` (die/mold-release draft-angle floor), `check_ratio_max` (declared
ratio must not exceed a process limit -- rib/wall ratio, draw-depth/
opening ratio, upset ratio, per-pass diameter reduction), and
`check_boolean_gate` (a plain yes/no geometric/process predicate --
axisymmetric-only, no-undercut, single-axis release). The subtractive/
sheet/surface family REMAINDERS (procres/subtractive.md,
procres/sheet.md, procres/surface.md, beyond each family's wave-1
entries) are NOT yet populated -- named as remaining work for a future
wave, not silently dropped.

<a id="models-material-state"></a>
### `harness/models/material_state.py`

WO-166 slice (a) (D268 item 1): the plain-pydantic material-state
representation (`HeatTreatState` -- `as_rolled`/`annealed`/
`quenched_and_tempered(temper_temp_c)`/`through_hardened(target_hrc)`,
one model gated by a field validator rather than a discriminated
union) and `HeatTreatStep` (an explicit heat-treat program step: a
material transitioning `from_state` -> `to_state` via a declared
`process_record_key`). Lives at this plain-pydantic layer rather than
as a hematite grammar addition (T-0043/D272 posture: schema frozen,
realized kinds stay plain-pydantic, promotable later). `check_heat_
treat_transition` gates a step against the REAL WO-169 wave-1 checks
(`check_process_sequencing`, `check_quench_section_uniformity`) --
never a new predicate.

## harness/models/hdl

<a id="models-hdl"></a>
HDL sim-tier evidence models (`models.py`), verilator adapter
(`verilator_adapter.py`), and test fixtures (`fixtures.py`) that
give cuprite digital designs simulation-backed evidence per
`toolenv.py`'s verilator/ghdl posture. See
`docs/spec/toolchain/00-architecture.md`.

<a id="models-hdl-init"></a>
### package marker

`harness/models/hdl/__init__.py` re-exports the hdl model surface
for registration; no logic lives here.

## numeric

<a id="numeric"></a>
### `python/regolith/harness/numeric.py`

The reduced-tier numeric model contract (WO-26 D105b).

A reduced-tier numeric model is a worst-corner sweep over a scalar
point evaluation (regolith/07 sec. 2's sweep coverage): the subclass
provides ONLY the physics (:meth:`NumericReducedTierModel.evaluate_point`)
plus optional per-input monotonicity declarations and its worst-case
error; the base owns corner enumeration, the grid sweep for
non-monotone axes, the D95 structured coverage axes, and the single
margin rule via the shared :meth:`regolith.harness.model.Model.discharge`
(NO DUPLICATION -- no subclass reimplements corners or the margin).

Conservatism (INV-9): a declared-monotone input contributes exactly its
WORST corner (direction chosen from the declaration and the claim
sense); an undeclared input contributes a k-point grid INCLUDING both
corners -- honest about being a sample, never claimed as a proof, and
recorded per-axis in the evidence's coverage (D95).

## payloads

<a id="payloads"></a>
### `python/regolith/harness/payloads.py`

The payload-kind vocabulary the D96 channel carries (WO-30, sec. 8.3).

Single-homed here so no signature or discharge request ever hard-codes
a payload-kind string: registration lints signature ``payload_kinds``
values against this tuple. The strings are feldspar 09 sec. 4's list
VERBATIM -- the contract is the string, not a regolith re-styling of
it.

## plugin

<a id="plugin"></a>
### `python/regolith/harness/plugin.py`

Model-pack composition over the ONE plugin seam (WO-20/AD-19, WO-44/AD-26).

Design: `docs/spec/toolchain/20-solver-abstraction.md` sec. D-B. A pack is
a normal Python distribution exposing one entry point in the group
``regolith.plugins`` whose target is a ``regolith.plugins.PluginManifest``
with ``kind=model_pack`` and a ``register_fn(registry) -> None`` callable
(WO-44 migrated this seam off its own ``regolith.model_packs`` group onto
the shared one). regolith discovers packs by id only and NEVER imports one
by module path (no dependency cycle is representable). Composition is
deterministic: built-ins first (``default_registry``), then packs in
sorted-by-id order. A bad pack is skipped LOUDLY -- its error is a value
recorded on the registry and named in the build report, and its models
are staged so a mid-registration failure never leaves a partial load --
but it never aborts the other packs and never raises.

## quantity

<a id="quantity"></a>
### `python/regolith/harness/quantity.py`

Harness-side scalar and interval quantities (Phase C model math).

The harness works in plain ``f64`` magnitudes in a single consistent unit
system: unit reconciliation and dimensional checking are the compiler
core's job (``regolith-qty``, AD-1/AD-9), so a model that reaches the
harness is fed numbers whose units the orchestrator has already made
coherent. What the harness DOES own is corner discipline (INV-9): an
input tolerance/environment range is an :class:`Interval`, and a model
evaluates its claim at that interval's own worst corner.

## registry

<a id="registry"></a>
### `python/regolith/harness/registry.py`

The versioned model registry and deterministic, total selection.

Regolith/07 sec. 3: the harness holds models keyed by the claim kind
they discharge. Selection is TOTAL and honest -- an obligation with no
matching model yields an explicit indeterminate evidence value
(``harness.no_model``), never a silent pass -- and DETERMINISTIC:
candidates are ordered by (cost, model id) so the same obligation always
picks the same model.

Version discipline (BE-1/INV-1): the registry carries
:data:`regolith.harness.MODEL_REGISTRY_VERSION`, and that string is folded
into every evidence hash (via :mod:`regolith.harness.evidence`). The Rust
core already threads this same version into the obligation/evidence-cache
key at discharge time; bumping it invalidates cached evidence so a model
upgrade forces re-verification.

## signature

<a id="signature"></a>
### `python/regolith/harness/signature.py`

Model signatures: the typed contract the registry matches against.

A signature is the harness-side half of the spec's model registry
(regolith/07 sec. 3): what claim a model discharges, which inputs it
needs, and the validity-domain tags it declares. It is deliberately a
Python-native model (not the generated ``_schema.Signature``, which is
the Rust-side interchange record for `impl ... by` declarations): the
harness owns the executable code and its matching predicate.
