# WO-96 -- Assembly/build instructions producer

Status: todo (dispatch AFTER the D197 preview verb merges -- shares
  the producer-invocation seam)
Language: Python (backends + orchestrator read-side)
Spec: D199 (the ruling this executes); D197 (preview/ship
  consumer split); WO-62 (RealizedAssembly: mates, placements);
  WO-50 (drawings backend + quality-audit posture); WO-54/WO-63
  (itemized evidence / parity report precedents for document
  honesty); regolith/07 sec. 6 (backends never decide).

## Goal

`regolith preview`/`ship` can emit ASSEMBLY INSTRUCTIONS: an
ordered, viewable build document derived entirely from proven
pipeline data. No invented content: order from the mate graph,
parts from the BOM/manifest, fastener callouts (with torque) only
where a discharged bolted-joint/bearing claim supplies the number.

## Deliverables

1. `AssemblySteps` producer (backends/, beside the drawings/
   diagram producers): consumes a build's RealizedAssembly payload
   (mate graph + placements) + manifest/BOM rows + discharged
   evidence index. Emits the machine-readable steps JSON: ordered
   steps, each {step n, action (place/fasten), part refs, mate
   ref, fastener ref + torque + evidence hash where available,
   unordered-parts callout section for anything the graph cannot
   order}. Topological order over mate dependencies, base part =
   the mate-graph root (document the tie-break rule; deterministic,
   INV-10 posture).
2. Renderer to the human document (one renderer for it -- pick the
   repo's existing document-rendering idiom; check what docsgen
   and the drawings renderer already use before adding ANY new
   dependency). PREVIEW consumers get the D197 gate stamp;
   ship consumers require the release gate as always.
3. Wiring: `preview --out` includes instructions when a
   RealizedAssembly exists; `ship --spec` gains an "instructions"
   block (subject list), refused content-free.
4. Tests: a fixture assembly (the WO-62 exemplar or printer XY
   gantry) produces deterministic steps JSON (golden) + rendered
   document; mate-cycle fixture renders the honest unordered
   callout; torque callout appears ONLY with discharged joint
   evidence (test both ways).
5. Docs: guide section (where preview/ship are documented);
   docstrings.

## Acceptance criteria

- `regolith preview <flagship-with-assembly> --out DIR` writes
  steps JSON + the document, honestly stamped; deterministic
  across two runs.
- Every number in the document traces to payload/record/evidence
  (spot-check assertion in tests: no literal not present in
  inputs).
- No SCHEMA_VERSION bump (read-side only). `make check` green.

## Dependencies

D197 preview verb (in flight). RealizedAssembly (WO-62, landed).
