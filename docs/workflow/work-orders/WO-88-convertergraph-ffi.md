# WO-88 -- ConverterGraph execution FFI

Status: done
Language: Rust (regolith-api/-py marshalling) + Python (harness
  consumer)
Spec: F112 ("ConverterGraph execution FFI", verbatim); WO-36 (elec
  behavioral bodies: typed CST -> ConverterGraph, INV-16 -- the
  graph EXISTS in Rust and is tested there); cuprite/08 (behavioral
  semantics); AD-4 (one coarse FFI boundary; regolith-py is
  marshalling ONLY); AD-22 (ordinary build door).

## Goal

WO-36's ConverterGraph is landed and tested Rust-side but never
crosses the FFI, so no Python harness model can evaluate a
behavioral body (buck converter duty/ripple models consume
hand-supplied parameters instead of the compiled graph). Expose
the graph through the existing coarse boundary and wire ONE
consumer to prove the seam.

## Deliverables

1. VERIFY FIRST: what the BuildPayload already carries for
   behavioral bodies (grep the payload schema for converter/graph;
   WO-36's close-out names its output surface). If the graph
   already rides payload_json, the FFI work is ZERO and this WO
   is Python-side consumption only -- report that finding and
   proceed accordingly (the WO-89 pattern: verification may
   dissolve the premise).
2. If a crossing is genuinely needed: serialize the graph through
   the EXISTING payload channel (schemars type, which means THIS
   WO owns a 27->28 SCHEMA_VERSION bump -- D168: confirm nothing
   else is bumping, regenerate via make schema, never hand-edit).
   regolith-py stays marshalling-only.
3. One consumer: the buck-converter model family (harness/models/
   buck_*.py) resolves its topology parameters FROM the compiled
   graph when present (hand-supplied inputs remain the fallback,
   honestly labeled in evidence provenance).
4. Corpus proof: one existing behavioral-body design (grep the
   corpus for the WO-36 grammar) discharges or defers MORE
   SPECIFICALLY through the graph path; census before/after.
5. Tests both sides; goldens via make targets; docs (cuprite guide
   note + WO-36 ledger annotation).

## Acceptance criteria

- A committed test proves graph-derived parameters reach a
  DischargeRequest (no hand-supplied duplicates).
- Zero lowered->deferred fleet-wide; make check green; the schema
  decision (bump or no-bump) explicitly reported with evidence.

## Dependencies

WO-36 (landed). Serializes with any other schema-bumping WO (none
in flight).
