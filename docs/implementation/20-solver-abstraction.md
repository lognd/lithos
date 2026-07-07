# Solver abstraction and signed evidence (design)

One sentence: external solvers (FEA, SPICE, CAM, vendor tools) plug
into the harness as discoverable model packs -- in-process Python or
out-of-process executables -- and every solver cryptographically signs
the evidence it produces, feeding the existing trust-tier machinery.

Status: design accepted (cycle 18); implemented by WO-20 (plugin
layer), WO-21 (signing), WO-27 (reference external FEA pack).
Architecture decisions: AD-19, AD-20 in `00-architecture.md`.
Spec anchors: regolith/07 (model registry, margin-driven discharge,
evidence), regolith/11 sec. 3 (`models` package kind) and sec. 7/10.6
(trust tiers, signing carries trust), regolith/13 INV-1/9/10/14/22.

## 0. The gap this closes

The abstraction layer half-exists and is NOT replaced: `harness.Model`
(ABC), `harness.signature.ModelSignature` (the match contract),
`harness.registry.ModelRegistry` (deterministic, total selection), and
the serializable `DischargeRequest`/`Evidence` pair. What is missing:

1. A way for a model pack that is NOT in this repo to register itself
   (regolith/11 already names `fea.shell`, `spice.ngspice`,
   `cam.mill3ax` as `models`-kind packages; nothing loads them).
2. A way for a solver that is NOT Python to discharge obligations
   (obligations are serializable BY DESIGN, regolith/07 sec. 2 --
   "remote/distributed discharge for free" -- but no adapter exists).
3. Attribution: evidence records `model:` as a string. Nothing proves
   WHICH solver binary produced a result, so the trust floor machinery
   (`trust: >= certified`) cannot apply to computed evidence the way
   it applies to signed registry records.

## 1. Design decisions

### D-A: the model registry IS the solver abstraction layer

External solvers are model packs conforming to the existing `Model`
contract (signature -> worst-corner evaluation -> `Prediction` -> the
one shared margin rule). No parallel "solver API" is introduced.

Rejected: a separate `regolith.solvers` protocol distinct from harness
models. Two registration/selection/keying paths would desync (NO
DUPLICATION), and regolith/07 sec. 3 already defines the three tiers
(closed-form / reduced / full) as ONE registry with cost and validity
domains -- best-path search needs them in one graph.

### D-B: discovery by entry points; regolith never imports packs

A pack is a normal Python distribution exposing one entry point in
group `regolith.model_packs`:

```
[project.entry-points."regolith.model_packs"]
feldspar = "feldspar.pack:register"
```

`register(registry: ModelRegistry) -> None` adds models.
`default_registry()` composes built-ins first, then discovered packs
in sorted-by-name order (deterministic composition). The dependency
arrow points one way: packs import `regolith.harness`; regolith
discovers packs by name only. No cycle is representable.

### D-C: out-of-process solvers speak the existing schemas

A non-Python solver is wrapped by `SubprocessSolverModel`, a `Model`
whose evaluation is: serialize the `DischargeRequest` to JSON
(schema-versioned, AD-5), write to the child's stdin, read a
`SolverResponse` JSON from stdout, map into the shared discharge rule.
stderr is logs (bridged to the `regolith.harness.adapter.*` logger).
Exit code 0 covers ALL computed outcomes including violated --
a nonzero exit is an infrastructure failure and maps to an explicit
`harness.adapter_error` INDETERMINATE evidence value, never a pass,
never an exception (the no-model precedent).

This is deliberately the same seam as roadmap Phase E item 13
("harness as a separate process"): once one model can discharge over
stdio, the whole harness can, and remote discharge is the same wire
format over a different transport. One protocol, three deployments
(in-process, subprocess, remote).

Rejected: gRPC/HTTP adapter in v1 (heavier; revisit for remote
discharge exactly as AD-4 already notes); per-solver bespoke CLI
parsing in regolith (the wrapper executable owns translating the wire
format to its solver's native input -- mesh files, SPICE decks --
because the wrapper knows the solver; regolith knows only the schema).

