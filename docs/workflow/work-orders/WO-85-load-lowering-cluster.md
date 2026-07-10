# WO-85 -- Load-lowering cluster: member-targeted loads, axial demand, aggregates, embedment

Status: done
Language: Rust (regolith-lower, schema) + Python (orchestrator)
Spec: calcite/03 (load cases sec. 4, claims sec. 5); design-log
  2026-07-10-cycle-32 F112 (press/pavilion/barn asks); design-log
  2026-07-10-cycle-33 opener; toolchain/00-architecture.md AD-25
  (payload IRs), D168 train rule (schema bumps serialize);
  feldspar:docs (frame consumer contract, read-only reference).

## Goal

Close the fleet's load-vocabulary gaps, in the sources' own words
(the corpus files carry the honest commentary inline):

- hydro_press frame.calx: "a direct kN/m line load on a beam has no
  landed path" -- member-targeted LINE loads (`N/m`, `kN/m` in an
  `on [member]` clause) do not lower; only area (`kPa`) loads over
  tributary transfers do.
- timber_pavilion frame.calx: point loads on a member endpoint are
  unverified; "axial demand is pinned at 0" in the utilization
  translate path -- column axial demand never extracts.
- `.members.all` aggregate (small_office, hydro_press, pavilion):
  the aggregate form "defers whenever ANY member in the frame is
  indeterminate" -- it must instead partition: discharge what is
  resolvable per-member, defer the rest with per-member reasons
  (mixed roles: girders, columns, braces in one group subject).
- `civil.embedment` claim form (pole_barn ask): declared embedment
  depth vs required (moment/lateral demand at grade), closed-form
  per the calcite/03 claim-form pattern; harness model half rides
  the existing WO-48-deliverable-5 model family.

## Deliverables

1. Grammar/lowering: accept `N/m`-family quantity literals in
   member-targeted `loads:` rows (`on [G1]`) and point-load rows
   (`at <named endpoint/station>` per calcite/03 sec. 4's declared
   grammar -- verify the exact production in the spec and the
   grammar.ebnf before implementing; if the spec lacks the point
   form, STOP and escalate a design-log entry rather than invent).
2. FramePayload v-next: load entries carry kind (area | line |
   point), magnitude+unit, and target (member ref + optional
   station); THE cycle-33 SCHEMA_VERSION bump (26->27) -- this WO
   owns it (D168: anything else bumping serializes behind it).
   `make schema` regeneration, never hand-edits.
3. Demand extraction (Python translate/frame_resolve): line/point
   loads on a resolved member produce bending AND axial demand
   (axial from column-role members' gravity load paths); the
   utilization/deflection translate paths consume them; the "axial
   pinned at 0" comment dies in the same change.
4. `.members.all` partitioning: per-member obligations (or
   per-member verdict rows inside one obligation -- follow the
   existing aggregate posture in translate.py; escalate if neither
   fits) so one indeterminate member no longer defers the whole
   group; per-member deferral reasons preserved.
5. `civil.embedment` claim form end-to-end at the closed-form tier
   (grammar row if calcite/03 already declares it -- verify; lower;
   translate; model; corpus: pole_barn's embedment claim moves from
   deferred to a real verdict).
6. Corpus + goldens: hydro_press line-load path, pavilion point
   load + axial, small_office/.members.all partition, pole_barn
   embedment; regenerate deferral goldens (never hand-edit);
   negative fixtures for malformed load rows (check filename-number
   collisions against master at integration).
7. Docs: calcite guide section update; track-header version bump
   for materially-changed calcite/03 IF its text changes (grammar
   verification may make this doc-only-cite).

## Acceptance criteria

- `regolith build --release examples/flagships/hydro_press_h30`
  and `timber_pavilion` each discharge at least one previously
  load-blocked obligation (compare F114 sweep logs); no previously
  discharged obligation regresses anywhere in the corpus.
- `.members.all` groups report per-member outcomes; a group with
  one unresolvable member no longer defers wholesale.
- SCHEMA_VERSION 27 lands once, with `make schema` output
  committed; schema-check green.
- `make check` green; `make install` before it (Rust + schema).

## Dependencies

WO-84 (record paths -- landed; the demand extraction consumes
resolved sections). Serializes with any other schema-bumping WO
(none in flight). feldspar checkout is read-only reference; its
frame-consumer extension is feldspar-side follow-up, recorded not
implemented.
