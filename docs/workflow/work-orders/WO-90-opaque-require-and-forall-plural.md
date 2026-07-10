# WO-90 -- Multi-line opaque-require capture + bare-plural forall trap

Status: done
Language: Rust (regolith-syntax, regolith-lower) + goldens
Spec: F112 (reaction_wheel/dune_buggy routing ask; boards/
  assemblies trap); F115 addendum (arm_a6/reaction_wheel/
  regen_engine/dune_buggy are the still-zero mech projects, and
  their dominant blocker is this cluster); WO-92 close-out (the
  uav "multi-line-truncated mech.deflection(...)" note); WO-68
  (the forall lowering this WO's diagnostic guards); hematite/04
  (one word one idea -- diagnostics teach, never guess).

## Goal

Two parser-level honesty gaps:

1. MULTI-LINE OPAQUE-REQUIRE CAPTURE: a `require:` (or claim)
   expression that spans multiple physical lines is truncated at
   the first line break by the layout/claim capture, so the
   remainder is silently lost and the claim defers as
   `unsupported_op` (or worse, lowers a truncated predicate).
   reaction_wheel and dune_buggy's routing requires and uav's
   wrapped `mech.deflection(...)` are the recorded victims. Find
   the exact capture point in the layout pass / claim reader
   (regolith-syntax) and extend capture across continuation lines
   per the layout rules the track specs actually declare (verify
   what the specs say about continuation -- indentation-based
   continuation is the existing layout posture; if NO continuation
   rule is declared in any spec, STOP and escalate the rule as a
   design-log question instead of inventing one).
2. BARE-PLURAL FORALL TRAP: `forall b in boards:` (or
   `assemblies`) where the bare plural names NO declared domain
   silently yields an empty domain -- zero obligations, a silent
   pass. Emit a constructive diagnostic (new E-code from the
   registry's next free number) naming the empty/unknown domain
   and the declared domains in scope ("did you mean
   registry(<family>) or <Entity>.members.all?"). An explicitly
   EMPTY declared domain stays legal (empty sweep = zero
   obligations, honest); only an UNDECLARED bare-plural name trips
   the diagnostic.

## Deliverables

1. The capture fix with Rust unit tests: single-line unchanged
   byte-identical; two-line and three-line predicates capture
   whole; CRLF twin fixtures (the cycle-28 lexer posture).
2. The E-code diagnostic + negative fixtures (check numbering
   against master at integration; master currently ends at 68).
3. Corpus: reaction_wheel/dune_buggy/uav_talon/arm_a6/regen_engine
   release builds before/after -- report which unsupported_op /
   silent-empty families move to lowered or to the new diagnostic;
   goldens/deferral corpora regenerated, never hand-edited. Any
   NEWLY LOWERED claim that then VIOLATES is reported loudly in
   the close-out, never tuned away.
4. Docs: the layout/continuation rule made explicit in the track
   spec section that owns layout (with header version bump) if the
   fix required interpreting it; guide mention only if user-facing
   behavior text exists.

## Acceptance criteria

- The recorded victims' multi-line requires lower whole (show the
  before/after obligation for one of each).
- `forall x in boards:` with no declared `boards` domain is a
  constructive diagnostic, not a silent zero-obligation pass;
  WO-68's declared-domain forms are untouched (its tests stay
  green).
- No SCHEMA_VERSION bump. `make check` green.

## Dependencies

WO-85/WO-92 landed (their goldens are the base). Serializes with
anything editing the layout pass (nothing else in flight touches
it; WO-87 is in the lower entity pass).
