# WO-13: Claims, obligations, evidence schemas

Status: done
Depends: WO-12

> Cross-ref (ladder): the waiver ledger schema
> (`regolith_oblig::waiver`) is now wired end-to-end by
> `regolith-lower::waivers` (WO-19): `Waiver` carries `target`/`scope`/
> `basis`/`evidence`/`expires`; `WaiverRecord { waiver, kind, matched }`
> is the INV-2 acceptance record (no status) + INV-12 audit surface;
> `WaiverKind` = matched / deferred_rule_pack / stale. `SCHEMA_VERSION`
> bumped 2 -> 3 for the shape change. See TRIAGE BE-9.
>
> Cross-ref (cycle 12): WO-19's depth pass now exercises this schema
> end-to-end -- `Obligation.given` (materials/loads) is populated from
> source (BE-2), and impl/extern/import bindings lower to
> `<upper> conforms <lower>` `Obligation`s (BE-6, INV-13). No schema
> change; the WO-13 model surface was already sufficient.
>
> Cross-ref (INV-13 discharge half): the emitted `conforms` obligation is
> discharged by the Python harness conformance-refinement model
> (`harness.models.conformance`, AD-1) -- it checks the lower impl bound
> refines the upper spec bound. The `conforms` claim form carries the
> binding structure (lhs/rhs); the two refinement windows now travel in
> the obligation's `given.loads` (`conformance_sense`/`spec_bound`/
> `impl_bound`) when both sides declare a leading comparator bound, and
> `orchestrator.translate` lifts them into a `DischargeRequest` -- the
> INV-13/26 bridge, CLOSED cycle 16 (TRIAGE C16). Honest cut: positional
> first-bound extraction; a side with no literal bound leaves the windows
> absent and the orchestrator defers the obligation (never a silent pass).
Language: Rust (`regolith-oblig`; schemars export feeds WO-18) -- see `00-architecture.md` (normative; supersedes Python-specific implementation notes below)
Spec: substrate/07 (all); substrate/02 sec. 5, 7

## Goal

The verification spine's data model: claims lower to self-contained,
serializable obligations; evidence is the only return type. No harness
models in this WO -- schema + lowering + one trivial closed-form
discharger to prove the loop.

## Deliverables

- Claim AST: named claims in `require <Group>:`, `forall <cfg>`,
  `sf=`, `scatter_factor=`, `trust: >= tier`, `@hint`, time/frequency
  forms (`peak`, `settles`, `overshoot`, `rms(band=)`,
  `stays_within(mask)`, windows `during` / `within .. after` /
  `until`), `assume!(expr, basis=)`.
- `Obligation` (substrate/07 sec. 2): claim, content-addressed subject
  ref, `given:` block (materials/loads/backing), hints, `sweep:`
  domains (one obligation carrying the domain). JSON serialization =
  THE interchange format; golden-file it.
- `Signature` registry (inputs/outputs/domain) and `impl <sig> by`
  records with cost + error model + validity domain (data only).
- `Evidence` (status discharged/violated/indeterminate, value + eps,
  margin after error, model id, coverage for sweeps, cost, hash);
  content-addressed cache keyed on (subject, contract, registry
  versions).
- Margin-driven discharge rule implemented once, generically:
  `value + eps_model <= limit`, with one toy closed-form model wired
  end-to-end (e.g. budget-sum recheck) to prove claim -> obligation ->
  evidence -> cache.
- `todo!`/`assume!`/`waive` ledger with `--release` refusal semantics
  (flag on the report; CLI wiring in WO-15). Waivers (substrate 12
  sec. 3): scoped matching against claims/rules, deviation status when
  evidence-carrying, and the stale-waiver check (a waiver matching
  nothing is an error). `model=` claim pins select the discharge
  model; margin math unchanged.

## Acceptance

- Round-trip: lower the examples' claims to obligations, serialize,
  reload, discharge the toy-model subset; cache hit on second run.
- Indeterminate is distinct from violated in every surface (statuses,
  report, exit codes).
