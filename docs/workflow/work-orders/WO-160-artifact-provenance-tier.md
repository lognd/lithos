# WO-160 -- artifact provenance tier (AD-45)

Status: open (Depends: WO-147 [owns the cycle-37 SCHEMA_VERSION bump,
  D211 one-bump discipline] IF AND ONLY IF `ArtifactRow` is a
  schemars-mirrored type; see "Schema bump sequencing" below -- check
  WO-147's `Status:` line before starting and follow whichever branch
  it names)
Language: Python (`python/regolith/backends/artifact_index.py` and
  every producer registration that constructs an `ArtifactRow`); Rust
  ONLY if `ArtifactRow` turns out to be schemars-sourced (see below).
Spec: `docs/spec/toolchain/44-boundary-charter.md` sec. 3 (AD-45);
  `docs/spec/toolchain/38-emission-and-release.md` (AD-36, the three
  emission registries this field rides); D267 (A3 closure).

## Goal

`ArtifactRow` gains a required `provenance` field:

```
provenance:
  tier: real_tool | deterministic
  tool: { name: str, version_digest: str } | null   # required when tier=real_tool, null when tier=deterministic
```

Every producer registration that creates an `ArtifactRow` must supply
this at construction time -- no default, no post-hoc inference. The
fake/real KiCad fork (`python/regolith/realizer/elec/kicad.py` vs.
`fake_kicad.py`) and every future two-tier adapter (wire EDM, CAM
posts, per D268/WO-166) becomes readable from the artifact index
alone: a consumer never infers tier from relpath naming or toolenv
state.

## Schema bump sequencing (read before starting)

1. First, determine WHERE `ArtifactRow` is defined: grep
   `class ArtifactRow` in `python/regolith/backends/artifact_index.py`
   (as of 2026-07-19 recon it is a plain pydantic model there, NOT a
   schemars-mirrored `_schema/` type). If it remains a plain Python
   pydantic model with no Rust schemars counterpart, this WO does NOT
   need a schema bump at all -- add the field directly, no D211
   sequencing note applies, and this WO is fully independent of
   WO-147.
2. If, by the time this WO is dispatched, `ArtifactRow` (or its
   producer-registration contract) HAS been folded into a
   schemars-sourced type (e.g. as part of some other cycle-37 WO's
   scope), then per D211 one-bump discipline this field addition MUST
   ride WO-147's bump, not open a second one. Check WO-147's `Status:`
   line: if WO-147 is still open, add this field as a passenger note
   in WO-147's own body (escalate to the WO-147 dispatcher/coordinator
   rather than editing WO-147 directly from this WO); if WO-147 is
   done, its bump has already closed for the cycle and this field
   change escalates to the coordinator for a decision (next cycle's
   bump, or a named exception) rather than silently opening bump #2.
3. Record whichever branch applied in this WO's close-out explicitly.

## Deliverables

1. `provenance` field on `ArtifactRow` (pydantic, `ConfigDict
   (frozen=True)` per house style), with `tier: Literal["real_tool",
   "deterministic"]` and a nested `tool: ToolIdentity | None` model
   (`name: str`, `version_digest: str`).
2. Update every existing producer registration (`backends/elec.py`,
   `elec_fabset.py`, `mech.py`, `hdl.py`, `firmware.py`, `drawings/`,
   `three_d/`, and any other module constructing `ArtifactRow`
   directly -- enumerate via
   `grep -rln "ArtifactRow(" python/regolith/backends/`) to supply
   `provenance` at construction. The two-tier KiCad fork is the
   worked example: `kicad.py`'s real path supplies
   `tier=real_tool, tool={name: "kicad-cli", version_digest: <digest
   of the observed version string, or the version string itself if
   no digest scheme exists yet -- name which you used>}`;
   `fake_kicad.py`'s path supplies `tier=deterministic, tool=None`.
3. `check_index_consistency` (or wherever the belt-and-suspenders
   consistency gate lives) extended to assert every row's
   `provenance.tier` is set and `tool` is present iff
   `tier=real_tool` -- a missing/malformed provenance is a hard
   failure, not a warning.
4. Docs: `docs/spec/toolchain/38-emission-and-release.md` (or
   wherever `ArtifactRow`'s schema is documented) gets the new field
   documented in the same change.

## Non-goals

- No change to WHICH artifacts exist or how they are classified
  (that is WO-161).
- No retrofit of provenance data for demo `PROOF.md`/`manifest.json`
  committed artifacts beyond regenerating them through the updated
  producers (the D265 churn posture is unchanged).

## Acceptance

- `python -c "from regolith.backends.artifact_index import
  ArtifactRow; ArtifactRow.model_fields['provenance']"` shows the
  field is required (no default).
- Every producer registration test exercising an `ArtifactRow`
  construction (existing test suite) passes with `provenance`
  supplied; a new test asserts a real-KiCad-tier row has
  `tool is not None` and a fake-KiCad-tier row has `tool is None`.
- `check_index_consistency` (or equivalent) has a new negative-path
  test: a row missing `provenance` or a `real_tool` row with
  `tool=None` fails the check.
- `make check` green; if a schema bump was required per the
  sequencing note above, `make schema` diff is committed and
  `schema-check` passes.
</content>