### D-D: version keying extends BE-1, per pack

Evidence hashes already fold `MODEL_REGISTRY_VERSION` (BE-1/INV-1).
With external packs that single version is insufficient: upgrading
feldspar must invalidate feldspar-produced evidence and nothing else.
The evidence hash therefore additionally folds the discharging model's
`(pack_name, pack_version)`; built-ins carry
`("regolith", MODEL_REGISTRY_VERSION)`. Non-deterministic solvers keep
folding their settings digest (existing mechanism, INV-10).

### D-E: solvers sign the evidence content address

`Attestation` is an ENVELOPE around evidence, not part of it:

- The signature is computed over the evidence's existing
  content address (`blake3(domain_tag || schema_version ||
  canonical_cbor(evidence))`, AD-18). Signing therefore never perturbs
  the hash, cache keys stay pure functions of the payload, and
  re-signing (key rotation) never invalidates a cache.
- Verification happens at consumption (orchestrator, release gate),
  not at storage: the cache stores what it is given; trust is decided
  by the CONSUMER's key set, exactly like registry records
  (regolith/11 sec. 10.6 rule 4 -- signing carries trust, hosting/
  storage does not; INV-14).
- Tier mapping reuses the existing evidence-class ladder: evidence
  whose attestation verifies against a key the consumer designates
  `certified` (vendor/authority solver keys) ranks `certified`;
  against a designated project/machine key, `tested`; unsigned or
  unverifiable, `community`. A claim's `trust: >= tier` floor then
  applies to computed evidence with zero new surface.
- A PRESENT-but-INVALID signature (tamper, wrong key) makes the
  evidence INDETERMINATE with its own diagnostic -- never violated
  (the result might be fine; we cannot trust it), never silently
  accepted. Absence of a signature is not an error; it is the
  `community` tier.

