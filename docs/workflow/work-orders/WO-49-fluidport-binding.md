# WO-49: `impl FluidPort<medium=...>` binding + FOPEN-1 medium-mismatch

Status: todo
Depends: WO-31/WO-32 (done -- the fluorite surface + lowering this
completes), WO-22 engine half (done -- the hematite realizer side
the binding touches). This is the WO-32 close-out's named blocker,
scoped: FOPEN-1 was correctly NOT implemented in WO-32 D5 because
no `impl FluidPort<medium=...>` binding existed to check against
(coordinator memory, cycle-24 UPDATE 4; `FlownetPayload`/
`MediumRef`'s own doc comment: "FOPEN-1 is enforced upstream of
construction").
Language: Rust (`regolith-syntax` if any binding surface is still
opaque, `regolith-lower` for resolution + the check) + fixtures.
Spec: docs/spec/fluorite/02-language.md (FluidPort, media),
docs/spec/fluorite/04-open-questions.md FOPEN-1 (the deferral being
closed -- flip it in the same change), docs/spec/hematite/02-language.md
sec. 6 (cavity/wetted surface -- the mech side of a fluid
boundary), regolith/04 (impl binding); WO-32's close-out notes;
`examples/negative/40_*.fluo` (the EXPECT-TODO fixture this
un-todos).

## Goal

A component's fluid ports bind to media for real: `impl
FluidPort<medium=...>` declarations resolve edge -> component ->
medium, so a flownet whose endpoints disagree on medium is caught
BEFORE payload construction (the structural
cannot-represent-mixed-media property stays true), with a
constructive diagnostic naming both media and both declaration
sites. Fixture 40 flips from EXPECT-TODO to a real E-code.

## Deliverables

1. Binding resolution: `impl FluidPort<medium=...>` (and the
   corpus's existing spellings -- inventory them FIRST; if the
   corpus and fluorite/02 disagree on a spelling, escalate, do not
   pick) resolved during fluorite lowering into a per-port medium
   table.
2. The FOPEN-1 check: per flownet edge, endpoint media must agree
   (compatible per the media records' declared compatibility, not
   string equality -- water/water_glycol is a RECORD question);
   mismatch is a new diagnostic in the FluidNet family (E020x block,
   beside E0203), pre-payload (the payload stays structurally
   single-medium).
3. Fixture 40 un-TODO'd to `# EXPECT:` its code; an honest-pass
   sibling; a compatibility-record positive case.
4. fluorite/04 FOPEN-1 entry flipped to closed-with-citation; the
   `MediumRef` doc comment's "enforced upstream" now names the
   enforcing pass.

## Acceptance criteria

- Mixed-media net -> the new diagnostic naming both sides; clean
  and record-compatible nets pass; no golden churn on the existing
  fluorite corpus (it is single-medium throughout).
- `make check` green; WO-32's Status line updated from
  PARTIAL-DONE to done in the same change (this was its only open
  item).

## Non-goals

- Multi-medium mixing components: now SPECIFIED (D142, cycle 27:
  `Mixer(outlet=<medium>)`, fluorite/02 sec. 3) and implemented by
  WO-52, which plugs the mixer's medium-boundary treatment into
  THIS WO's consistency check -- still not this WO's scope; land
  WO-52 after or together.
- Cavity-derived wetted-path lowering (hematite/07 sec. 2a deferral
  stands; D130's declared flow_paths are the v1 producer).
