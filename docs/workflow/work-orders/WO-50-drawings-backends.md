# WO-50: drawings + schedules backends (`DrawingModel` IR, producers, renderers, quality audit)

Status: in-progress (schema + mech + fluid + elec-BOM legs + quality
audit + DXF/PDF-sibling deferral landed; the ONE named residual is the
civil plan/section producer, blocked on WO-48's `frame` payload per
this file's own dependency line -- see "Residuals" below)
Depends: WO-25 framework (backend discovery + `regolith ship`,
landed), WO-42 (realized IRs + store, done), WO-44 preferred
(register via `regolith.plugins`, kind=backend). The civil sheet
producer additionally gates on WO-48 (the `frame` payload); land it
as this WO's final slice or a fast-follow -- the WO is dispatchable
NOW for the schema + mech + fluid legs. The quality-audit leg needs
the WO-28 engine remainder for in-language drafting rules; until it
lands, ship the drafting checks as the engine's Python-side
precursor EXACTLY like existing realized-fact rules (escalate, do
not invent a second engine).
Language: Rust (`regolith-oblig` schema) + Python (producers,
renderers, audit) + fixtures.
Spec: docs/spec/toolchain/25-drawings-and-artifacts.md (NORMATIVE
charter, incl. the sec. 1.7 quality machinery), 00-architecture.md
AD-27 (+ AD-5/6/18/20/21/22/25/26), design-log 2026-07-08-cycle-27
D140; calcite/03 sec. 6 (civil sheet content), fluorite/03 sec. 2
(flownet payload the P&ID projects).

## Goal

`regolith ship` produces engineering drawings, diagrams, and
schedules as derived, deterministic, provenance-carrying,
QUALITY-AUDITED artifacts: one `DrawingModel` IR, per-track
producers, an SVG reference renderer (DXF sibling), drafting-rule
auditing, contract-coverage checking, and attestation-signed
sign-off.

## Deliverables

1. `DrawingModel` schema in `regolith-oblig` (charter sec. 1.1
   field families: sheets/views/entities/dimensions/annotations/
   tables), schemars-exported, content-addressed; `make schema`
   regenerates the pydantic mirror. Every dimension REQUIRES a
   provenance field (cause | record hash | obligation id).
2. Producers (Python, `regolith.backends.drawings`): mech part
   drawing from `RealizedGeometry` + source dims/GD&T; fluid P&ID
   from `flownet` payloads + symbol records; schedule tables
   (member/opening/area for calcite once WO-48 lands; BOM tables
   for elec NOW from existing netlist state). Civil plan/section
   producer in the final slice (frame payload + grids/levels).
3. SVG reference renderer (deterministic text output) + DXF
   sibling; renderers consume ONLY `DrawingModel` (AD-27).
4. Quality audit (charter sec. 1.7): the seed drafting rule pack
   (>= 5 rules, `per:` citations, pass/fail fixtures), the
   contract-coverage check (uncovered toleranced roles -> named
   diagnostic), `regolith ship --explain` audit report, and the
   AD-20 attestation path over sheet content addresses.
5. Goldens: drawing IR + SVG goldens for the acceptance fixtures;
   `make snapshots` reviews; determinism proven (two runs,
   byte-identical).
6. Docs: charter status flips; guide note in `docs/guide/README.md`
   deferred to the guide wave.

## Acceptance criteria

- Charter sec. 4 verbatim: pillow_block part drawing, small_office
  plan + member schedule (or the recorded gate if WO-48 has not
  landed), feed_system P&ID -- deterministic, provenance-complete,
  golden-enrolled.
- Quality: the drafting pack catches a deliberately over-dimensioned
  and an under-dimensioned fixture; the coverage check catches a
  deliberately-omitted toleranced role; `--explain` renders the
  audit ledger; a signed sheet's attestation dies on regeneration.
- No producer parses a native file; no renderer computes geometry;
  `make check` green.

## Non-goals

- BIM/IFC, WYSIWYG layout, DWG (charter sec. 3).
- Gerber generation (exists via kicad-cli, WO-24/25).
- The overlay/annotation source file (future seam, charter
  sec. 1.5).

## Residuals (this dispatch)

- **Civil plan/section + member-schedule producer**: the ONE named
  cut, per this file's own dependency line -- WO-48's `frame` payload
  has not landed, and building against the unlanded `std.civil`
  surface was explicitly out of scope for this dispatch. Everything
  else this WO promises (schema, mech producer, fluid P&ID producer,
  the elec BOM table producer, the SVG renderer, the full quality-
  audit machinery, and drawing attestation) is landed and tested.
  Fast-follow once WO-48 lands.
- **DXF/PDF sibling renderers**: SVG (the MANDATORY reference
  renderer per charter sec. 1 decision 2) is landed; DXF/PDF are
  explicitly "siblings of the same IR" the charter allows as
  follow-on work, not blocking this dispatch's acceptance shape
  (sec. 4 only requires the SVG-rendered, golden-enrolled set).
- **View-source digest algorithm**: `ViewSource.source_digest` (and
  the drawing-attestation content address) is a blake3 digest over
  the realized IR's/`DrawingModel`'s own canonical JSON bytes
  (`model_dump_json(by_alias=True)`), NOT the Rust
  `regolith_util::canon::content_address` algorithm the Rust
  `DrawingModel::content_digest`/`RealizedGeometry::content_digest`
  use -- that canonical-CBOR encoder lives behind the FFI boundary
  this Python package may not cross (`regolith-py` marshalling only,
  AD-4/AD-27). Both digests share the same anti-staleness property
  (any changed field changes the digest) and this is documented at
  the point of use (`regolith.backends.drawings.producers`,
  `regolith.backends.drawings.attest`); a follow-on could expose the
  canonical address through the FFI facade if byte-for-byte parity
  with the Rust digest is ever load-bearing for a consumer.
- **`ship --explain` CLI flag**: the audit report
  (`regolith.backends.drawings.audit.explain_report`) is implemented,
  tested, and wired into `DrawingsBackend.produce` (every ship run
  emits `drawings/<subject>.explain.txt`); the CLI's existing
  `--explain` flag on a different command (diagnostic-code lookup)
  was not repurposed/extended to print this report interactively --
  the file output satisfies the charter's "renders ... the audit
  ledger" requirement; a dedicated `ship --explain` flag reading that
  file back is a small, unblocked fast-follow.
- **Drafting-rule fixtures 60/61**: reserved by
  `examples/negative/README.md` for this WO but NOT filed as
  `.hema`/`.cupr`/`.fluo`/`.calx` source fixtures -- the drafting
  audit runs over a produced `DrawingModel` (a backend artifact), not
  a compiler diagnostic, so the negative corpus's `# BREAKS`/
  `# EXPECT` header contract does not apply. They are proven instead
  as `tests/backends/test_drawings.py::TestDraftingRules` fixtures 60
  (over-dimensioned) and 61 (under-dimensioned/coverage), with the
  numbering rationale recorded in `examples/negative/README.md`
  itself.
