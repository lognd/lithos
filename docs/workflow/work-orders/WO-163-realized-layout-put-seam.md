# WO-163 -- `RealizedLayout` put seam, generalized for board-shaped capabilities (A7)

Status: open (Depends: none new)
Language: Rust + Python (schemars type extension in whichever crate
  currently sources `RealizedLayout` -- `python/regolith/_schema/
  models.py:2749` is the GENERATED mirror, so the schemars source
  lives in Rust; the put-seam function and staged-loop wiring are
  Python). If the schema needs a genuinely new field (see Deliverable
  1), this is a schema-bump candidate: same D211 sequencing note as
  WO-160 -- check WO-147's `Status:` before starting and follow
  whichever branch applies, recording the choice in close-out.
Spec: `docs/spec/toolchain/44-boundary-charter.md` sec. 5 (AD-47,
  "PCB fab-set emission is retrofit INTO this shape... A7's
  `RealizedLayout` put seam is its missing realized_kind emission and
  is a prerequisite ticket"); sec. 6 (known exceptions ledger, A7
  entry).

## Context -- recon correction (read before planning)

The charter's A7 finding, read literally, says the `RealizedLayout`
put seam is "not landed." As of this WO's dispatch, that is NOT
fully accurate for the KiCad path specifically:
`python/regolith/realizer/elec/realized.py:97`
(`put_realized_layout`) exists, is called from
`python/regolith/orchestrator/orchestrate.py:1465` inside the staged
build loop, and stores a `layout.realized`-kind payload keyed by
content digest exactly like the mech `put_realized_geometry`
precedent. The KiCad-routed-board put seam IS landed.

The actual gap AD-47 sec. 5 is naming: `RealizedLayout`
(`python/regolith/_schema/models.py:2749`) is COPPER-BOARD-SHAPED --
it carries a mandatory `copper: CopperSummary` field and a
`kicad_pcb_content_hash` pin, both meaningless for a perf-board
substrate (no etched copper, no `.kicad_pcb` native file -- a
fixed-grid substrate with jumper/wire assignment per D268's
perf-board program). So the real prerequisite this WO must close is:
**a `realized_kind` shape that board-shaped capabilities OTHER than
etched-copper KiCad boards can emit through the same put-seam
pattern**, without breaking the existing KiCad path.

Do not silently "fix" the charter text; name this correction
explicitly in the close-out (it is exactly the kind of honest
recon-vs-ambiguity finding the dispatch protocol asks for).

## Goal

A board-shaped realizer (perf-board today, per WO-165; any future
substrate-and-assignment capability later) can produce a
`realized_kind` payload and put it into the content store through
the SAME pattern `put_realized_layout`/`put_realized_geometry`
establish, without being forced to fabricate a fake `copper`/
`kicad_pcb_content_hash` value.

## Deliverables

1. Decide the shape: either (a) make `RealizedLayout` polymorphic
   (a shared base + KiCad-specific and substrate-specific variants,
   `copper`/`kicad_pcb_content_hash` moved into the KiCad variant
   only), or (b) add a sibling type (e.g. `RealizedBoardAssignment`
   or similar name -- pick one consistent with existing naming, do
   not invent a name colliding with anything in `_schema/models.py`)
   carrying substrate/jumper/wire-assignment fields, with its OWN
   `put_realized_*` function following the exact pattern of
   `put_realized_layout`. Prefer (b) unless the polymorphic refactor
   of (a) is a small, safe, backward-compatible change -- (a) touches
   every existing KiCad-path caller and test; justify the choice in
   the close-out rather than defaulting silently.
2. Whichever shape wins, register its `realized_kind` string
   consistently with how `layout.realized`/`geometry.realized` are
   named today (grep for the kind-string constant).
3. A `put_realized_<kind>` function (Python, `PayloadStore.put`
   fresh-digest, matching the existing two precedents' logging and
   docstring style) plus staged-build-loop wiring analogous to
   `orchestrate.py:1465`'s block, gated behind whichever subject
   selector distinguishes a perf-board-family subject from a
   KiCad-copper-board subject (do not wire it in dead -- WO-165
   consumes this seam, but this WO's own acceptance only requires the
   seam to exist and be unit-tested, not a full perf-board realizer).
4. Docs: `docs/modules/py-realizer.md#elec-realized` (the existing
   `frob:doc` anchor on `put_realized_layout`) gets a new anchor or
   an extended entry for the new/generalized shape.

## Non-goals

- No perf-board realizer logic itself (WO-165).
- No change to the KiCad-copper path's existing behavior or field
  names (backward compatible; existing tests must still pass
  unmodified unless directly exercising the shape this WO changes).

## Acceptance

- A new schemars/pydantic type (or extended `RealizedLayout`) exists
  for a non-copper board-shaped realized kind, with a corresponding
  `put_realized_*` function and at least one round-trip unit test
  (construct -> put -> get by digest -> deserialize, matching the
  existing KiCad round-trip test's shape).
- Existing KiCad-path tests (`test_kicad_real.py` and friends) pass
  unmodified.
- Close-out explicitly states which of (a)/(b) was chosen and why,
  and explicitly corrects the charter's "not landed" framing per the
  Context section above (or, if this WO's author finds the KiCad put
  seam was in fact NOT reachable from the staged loop for some reason
  this planner's recon missed, states THAT instead -- verify before
  writing the close-out, do not assume this WO doc's recon is
  infallible).
- `make check` green; schema bump sequencing note followed if a new
  schemars type was needed (see header).
</content>
