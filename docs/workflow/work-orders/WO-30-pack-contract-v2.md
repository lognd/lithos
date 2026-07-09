# WO-30: Pack contract v2 (coverage, payloads, given resolution, kind competition)

Status: done
Depends: WO-20 (plugin layer), WO-21 (signing) -- both done. GATES
WO-27's remaining conformance surface, WO-32 (flownet payload rides
the channel), WO-33 (field payload), and feldspar's M4/M6 milestones.
No file overlap with the WO-29 remainder (may run concurrently).
Language: Rust (`regolith-oblig` schema types, ONE `SCHEMA_VERSION`
bump); Python (`harness/` selection + registry, `orchestrator/`
given resolution + payload store, regenerated `_schema/`)
Spec: `../../spec/toolchain/20-solver-abstraction.md` sec. 8 (NORMATIVE for this WO:
D94-D97, cycle 20) + sec. 7 items 1-4 (the demand record);
regolith/07 sec. 2-3; regolith/13 INV-1/9/10/14; AD-5 (schema
direction of truth), AD-17 (lowering does no IO), AD-18 (content
addressing); feldspar's halves: `../feldspar/docs/spec/06`
(port vocabulary, reject-unresolved, regime interim) and 09 sec. 4
(payload kinds -- adopt the strings verbatim, do not restyle them).

## Goal

One coupled schema change (F100) making four contract gaps real:
structured per-axis coverage, the generalized payload-ref channel,
a normative given-resolution pass with regime tags, and
vocabulary-owned claim kinds with per-kind registration. After this
WO an external pack can state grid/enumerated coverage, receive
hash-pinned geometry/spectrum/flownet refs, rely on a documented
resolution rule for named givens, and compete with built-ins under
shared claim kinds.

## Deliverables

1. **Structured coverage (D95, sec. 8.2).** In `regolith-oblig`:
   `CoverageAxis { axis, domain: Interval | {values: [String]},
   method: corners | grid{k: Vec<u32>} | enumerated | analytic |
   monotone }` and `Coverage { axes: Vec<CoverageAxis>, fraction:
   f64bits }` (schemars-derived, serde snake_case like siblings).
   Replace the bare `coverage_bits: u64` field on `Evidence` and
   `SolverResponse` with `coverage: Coverage`; keep the fraction
   collapse as `Coverage::fraction` (construction helper
   `Coverage::full()` = no axes + fraction 1.0 preserves the
   closed-form precedent). Bump `SCHEMA_VERSION` ONCE for this whole
   WO. `make schema`; Python `Prediction`/`Evidence` consumers move
   to the generated model.
   The SAME single bump also carries three cycle-21 shapes (D102,
   D103, D105(d) -- design-log `2026-07-07-cycle-21.md`; their
   LOWERING/consumer wiring stays in WO-26's remainder, only the
   schema fields land here): `ClaimForm::{Peak, Rms, Overshoot}`
   gain `op: String, rhs: String` (reduction forms take an external
   comparator; `Settles`/`StaysWithin` stay self-contained);
   `Given` gains `refs: Vec<(String, String)>` (entity-field
   reference path -> resolved value-source text, for D103 expression
   givens); lockfile waiver rows gain `match_set: Vec<String>`
   (sorted entity refs at authorship, for the INV-12 growth diff).
2. **Payload-ref channel (D96, sec. 8.3).** In `regolith-oblig`:
   `PayloadRef { kind: String, digest: String, origin: String }`.
   Python `DischargeRequest` (`harness/model.py`) gains
   `payloads: Mapping[str, PayloadRef] = {}`;
   `ModelSignature` (`harness/signature.py`) gains
   `payload_kinds: Mapping[str, str] = {}` (port name -> required
   kind string); registry selection (`harness/registry.py`) treats a
   missing/mismatched payload kind as a non-match (falls through to
   the honest `harness.no_model` path -- never an exception). The
   kind vocabulary is the feldspar 09 sec. 4 string list VERBATIM,
   documented as a module-level constant tuple in ONE place
   (`harness/payloads.py`) with a lint that signature kinds come
   from it. Payload STORE: `orchestrator` gains a minimal
   content-addressed store (`orchestrator/payload_store.py`:
   `put(bytes) -> digest`, `resolve(digest) -> Result[bytes,
   PayloadStoreError]`, blake3, files under `.regolith/payloads/`);
   `DischargeContext` (or the existing discharge call path) passes a
   resolver handle to models. Log every put/resolve at DEBUG.
