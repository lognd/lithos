# 44 -- the boundary charter (AD-43..AD-47)

Status: adopted (cycle 38, D267). Normative under
`00-architecture.md`; where an older document contradicts this
charter, this charter wins and the older text is scheduled for
alignment (D267 lists the known instances).

One sentence: lithos is six one-way layers with named, type-shaped
seams; every crossing is a schema or a registration, never a
convention; and every ambiguity in the 2026-07-19 as-built census
(A1..A8) is closed here by construction, by gate, or by a named,
ticketed exception.

## 1. The layer model (AD-43)

```
L0 SOURCE      .hema .cupr .fluo .calx .rgp | stdlib records | magnetite manifests
L1 LOWER       regolith-lower (Rust): parse -> ... -> discharge; pure; BuildPayload out
L2 ORCHESTRATE staged_build fixed point; content store; translate -> DischargeRequest;
               procio (ONLY subprocess seam); harness registry + solver packs
L3 REALIZE     domain realizers: program IR in -> Realized* IR + native bytes out,
               through tool adapters (two-tier); never parse L0 source
L4 EMIT        backend registries (producer/renderer/family) -> dist/ + ledgers
L5 SURFACE     artifact index (D244) -> CLI | graphite | LSP; authoring surfaces
               write L0 ONLY (D259/D260)
```

Rules:

- **One direction.** L(n) may depend on L(n-1)'s published contract
  types; never the reverse; never skip-around (an L5 consumer reading
  L2 internals is the A5 violation this charter exists to kill).
- **Helpers are layer-pinned.** feldspar = an L2 helper behind the
  `regolith.plugins` seam (AD-19/AD-26; verified migrated). stdlib
  records = L0 data. procio = the L2 subprocess utility; any NEW
  realizer that shells out routes through procio from day one or it
  is a named exception like `tools/health` (D264) -- there is no
  third posture.
- **Crossings are artifacts, not calls.** Every seam's contract is a
  schemars/pydantic type or a registration record. If a crossing
  cannot name its contract type, it is not a crossing -- it is a leak.

## 2. Declarative -> realizer boundary (restated + hardened)

Exactly three things cross from the declarative world into a
realizer, all typed, all producer-side:

1. **Obligations/claims**: `BuildPayload` (AD-5, schemars, one
   schema door).
2. **Domain programs**: `FeatureProgram` and siblings. The AD-22
   promotion rule gains teeth (closes A1): a forward-authored
   contract type must carry a `frob:ticket` edge to the OPEN
   promotion ticket for as long as the hand-written form exists;
   promotion closes the ticket and deletes the shadow in the SAME
   change. An open promotion ticket is the honest ledger of
   pre-promotion state (today: `FeatureProgram` extraction in
   `orchestrator/programs.py`, hematite/07 sec. 2a deferral).
3. **Realized-input bytes by digest**: `RealizedInput` (AD-25
   purity: lower() never does IO).

A realizer never parses L0 source, never reads the content store
directly, and demands inputs by TOTAL matching (D96/D97): a missing
payload or regime is a non-match, never an assumption.

## 3. Realizer -> artifact boundary (restated + hardened)

- All emission flows through the three registries (AD-36). A new
  artifact type/format/family is ONE registration -- never a new
  code path.
- **Provenance tier (AD-45, closes A3).** `ArtifactRow` gains a
  required `provenance` field: `tier: real_tool | deterministic`,
  plus `tool: {name, version_digest}` when `tier=real_tool`. The
  producing registration supplies it; the fake/real KiCad fork (and
  every future two-tier adapter: wire EDM, CAM posts) becomes
  readable from the artifact index alone, which is the only surface
  L5 consumers have (D259). No consumer may infer tier from relpath
  or toolenv state.
- **Registration-derived classification (AD-46, closes A4).**
  `classify()`'s relpath patterns move INTO
  `ArtifactFamilyRegistration` (a `path_patterns` field plus
  `kind`/`viewer` mapping). `artifact_index.build_index` classifies
  by consulting the registry; the hand-written dispatcher is deleted.
  `check_index_consistency` remains as a belt-and-suspenders gate but
  can no longer be the only thing holding two independent
  classification paths together, because there is only one path.
- **Dimensioned values**: D262/WO-150 is landed and binding
  (`backends/quantity.DimensionedValue`); every NEW renderer
  interface takes unit-carrying types from day one. INV-34 covers it.

## 4. The UI/read seam: regolith.surface (AD-44, closes A5)

Finding (2026-07-19, confirmed by grep): graphite imports
`regolith.orchestrator.lockfile` and `regolith.orchestrator.
orchestrate` types in `graphite/service/reports.py` and
`graphite/server/routes/build.py` -- a third, un-sanctioned contact
beyond D259's two.

Ruling: the read side gets the same shape the FFI door has (AD-4
precedent). A new module `regolith.surface` is the ONE sanctioned
import surface for external UIs:

- Exports, re-exported by value not by reach-through: the D244
  artifact index models + `build_index`, the report read models
  (`BuildReport`, `StagedBuildReport`), lockfile parse, and nothing
  else. Additions to the facade are reviewed API changes.
- graphite (and any future UI) may import `regolith.surface` and
  NOTHING else from `regolith`. Enforced twice, by machine:
  in graphite's `frob.toml` as `[[policy.forbidden-import]]` rules
  (module = `regolith.orchestrator`/`regolith.harness`/
  `regolith.realizer`/`regolith.backends`/`regolith.compiler`,
  within `graphite/**`), and in this repo by a strata flow claim
  (the graphite consumer node's only inbound edge is from the
  surface node).
- D259's two-contact statement is AMENDED to three: (a) read the
  D244 index, (b) save L0 source text, (c) import `regolith.surface`
  for typed read models. Contact (c) subsumes what (a) already
  intended; the compiler-indistinguishability proof for the write
  side (D261) is unchanged.

## 5. The realizer capability registry (AD-47, the extension seam)

Adding a manufacturing/generation capability today means touching an
unwritten list of places. This charter names the list and makes it a
single registration. A **capability** is:

```
RealizerCapability:
  domain            mech | elec | fluid | civil | <new>
  program_kind      the L1/L2 program IR it consumes
  realized_kind     the Realized* IR it emits (AD-25 discipline)
  artifact_families the AD-36 family registrations it brings
  tool_adapters     ordered tiers: real_tool (procio-invoked) then
                    deterministic fallback; each stamps AD-45
                    provenance
  process_records   the stdlib namespace it consults (AD-37 naming)
  dfm_checks        the check set gating realize (hematite DFM
                    doctrine generalized to every domain)
  claim_kinds       the claim vocabulary it discharges evidence for
```

The registry is the checklist: a capability missing any field is
refused at registration, so "wire EDM support" cannot land as a
code path without its process records, DFM checks, and provenance
story landing with it. The three owner-named capability programs
(D268) are the first consumers: wire-EDM die-set production,
perf-board routing, dwelling wiring. PCB fab-set emission is
retrofit INTO this shape (it already has every field in scattered
form; A7's `RealizedLayout` put seam is its missing realized_kind
emission and is a prerequisite ticket).

## 6. Known exceptions ledger (named, ticketed, nothing silent)

- `tools/health` raw subprocess (D264 exception; unchanged).
- `FeatureProgram` pre-promotion extraction (sec. 2; ticketed).
- `RealizedLayout` put seam not landed (A7; prerequisite ticket for
  the PCB/perf-board program).
- Demo `PROOF.md`/`manifest.json` churn (committed generated
  artifacts; D265 posture unchanged).

Anything else found reaching around a seam is a violation to fix,
not a new exception to record -- exceptions require a D-number.
