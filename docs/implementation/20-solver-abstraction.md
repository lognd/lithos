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
break that promise and bloat every install). It lives in
`packs/<name>/` at the repo top level with its own `pyproject.toml`
(excluded from the regolith build; movable to its own repository
later without history surgery). The regolith repo keeps the CONTRACT:
a pack-protocol conformance test suite (`tests/packs/`) that any pack
can run against itself.

Working name: **feldspar** (geology theme). NAMING IS OWNER'S CALL
(precedent D78/D80/D81) -- the name is a placeholder until confirmed;
nothing may hard-code it outside the pack's own directory.

### D-G: the invariant enters the ledger with its implementation

The new guarantee ("computed evidence is attributable: a verdict's
producing solver and version are cryptographically attestable, and
trust floors apply to computed evidence") becomes **INV-28 evidence
attribution** in `docs/regolith/13-invariants.md` in the SAME change
as the WO-21 implementation, with its proof argument -- per the house
rule, it is NOT added now, because nothing enforces it yet. Draft
proof argument for that change: the signature is over the AD-18
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
