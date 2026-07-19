# WO-164 -- the realizer capability registry (AD-47)

Status: open (Depends: WO-160, WO-161 [both touch the artifact-family/
  provenance shape a capability's `artifact_families` field points
  at -- land the registry AFTER those two so it can reference the
  final registration shape, not a moving target]; does not depend on
  WO-159/162/163, which touch different seams)
Language: Python (`python/regolith/backends/` or a new
  `python/regolith/capabilities.py` module -- pick the home and say
  why in close-out; likely alongside `registry.py` since it is a
  registry-shaped concept).
Spec: `docs/spec/toolchain/44-boundary-charter.md` sec. 5 (AD-47, the
  full `RealizerCapability` field list, quoted verbatim below).

## Goal

Add the ONE registration type that makes "add a manufacturing/
generation capability" a single, checklist-refused registration
instead of an unwritten list of places to touch:

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

A capability registration MISSING any field is refused at
registration time (raise/return an error at import/registration time,
not a silent None) -- "wire EDM support" (WO-166) cannot land as a
code path without its process records, DFM checks, and provenance
story landing with it, because the registry mechanically enforces
that every field is populated.

## Deliverables

1. The `RealizerCapability` pydantic model (`ConfigDict(frozen=True)`),
   one field per the charter's list above, each typed against the
   REAL existing types it references (`program_kind`: whatever
   sentinel/enum identifies an L1/L2 program IR class today;
   `realized_kind`: the kind-string convention `put_realized_*`
   functions use, per WO-163; `artifact_families`: a list of
   `ArtifactFamilyRegistration` references per WO-161's shape;
   `tool_adapters`: an ordered list of adapter descriptors, each
   carrying enough to stamp WO-160's provenance tier;
   `process_records`: a stdlib namespace path/glob per AD-37 naming;
   `dfm_checks`: a list of check identifiers from the existing DFM
   check-set machinery (`harness/models/dfm/checks.py`);
   `claim_kinds`: a list of claim-kind identifiers from the existing
   claims vocabulary).
2. A registration function/decorator (`register_capability(...)`)
   that validates every field is non-empty/populated and raises a
   clear, named error (typani `Result` if this is a fallible caller-
   facing API, or a hard `CoreBug`-style exception if it is a
   load-time programmer error -- pick per the house Result-vs-
   exception doctrine and justify) on a missing field.
3. **Retrofit the two existing domains as the first registrations**:
   mech (feature-program realizer, OCCT/STEP path) and elec (KiCad
   two-tier path). This is the acceptance-proving step: if mech and
   elec cannot be honestly expressed in the registry's field set
   without inventing data, the field set is wrong -- fix the type,
   do not fudge the registration. Record any field-shape friction
   found during retrofit in the close-out.
4. A lookup/query surface (`get_capability(domain) -> RealizerCapability
   | None` or similar) that WO-165/166/167 will use to discover a
   domain's process records / DFM checks / tool adapters instead of
   hard-coding them.
5. Docs: a new `docs/spec/toolchain/` section or an addendum to the
   boundary charter's own AD-47 text pointing at the landed module
   (a doc-drift note, not a spec change -- the charter itself is
   already normative).

## Non-goals

- No new domain/capability in this WO (fluid, civil retrofits are
  each capability program's own scope if/when they need it; this WO
  only proves the shape against mech + elec).
- No change to DFM check content or claim vocabulary content -- this
  WO references the EXISTING sets, it does not grow them.

## Acceptance

- `RealizerCapability` model exists with all seven fields, each
  required (no field is `Optional` with a silent default -- if a
  field is legitimately empty for some domain, e.g. `tool_adapters`
  for a fully deterministic realizer, model that as an explicit
  empty-list value the caller had to supply, not an implicit
  default).
- Registering a capability with a missing/empty field raises the
  named error; a test proves this for at least two fields.
- mech and elec are both registered; a test looks each up via
  `get_capability` and asserts every field is non-trivially populated
  (i.e. not just "the field exists," but "the DFM check list is the
  real mech DFM check list," etc.).
- `make check` green.
</content>