Rejected: signature as a hash input (couples caching to key
management); signing the request+response transcript (the content
address already commits to the full evidence payload, which embeds
the request key); a new trust vocabulary (the record tiers exist and
INV-14's proof argument extends verbatim).

### D-F: FEA is a separate distribution; the repo keeps the contract

The FEA solver pack is NOT part of the `regolith` wheel (AD-2: one
wheel, no version skew -- a scipy/meshing/FEA dependency stack would
break that promise and bloat every install). OWNER DECIDED
(2026-07-05): it lives in its OWN repository, sibling to this one
(`../feldspar`), with its own `pyproject.toml` -- the stronger form
of the separation this section originally proposed (`packs/<name>/`
in-monorepo was the fallback and remains the pattern for future
packs that want lower friction). The regolith repo keeps the
CONTRACT: a pack-protocol conformance test suite (`tests/packs/`)
that any pack runs against itself.

Name: **feldspar** -- CONFIRMED by owner (2026-07-05), joining the
geology theme (precedent D78/D80/D81). The name may appear only in
the feldspar repo itself and in docs/WO prose here; regolith code
never hard-codes pack names (discovery is by entry point).

### D-G: the invariant enters the ledger with its implementation

The new guarantee ("computed evidence is attributable: a verdict's
producing solver and version are cryptographically attestable, and
trust floors apply to computed evidence") becomes **INV-28 evidence
attribution** in `docs/regolith/13-invariants.md` in the SAME change
as the WO-21 implementation, with its proof argument -- per the house
rule. LANDED (WO-21): INV-28 is now in the ledger, enforced by
`harness/attest.py` verification and the orchestrator release gate.
Proof argument (as filed): the signature is over the AD-18
content address, whose collision resistance is blake3's; the tier is
decided by the consumer key set (INV-14 argument, unchanged); the
invalid-signature path is total because verification returns a
three-valued result (valid-with-tier / absent / invalid) and both
non-valid arms map to explicit evidence states.

## 2. Public API (Python, `regolith.harness`)

```
# discovery (plugin.py)
class PackInfo(BaseModel):            # frozen
    name: str                         # entry-point name == pack name
    version: str                      # distribution version
def load_packs(registry: ModelRegistry) -> Result[tuple[PackInfo, ...], PackLoadError]
    # discovers group "regolith.model_packs", calls each register();
    # sorted-by-name order; duplicate model id across packs is an Err

# subprocess adapter (adapter.py)
class SolverSpec(BaseModel):          # frozen
    argv: tuple[str, ...]             # the wrapper executable + args
    signature: ModelSignature         # what it matches (existing type)
    domain: DomainGuard               # validity domain (existing type)
    cost_s: float                     # declared cost for best-path search
    deterministic: bool               # INV-10 hash-input flag
    timeout_s: float                  # wall clock; expiry -> adapter_error
class SubprocessSolverModel(Model):
    def __init__(self, spec: SolverSpec) -> None
    # discharge() inherited: serialize request -> child -> SolverResponse
def solve_via_subprocess(spec: SolverSpec, request: DischargeRequest)
        -> Result[SolverResponse, AdapterError]

# signing (attest.py; schema type is Rust-generated, AD-5)
def sign_evidence(evidence: Evidence, key: SigningKey) -> Attestation
def verify_attestation(evidence: Evidence, att: Attestation | None,
        keys: TrustKeySet) -> AttestationStatus
    # AttestationStatus = Valid(tier) | Unsigned | Invalid(reason)
```

## 3. Data models crossing boundaries (Rust-sourced, AD-5)

Defined in `regolith-oblig`, exported via schemars like every shared
schema; `SCHEMA_VERSION` bumps.

```
SolverResponse { value: f64bits, eps: f64bits, coverage: Coverage,
                 solver_version: str, settings_digest: str | null,
                 domain_ok: bool, note: str | null }
Attestation    { model_id: str, pack_name: str, pack_version: str,
                 key_id: str, algorithm: "ed25519",
                 signature: bytes (base64 in JSON) }
```

`Evidence` itself is UNCHANGED (D-E: attestation is an envelope; the
evidence cache rows gain an optional attestation column).

## 4. Error types

| type | variants | maps to |
|---|---|---|
| `PackLoadError` | `DuplicateModelId`, `EntryPointRaised`, `BadRegisterSignature` | build-level diagnostic; the pack is skipped, named in the report; never a silent partial load |
| `AdapterError` | `SpawnFailed`, `Timeout`, `MalformedResponse`, `SchemaVersionMismatch`, `NonzeroExit` | `harness.adapter_error` indeterminate evidence (like `harness.no_model`) |
| `AttestationStatus.Invalid` | `BadSignature`, `UnknownKey`, `AlgorithmMismatch` | indeterminate + its own diagnostic family (D-E) |

All returned as typani `Result`s / values per house rules; exceptions
remain programmer bugs only.

## 5. Dependencies

- `cryptography` (ed25519 sign/verify) -- Python side only; boring,
  maintained. Rust defines the Attestation SCHEMA only (no signing in
  the core: keys and processes are "talking to the world", AD-1).
- `importlib.metadata` entry points (stdlib) for discovery.
- Existing: quarry `trust.py` key sets (extended with local signing
  keypairs under `.regolith/keys/`, gitignored), AD-18 content
  addressing, the harness registry/evidence modules.

## 6. Integration points

- `default_registry()` calls `load_packs` (composition point).
- `orchestrator.discharge` attaches attestations after model
  discharge when a signing key is configured; `orchestrator` verifies
  at evidence-cache READ and the release gate enforces per-claim
  trust floors (regolith/11 sec. 7) against `AttestationStatus`.
- `quarry` trust key sets gain key DESIGNATIONS (which tier a key
  confers) -- same file, same INV-14 semantics as record signing.
- The Phase E separate-process split reuses `adapter.py`'s wire
  protocol with the whole registry behind it.
- WO-27 (feldspar) is the contract's first external consumer; its
  conformance run in `tests/packs/` gates the protocol's stability.

## 7. Feldspar-recorded asks (2026-07-07)

Owner-reviewed seam questions from the feldspar side
(`../feldspar/docs/feldspar/08-open-questions.md`); each needs a
regolith-side decision or schema change. Recorded here because this
doc owns the pack contract; none is committed regolith scope until a
WO picks it up.

1. **Claim-kind naming for tier competition** (feldspar OPEN-6): for
   FEA models to compete with closed-form models in ONE best-path
   graph (D-A), they must share claim kinds. Needed: the kind-naming
   ruling (fea-specific kinds vs re-keying onto the closed-form
   kinds), and whether one model may register under two kinds without
   a duplicate-model-id error in `ModelRegistry`.
2. **Coverage encoding** (feldspar OPEN-8): regolith/07 sec. 2 names
   the coverage vocabulary (`corners`, `grid(k)`, `analytic`) but
   `Prediction.coverage`/`Evidence` carry a bare float. Sweeping packs
   cannot state grid coverage until the schema encodes it
   (schema-versioned change in `regolith-oblig`, AD-5). Sharpened by
   the regen-engine test (feldspar G29): 2-D `forall` domains (mr x
   throttle) need `grid(k x m)` or per-axis monotonicity -- the
   encoding should be per-axis from day one. Sharpened again by the
   dune-buggy test (feldspar G43) and calcite COPEN-7: axes may be
   DISCRETE (range states, valve line-ups, circuit-failure states)
   crossed with continuous boxes -- the per-axis encoding must carry
   enumerated domains, not only grids.
3. **Reference-passing channel, GENERALIZED** (feldspar OPEN-2 +
   OPEN-11): `DischargeRequest.inputs` is scalar intervals only.
   Owner direction (2026-07-07): claims should be dischargeable
   across a fidelity hierarchy resolving at the cheapest valid level
   -- so ONE channel should carry hash-pinned, content-addressed
   payload refs of several kinds: WO-22 realized-geometry records,
   cheaper parametric descriptors (letting parametric solvers compete
   with full-geometry ones instead of being bypassed), and the
   regolith/02 sec. 5 time/frequency objects (load spectra, transient
   profiles, masks) -- without which no external pack can ever
   discharge `peak/settles/rms/stays_within` claims. All these are
   already hash-pinned registry/evidence objects on the regolith
   side, so the channel is refs-by-digest, not new payload schemas.
   Touches lowering (what obligations carry) and the request schema;
   coordinate with WO-22/WO-29. Pack-side consumer design: feldspar
   payload ports (`../feldspar/docs/feldspar/09-model-integration.md`
   sec. 4); parametric descriptors should align with feldspar's
   family port vocabulary (feldspar 05/06) so descriptor and
   signature stay the same strings.
4. **Given-resolution contract** (feldspar friction G2, found by
   tracing `examples/mech/sheet_bracket.hem`-class claims through
   the seam): obligations carry NAMES (`given: material: AISI_304`,
   `loads: interface_envelope(...)`) but `DischargeRequest.inputs`
   is `Mapping[str, Interval]`. WHO resolves records to scalar
   intervals -- and at which environment corner (`E: f(T)` over
   `T_env`) -- is unspecified. Needed: a normative resolution step
   (lowering or orchestrator) with rules for (a) property-record
   evaluation over environment boxes, (b) interface-envelope load
   extraction, (c) the port-name vocabulary shared with pack
   signatures, and (d) REGIME TAGS (feldspar audit A-10,
   2026-07-07): `DischargeRequest` has no channel asserting regime
   conditions (`linear_elastic`, `static`, `ideal_gas`) that the
   pack's validity domains require -- today a pack model must treat
   its tags as guaranteed by the claim kind's construction (feldspar
   06 pins that interim rule), which caps how general a claim kind
   can be. feldspar's half (its port vocabulary + reject-unresolved
   rule) is recorded in feldspar 06.