3. **Given resolution + regimes (D97, sec. 8.4).** In
   `orchestrator/translate.py` (the existing obligation->request
   seam): a `resolve_givens` pass that (a) evaluates property
   records over the environment box -- worst corner via the record's
   per-axis monotonicity metadata when declared, full-domain hull
   otherwise (log which rule fired per given); (b) extracts
   interface-envelope loads through the WO-12 contract IR
   vocabulary; (c) maps names through the shared port-name
   vocabulary (document the vocabulary table in
   `../../spec/toolchain/20-solver-abstraction.md` sec. 8.4 if any string is added --
   feldspar 06 owns the mech strings). Unresolvable names produce a
   typed `GivenResolutionError` value carried into an INDETERMINATE
   discharge naming the given -- never a guess, never an exception.
   `DischargeRequest` gains `regimes: tuple[str, ...] = ()`;
   translate asserts tags from claim-kind construction (start with
   the WO-13 claim-kind table's guarantees: `linear_elastic`,
   `static` for the static mech kinds; extend only where the kind's
   construction genuinely guarantees the tag). `ModelSignature`
   gains `required_regimes: tuple[str, ...] = ()`; selection treats
   a missing tag as a non-match.
4. **Kind competition (D94, sec. 8.1).** `ModelRegistry` keys
   `(claim_kind, model_id)`: registering one model instance under
   two kinds is legal; the duplicate-id error becomes per-kind.
   Registration lints kind strings against a method-word deny list
   (`fea`, `spice`, `cfd`, `ngspice`, `ccx`, `abaqus`, `ansys`) --
   violation is a `PackLoadError`-family registration error value.
   Built-in model kinds are audited: any built-in kind string
   violating the rule is renamed in the same change (with golden
   updates), so the lint ships clean.
5. **Conformance suite.** `tests/packs/` grows cases: a pack model
   registering under two kinds; structured coverage round-tripping
   through evidence + cache; a payload-requiring model matched only
   when the request carries the kind; regime non-match falls to
   no_model; given-resolution unresolved -> indeterminate naming the
   given. These are the cases feldspar runs from outside.
6. **Docs.** `../../spec/toolchain/20-solver-abstraction.md` sec. 8 marked implemented;
   regolith/07 sec. 2 coverage sentence updated to point at the
   structured encoding; `docs/spec/regolith/13-invariants.md` NOT touched
   (no new guarantee -- INV-9/10 proof arguments extend, note this
   in the WO close-out).

## Acceptance criteria

- ONE `SCHEMA_VERSION` bump covers all schema changes (including the
  D102/D103/D105(d) fields); `make schema` regenerates; the drift
  check passes; goldens updated by `make snapshots` (never by hand).
- A sweeping model can state `grid(k x m)` over two axes AND an
  `enumerated` discrete axis, and the evidence round-trips it.
- A request carrying `{"geometry": PayloadRef(kind="geometry.realized",
  ...)}` selects a model whose signature demands that kind; absent
  the payload, selection yields `harness.no_model` evidence.
- `resolve(digest)` returns the exact bytes `put` stored; a missing
  digest is an `Err` value mapped to indeterminate discharge.
- One model registered under `mech.static_stress` AND
  `mech.static_deflection` discharges both; registering two DIFFERENT
  models with one id under ONE kind is still an error.
- Registering kind `mech.fea.static_stress` fails with the D94 lint
  naming the offending word.
- An unresolved given (`material: NOT_A_RECORD`) produces
  indeterminate evidence whose diagnostic names `material`.
- `make check` green; conformance suite green; no `regolith._core`
  imports outside `compiler.py` (guard-core).

## Non-goals

- Feldspar's side of anything (it consumes; its repo moves on its
  own schedule).
- The flownet/field payload PRODUCERS (WO-32/WO-33); this WO ships
  the channel, not the contents.
- Remote discharge transports (Phase E unchanged).
- Coverage-driven PLANNING (the orchestrator does not yet choose
  sweep resolutions; models still decide, regolith/07 sec. 2).
