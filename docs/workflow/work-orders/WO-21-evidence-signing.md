# WO-21: Evidence signing (solver attestation + trust floors)

Status: done
Depends: WO-20, WO-16 (magnetite trust key sets)
Language: both -- Rust `regolith-oblig` (Attestation schema only),
Python `regolith.harness`/`regolith.magnetite`/`regolith.orchestrator`
Spec: regolith/11 sec. 7 + sec. 10.6 rule 4; regolith/13 INV-14,
INV-22; design: `../../spec/toolchain/20-solver-abstraction.md` D-E/D-G, AD-20

## Goal

Every solver can sign the evidence it produces; the orchestrator
verifies attestations against the consumer's magnetite key set, maps
them onto the existing evidence-class tiers, and the release gate
enforces per-claim `trust: >= tier` floors on computed evidence.
Delivers the new guarantee INV-28 (evidence attribution) INTO the
ledger with its proof argument, same change (house rule).

## Deliverables

- `Attestation` schema in `regolith-oblig` (model id, pack
  name+version, key id, algorithm `ed25519`, signature bytes);
  schemars export; `SCHEMA_VERSION` bump. Evidence itself UNCHANGED
  (envelope, AD-20); the evidence-cache row gains an optional
  attestation column.
- `harness/attest.py`: `sign_evidence` (over the AD-18 content
  address), `verify_attestation` returning total three-valued
  `AttestationStatus` = `Valid(tier)` | `Unsigned` | `Invalid(reason)`.
  `cryptography` dependency (ed25519).
- Magnetite trust extension (`magnetite/trust.py`): key DESIGNATIONS -- a
  local key set entry names the tier a key confers
  (certified/tested); local signing keypair management under
  `.regolith/keys/` (gitignored; never committed, never logged).
- Orchestrator wiring: attach an attestation at discharge when a
  signing key is configured; verify at evidence-cache READ; the
  release gate refuses a claim whose trust floor exceeds its
  evidence's conferred tier (unsigned = community). `Invalid` maps
  to indeterminate with its own diagnostic family -- never violated,
  never accepted.
- **INV-28 ledger entry** in `docs/spec/regolith/13-invariants.md` with
  the proof argument drafted in the design doc (D-G), plus its test
  column naming the fixtures below.
- Docs: harness doc section; `../../spec/toolchain/20-solver-abstraction.md` status flip.

## Acceptance

- Signed-evidence round trip: discharge -> sign -> cache -> reload ->
  `Valid(tested)` under a designated project key; the cache key is
  IDENTICAL with and without the attestation (envelope property).
- Tamper fixture: flip one byte of cached evidence -> `Invalid` ->
  indeterminate (distinct from violated in report and exit code).
- Trust-floor fixture: a claim with `trust: >= certified` over
  evidence signed by a `tested`-designated key is refused by the
  release gate; re-designating the key `certified` (consumer-side
  change only) flips it -- INV-14 semantics on computed evidence.
- `tests/invariants/test_inv_28_*.py` real and green (honest pass +
  deliberate violation); no xfail, no stub.
- `make check` green; `make schema` drift-clean.

## Deviations

- `SCHEMA_VERSION` 4 -> 5 lives in `regolith-util/src/canon.rs`
  (outside this WO's nominal crate list); authorized per AD-18, same
  precedent as WO-20.
- Golden corpus fixtures (`tests/golden/data/{buck_converter,
  cubesat,gear_reducer}.json`) regenerated -- required by the schema
  bump; pure hash replacements, no structural change.