5. **`spice.ngspice` naming** (feldspar OPEN-7, owner decision
   2026-07-07): the electrical numeric tier ships inside feldspar's
   `elec` namespace, not as a sibling pack. regolith/11 sec. 3's
   `spice.ngspice` example stays illustrative only; no regolith code
   change (discovery is by entry point, names are never hard-coded).
6. **Fluid-circuit language home** (feldspar G25, reproduction case
   `../feldspar/examples/lithos/regen_engine/feed_lines.hem`):
   hematite describes solids, cuprite `nets:` are electrical; flow
   topology (manifolds, feed lines, regen jackets: series/parallel
   resistances, plenums, conservation per node) has NO language
   home. Consequence: hydraulic obligations cannot be lowered from
   geometry -- givens are hand-asserted, and an entire fluids solver
   catalog has no source of truth to consume. Strawman in the
   reproduction case: `FluidPort` (through/across pairs) +
   `flownet` (the KCL-like fluids analog of `nets:`). This is a
   LANGUAGE-track design question -- the biggest lithos gap the
   feldspar stress tests found. A full DRAFT spec now exists:
   `docs/calcite/` (calcite, `.calc`, PROPOSED 2026-07-07) --
   media/FluidPort/flownet language, the `flownet` payload kind
   riding item 3's channel, cross-track couplings, COPEN list.
   Needs a design-cycle adversarial read + owner ratification
   (calcite COPEN-1); this item stays open until then.
   DEMAND UPDATE (2026-07-07, feldspar G39): the dune-buggy stress
   test adds three more reproduction circuits written against the
   draft (`../feldspar/examples/lithos/dune_buggy/{cooling,`
   `fuel_system,brake_hydraulics}.calc`) -- a coolant loop
   (thermostat states, HxSegment zone coupling), a fuel feed
   (vapor lock = pv(T) NPSH-analog), and a brake circuit whose
   pressure IMPOSER is another track's mechanical output and whose
   compliance budget is COPEN-5's question made mainstream.
   Ratification now blocks four fixtures, not one.
