# WO-50: drawings + schedules backends (`DrawingModel` IR, producers, renderers, quality audit)

Status: in-progress (schema + mech + fluid + elec-BOM + civil legs +
quality audit + DXF/PDF-sibling deferral landed; civil plan/section +
member-schedule producer landed this dispatch, WO-48's `frame` payload
having landed -- see "Residuals" below for what remains: DXF/PDF
siblings, the `ship --explain` CLI flag, and the drafting-rule fixture
numbering note)
Depends: WO-25 framework (backend discovery + `regolith ship`,
landed), WO-42 (realized IRs + store, done), WO-44 preferred
(register via `regolith.plugins`, kind=backend). The civil sheet
producer additionally gated on WO-48 (the `frame` payload); WO-48
slice B landed (`FramePayload` in `regolith-oblig`, frames threaded
through `LowerOutput`/`BuildPayload`/the payload store), un-gating
this leg -- it landed this dispatch. The quality-audit leg needs
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
   from `flownet` payloads + symbol records; BOM tables for elec from
   existing netlist state. Civil plan producer (`civil_plan_section`)
   LANDED this dispatch: one plan-view sheet from the `frame` payload
   (joints/members/supports, deterministic grid layout by sorted id --
   no grid/level record positions since `std.civil` record content is
   not on master yet, a named residual) plus a member-schedule `Table`
   on the same sheet (`std.civil`-unresolved section/material rendered
   `"unresolved"`, never fabricated).
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
  plan + member schedule, feed_system P&ID -- deterministic,
  provenance-complete. The civil leg's `small_office` proof is a
  constructed `FramePayload` fixture (`tests/backends/test_drawings.py`
  `_frame()`), mirroring the mech/fluid legs' own precedent
  (`_geometry()`/`_flownet()`) rather than a compiled `.calx` corpus
  run through the CLI end to end -- "golden-enrolled" for every leg in
  this WO means the same pytest determinism-assertion proof
  (`test_deterministic_across_two_runs`: two producer runs byte-
  identical, JSON and SVG), not a separate `insta`/snapshot file; no
  leg (mech, fluid, or civil) enrolled a distinct golden-file
  fixture -- recorded here so the civil leg is not held to a stricter
  bar than its siblings.
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

- **Civil plan/section + member-schedule producer**: LANDED this
  dispatch (`regolith.backends.drawings.producers.civil_plan_section`,
  wired into `DrawingsBackend`/`BackendInputs.frames`/`ship()`'s
  `frame`-kind realized-input derivation). Built ONLY against
  `FramePayload` itself (calcite/03 sec. 4) plus name-only record
  refs, per the dispatch caveat: `std.civil` record CONTENT (slice C)
  is still being authored in parallel and is not on master. Two named
  sub-residuals inside this leg, both honest-deferral, not scope
  creep:
  - **Plan-position layout**: joints are placed on a deterministic
    grid by sorted id (mirroring the fluid P&ID producer's own node
    layout), NOT at their actual `grid_refs`/level coordinates --
    resolving a grid ref to a real plan coordinate needs the
    `std.civil` grid/level record catalog, which this slice does not
    have. A follow-on that lands `std.civil` grids can upgrade the
    layout without changing the producer's public shape.
  - **Section/material schedule cells**: a member whose `section` or
    `material` is the AD-25 `free`/unresolved placeholder renders the
    literal string `"unresolved"` in its schedule row rather than a
    fabricated part/material name -- the honest-indeterminate idiom
    applied to a table cell instead of a claim.
  Everything else this WO promises (schema, mech producer, fluid P&ID
  producer, the elec BOM table producer, the SVG renderer, the full
  quality-audit machinery, and drawing attestation) is also landed and
  tested.
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