7. **Computed zone-valued fields** (feldspar G23, reproduction case
   `../feldspar/examples/lithos/regen_engine/chamber.hem`): the
   torch igniter ASSERTS zone wall temperatures as boundary givens;
   a regen chamber COMPUTES them, and sibling claims consume them
   (`sigma_y(T_local)`; FEA takes the temperature FIELD as a load).
   No language/lowering form exists for claim-computed zone fields
   feeding other claims' givens -- today it degenerates to worst-zone
   scalar claims with hand-carried conservatism. Interacts with
   regolith/02 sec. 4 zones and item 3's payload channel (`field`
   payloads are the transport half; the LANGUAGE half is open).
   GENERALIZED (2026-07-07, feldspar G36, dune-buggy test): the
   index axis of a computed field may be a CONFIG variable, not
   only space -- suspension camber(travel)/toe(travel)/motion-
   ratio(travel) curves are computed by kinematic solvers and
   consumed by sibling claims (including bounds on the curve's
   SLOPE). One design should cover zone-indexed and config-indexed
   computed fields; today both degenerate to worst-point scalar
   claims.
8. **Wiring-harness routing home** (feldspar G42, reproduction case
   `../feldspar/examples/lithos/dune_buggy/electrical_power.cupr`):
   voltage-drop, ampacity-derating, and weight claims need
   conductor LENGTHS, bundle membership, and connector environment
   classes. Hoses get hematite TubeRun geometry + calcite
   elaboration extraction; a WIRE RUN (routed path along structure,
   bundle grouping) has no language home in any track, so lengths
   and bundle factors are hand-asserted givens that nothing
   invalidates when the layout changes. Needed: a routing
   declaration (cuprite-side, or a shared routed-line core with
   calcite -- COPEN-2's generalized net machinery is the natural
   host) whose elaboration emits the lengths/bundles as lowered
   givens, exactly as calcite 03 sec. 1 extracts hydraulic
   parameters from realized geometry.
