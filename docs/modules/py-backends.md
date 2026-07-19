# py-backends

`python/regolith/backends` -- manufacturing backends + the ship
pipeline (WO-25, L6). A backend consumes ONLY `(lockfile, evidence
cache, realized artifacts)` -- never the compiler/CST (enforced by
construction: no `Backend` implementation imports
`regolith.compiler`/`regolith._core`; only `regolith.backends.ship`
calls the orchestrator) -- and serializes them into files a
manufacturer can consume. Backends never decide anything (regolith/07
sec. 6): every emitted byte traces to a pinned lockfile row, a
discharged obligation's evidence, or a realized-domain IR (AD-25)
already produced upstream. This is the WO-99/AD-38/AD-39-era emission
architecture; normative sources are pointed at, not restated:
`docs/spec/toolchain/00-architecture.md` AD-25/26/27/38/39,
`docs/spec/toolchain/25-drawings-and-artifacts.md`. See
`AUDIT-2026-07-16.md` for this pass's recon.

## Framework, registries, and the ship driver

<a id="backends-init"></a>
### `backends/__init__.py`

Package-level contract statement: a backend reads only `BackendInputs`
and writes `OutputFile`s; `regolith.backends.ship` is the top, enforcing
the release gate (INV-24) and producing a signed manifest.

<a id="backends-framework"></a>
### `backends/framework.py`

The backend framework: the `(lockfile, evidence, realized-artifacts)`
input triple every backend consumes and nothing else. `Backend` never
imports `regolith.compiler`/`regolith._core` (a standing check,
`tests/backends/test_framework.py`) and never invents a value
`BackendInputs` does not already carry. `OutputFile` carries an
optional `provenance: ArtifactProvenance | None` (WO-160, AD-45):
`ToolIdentity`/`ArtifactProvenance` (`tier: real_tool | deterministic`)
are supplied at construction time via `OutputFile.of(..., provenance=)`
by a two-tier producer (the KiCad fork is the worked example); an
untagged file resolves to the honest `deterministic` default at
index-build time (`artifact_index.build_index`), never an invented
`real_tool` claim.

<a id="backends-registry"></a>
### `backends/registry.py`

Producer + renderer registries -- the ONE dispatch seam (WO-99, charter
38 sec. 1.2): kills the `model_for_spec` if/elif ladder and the
`files_for_model` renderer quintet in favor of `ProducerRegistry`/
`RendererRegistry` lookups. Duplicate ids are a loud typed error, never
silent last-wins shadowing. `ArtifactFamilyRegistration` (WO-130/AD-41)
also carries `path_patterns: tuple[PathPattern, ...]` (WO-161, AD-46):
the per-file relpath-narrowing rules that used to live in
`artifact_index.classify`'s hand-written if/elif ladder (now deleted),
matched in order via `match_path_pattern` -- one dispatch path, not two
independently-drifting ones. `wiring_map` (svg default) and `cutlist`
(table default) are the two families WO-165's perf-board program adds,
registered the same way every other family is (`default_artifact_family_registry`,
mirrored into `backends/package.py`'s `FAMILY_DIRS`).

<a id="backends-capabilities"></a>
### `backends/capabilities.py`

The realizer capability registry (WO-164, AD-47 sec. 5, charter 44):
`RealizerCapability` names the full checklist a NEW manufacturing/
generation capability must supply -- `domain`, `program_kind`
(the L1/L2 program IR class), `realized_kind` (the `put_realized_*`
kind-string), `artifact_families`, `tool_adapters` (the ordered
real_tool-then-deterministic AD-45 tier ladder), `process_records`
(AD-37 stdlib namespaces), `dfm_checks`, and `claim_kinds` -- all seven
required, no silent-default holes. `CapabilityRegistry.register` raises
`IncompleteCapabilityError` (never a silent `None`) on any empty
required field or a duplicate `domain`; `register_capability` is a
`Result`-returning wrapper for composable call sites. `mech` and `elec`
are retrofit as the first two registrations, DESCRIPTIVELY -- named
field-by-field from their existing scattered pieces
(`FeatureProgram`/`geometry.realized`/build123d-OCCT in-process
deterministic tier for mech; `LayoutRequest`/`layout.realized`/the
kicad-cli-then-fake two-tier ladder for elec) -- no behavior change to
either realizer. `get_capability` is the lookup surface a future
capability program (wire-EDM die-set, perf-board routing, dwelling
wiring, D268) uses instead of hard-coding process records/DFM checks/
tool adapters per domain. `perfboard` (WO-165) is the third
registration and the FIRST NEW capability program (mech/elec were a
descriptive retrofit): `PerfboardNetlist`/`board_assignment.realized`/
the `wiring_map`+`cutlist` artifact families/a single deterministic
tool-adapter tier (no external tool, the assignment runs in-process)/
the `std.process.perfboard_assembly` pending process-record namespace
(WO-170 populates the real records)/`check_no_shared_holes`/
`perfboard.assignment_complete`.

<a id="backends-plugin"></a>
### `backends/plugin.py`

The `backend` plugin kind (WO-25 framework + WO-44/AD-26 one seam):
third-party manufacturing backends register through the same
`regolith.plugins` group (`kind=backend`); built-ins (`mech`, `elec`)
are never overridden by a plugin naming the same key.

<a id="backends-renderer-plugin"></a>
### `backends/renderer_plugin.py`

The `renderer` plugin kind (WO-99 registries + AD-26 one seam):
third-party producers/renderers register via `regolith.plugins`
(`kind=renderer`), composing alongside built-ins with no silent
last-wins on a colliding id. Installing a renderer plugin confers no
trust (INV-14/28).

<a id="backends-ship"></a>
### `backends/ship.py`

`regolith ship`: the release gate + signed manufacturing package
(WO-25). The one driver allowed to call the orchestrator; runs a T3
`staged_build` (INV-24 totality), refuses with a named diagnostic on
gate failure, then drives every configured `Backend` over the same
`BackendInputs`, folding every emitted file into one signed
`ShipManifest`.

<a id="backends-preview"></a>
### `backends/preview.py`

`regolith preview`: viewable artifacts without weakening INV-24 (D197).
Runs the same producer set `ship` drives, stamps every sheet with the
honest gate state through its own model (never post-editing a rendered
file), no signing/manifest/BOM/fab-note packages.

<a id="backends-package"></a>
### `backends/package.py`

The one `dist/<project>/` release-package layout (WO-99 d4, charter 38
sec. 1.3): `manifest.json`, `index.md`, `gate_summary.json`,
`parity_ledger.json`, `acceptance_ledger.json` (a placeholder here;
WO-98 owns its semantics). Owns only side files + the index; per-family
files come from the backends unchanged.

<a id="backends-manifest"></a>
### `backends/manifest.py`

The signed ship manifest (WO-25): same envelope discipline as
`regolith.harness.attest` -- signature over a domain-tagged content
address of the manifest's unsigned fields, never the raw bytes, never
folding the signature back into what it signs.

<a id="backends-parity"></a>
### `backends/parity.py`

The parity ledger: `regolith ship --explain`'s attribution report
(WO-63; D170; AD-33). Classifies every resolved value, discharge state,
and waive-ledger entry into D170's provenance classes. Artifact-only
(AD-22): reads only the lockfile/`ObligationResult` list/`WaiveLedger`
a build already produced. Escalated gap: `asserted(literal, source
position)` is not reachable from any emitted artifact today (recorded
per design-log 2026-07-09-cycle-31 addendum D170-a) -- rendered as an
explicit caveat, never a silently-empty list.

<a id="backends-artifact-index"></a>
### `backends/artifact_index.py`

The universal artifact index (WO-130, D244/AD-41, charter 42 secs.
6-7): every emitted file's `family`/`kind`/`relpath`/`content_hash`/
`bytes`/`media_type`/closed-vocabulary `viewer` hint/required
`provenance`/`source_refs`, via two-step classification (family from
top-level path segment, the family's own registered `path_patterns`
narrow kind/viewer -- WO-161, `classify()` is deleted) so a consuming
viewer never needs a hardcoded family list (the structural fix for
F145). `check_index_consistency` (WO-130 deliverable 6) additionally
catches a row whose family has no matching `path_patterns` entry
(WO-161) and a row whose `provenance` is internally inconsistent
(`tool` present iff `tier == "real_tool"`, WO-160) -- either is drift,
never a warning.

<a id="backends-artifacts"></a>
### `backends/artifacts.py`

The pinned native-artifact store (STEP bytes, `.kicad_pcb` bytes):
AD-25's amendment keeps the realized-domain IR as the semantic content
while the native artifact stays a pinned side artifact, addressed by
the SHA-256 hex digest already carried on the IR (its own digest scheme,
distinct from the `blake3:`-prefixed `PayloadStore` convention).

<a id="backends-quantity"></a>
### `backends/quantity.py`

The one home for a unit-carrying artifact-rendering value (WO-150,
D262 ruling 1): `DimensionedValue` makes an absent-unit state
unrepresentable (required field, empty string rejected); a genuinely
dimensionless magnitude must say so explicitly via `DIMENSIONLESS`.
Python-side type only, no schema bump.

## Mech, elec, firmware, HDL packages

<a id="backends-mech"></a>
### `backends/mech.py`

The mech manufacturing package: STEP + BOM + fab notes (WO-25). Every
serialized value already exists upstream (STEP bytes from the WO-22
realizer's pinned native artifact, mass/topology from the IR's own
`topology` block); BOM/fab-note text comes from the caller's
`AssemblyLine`/`FabNoteSpec` -- never invented.

<a id="backends-elec"></a>
### `backends/elec.py`

The elec manufacturing package: gerbers + drill + pick-and-place + BOM.
Drives `kicad-cli` against the pinned `.kicad_pcb` bytes resolved from
`NativeArtifactStore`; gated by `real_kicad_available()` -- when
closed, WO-124's fake-KiCad fab-set exporter emits the same file
manifest by hand instead of an honest cut. Panelization is a
single-board pass-through `PanelPlan` in v1. The real `kicad-cli` leg
tags every export `OutputFile` with `provenance=real_tool` + the
observed `kicad-cli` version (WO-160, AD-45) -- the worked example for
every future two-tier adapter.

<a id="backends-elec-fabset"></a>
### `backends/elec_fabset.py`

The complete board fab set (WO-124, charter 41 sec. 3, D238.2/AD-39):
the shared layer manifest, a deterministic hand-rolled Gerber X2 +
Excellon writer, and the set-completeness checker both legs (real
`kicad-cli`, this writer) run. Honesty discipline (D224): every layer
is genuinely derived or a legitimately empty-but-valid file, never
fabricated geometry. Every emitted `OutputFile` is explicitly tagged
`provenance=deterministic, tool=None` (WO-160, AD-45) -- this tier's
own honesty contract stated at construction time, never left to the
artifact index's untagged default.

<a id="backends-perfboard"></a>
### `backends/perfboard.py`

The perf-board manufacturing package: wiring map + cut list (WO-165,
AD-47 sec. 5). Mirrors `ElecBackend`'s shape (subject-bound,
`produce(inputs) -> Result[...]`) over `BackendInputs.board_assignments`
(the `board_assignment.realized` kind, WO-163) instead of `layouts`.
No external tool runs -- every emitted file is `tier="deterministic"`
(WO-160/AD-45), never a claimed `real_tool`. The wiring map is
projected via `regolith.backends.drawings.producers.perfboard_wiring_map`
and rendered through the SAME `DrawingModel` -> svg path every other
track uses (AD-27, "reuse, never invent a new renderer"); the cut list
is a CSV bill of wire lengths by gauge (`DimensionedValue`-carrying per
D262/INV-34; v1 assumes one gauge, `DEFAULT_JUMPER_GAUGE_AWG`, a named
simplification) plus a `board_dimensions.json` sibling.

<a id="backends-firmware"></a>
### `backends/firmware.py`

The firmware manufacturing package: the WO-37 realizer's generated
tree, a build report, and (when pinned) a compiled image (WO-102
deliverable 1). AD-22 stands -- nothing here invokes a compiler; a
design with no pinned ELF ships the generated tree + an honest
`elf: null`.

<a id="backends-hdl"></a>
### `backends/hdl.py`

The HDL manufacturing package (WO-102 deliverable 2): serializes what a
build already proved through the WO-82 `std.hdl` tiers -- nothing here
re-runs verilator/ghdl (AD-22). The verilated build directory is a
cache, never packaged; a synthesis tier that never ran is a named
absence, never a fabricated netlist.

<a id="backends-instructions"></a>
### `backends/instructions.py`

`AssemblySteps`: an ordered, viewable build document derived entirely
from proven pipeline data (WO-96, D199.1). `steps_for_assembly` builds
the raw model from a `RealizedAssembly` + evidence index;
`render_document` is the one renderer to markdown; `files_for_steps` is
the shared rendering tail for preview and `InstructionsBackend`. Steps
order fixed-first then placed (tie-broken by part id, AD-6);
underconstrained parts are never given an invented step -- named in
`unordered_parts` instead. Fastener callouts report the model's own
discharged quantity (VDI 2230 clamp force, L10 life), labeled honestly,
never an invented torque number.

<a id="backends-bom"></a>
### `backends/bom.py`

Derived BOM v2 + cost join, with real record-pinned mass (WO-101,
charter 38 sec. 1.7, D208). Replaces the first-generation BOM's
surface-area-mislabeled-as-mass column with rows derived from the
design graph (mech parts, assembly members, frame members, elec block
instances, flownet fittings) -- never invented. Part numbers come only
from a caller `AssemblyLine` or a hash-pinned record; an unsourced row
ships a loud `unsourced` marker. Mass is material-record density x
realized solid volume, both pins carried as provenance; a missing
input leaves an honestly empty cell with a reason (D204).

<a id="backends-cost-schedule"></a>
### `backends/cost_schedule.py`

Cost + schedule sheet producers (WO-101 deliverable 5, charter 38 sec.
1.8, AD-27): `cost_summary_sheet` and `member_schedule_sheet` project
persisted itemized estimates / calcite frame members into ordinary
`DrawingModel` tables -- these functions project, they never compute a
cost or takeoff.

<a id="backends-calc"></a>
### `backends/calc.py`

The calc package + audit index -- the audit trail (WO-114, D221): one
calc sheet per discharged obligation (claim, model, every `given` input
with provenance, solver/tier/attestation, margin, verdict, content-hash
chained to its evidence); one package-level audit index mapping every
obligation to exactly one disposition (calc sheet, accepted deviation,
named deferral, or violated), using the same census definitions as
`tools.health.fleet._census_from_report` so the two can never disagree.
Forms: canonical JSON + a rendered PDF through the existing
`DrawingModel` renderer registry -- no second renderer.

<a id="backends-harness-pack"></a>
### `backends/harness_pack.py`

The bring-up harness pack -- `harness/` family (WO-126, D237.3): tap
map, ordered bring-up procedure, expected-signal manifest where every
row traces to a discharged claim/calc-sheet hash/declared record, and
sigrok-compatible capture configs. Only formats data `ship` already
resolved (`debug_taps.TapSet`, the release report, the calc book);
an unverifiable expectation is a named `no_verified_expectation`
absence, never a fabricated number (D224).

<a id="backends-debug-taps"></a>
### `backends/debug_taps.py`

The debug-profile tap model + deriver (WO-125 deliverable 2, D237.2): a
tap is `(channel, kind, target_path, why)`. Two merged sources feed one
deterministic `TapSet` -- DERIVED (every claim-named net/signal, ranked
by claim family, overflow named `unallocated`) and EXPLICIT (the ship
spec's `"debug"` block, winning channels before derived ones; a path
absent from the candidate universe is a diagnostic, never a silent
skip). `derive_taps` is pure (no IO/compiler/orchestrator calls).
`check_tap_agreement` is the INV-32 check, re-parsed from emitted bytes.

## Drawings + schedules

<a id="drawings-init"></a>
### `backends/drawings/__init__.py`

Drawings + schedules backend: `DrawingModel` producers, an SVG
reference renderer, and the drafting quality audit (WO-50, AD-27/D140).
Producers derive, renderers render, quality is audited by rules
(`docs/spec/toolchain/25-drawings-and-artifacts.md`).

<a id="drawings-backend"></a>
### `backends/drawings/backend.py`

`DrawingsBackend`: rides the WO-25 framework to emit the drawing set
(`DrawingModel` JSON + SVG + DXF + PDF + audit report) for a configured
subject list (WO-50 deliverable 2/3). As of WO-99, `model_for_spec`/
`files_for_model` are thin wrappers over the registry seam; mirrors
`MechBackend`'s never-invents-subjects shape.

<a id="drawings-producers"></a>
### `backends/drawings/producers.py`

Per-track `DrawingModel` producers (charter sec. 1 decision 2): project
realized IRs into the documentation IR, never author page description
or compute geometry (AD-27). A `source_digest` is a local blake3 over
the realized IR's canonical JSON, prefix-tagged `local-blake3:` so it
is never confusable with an upstream Rust content address (WO-99 D6,
charter 38 sec. 1.4). An unresolved value (e.g. an unresolved `section:
free` member) is honestly omitted from dimensions/annotations, never
fabricated.

<a id="drawings-project"></a>
### `backends/drawings/project.py`

Real OCP/OCCT hidden-line projection of pinned STEP bytes into
`DrawingModel` views (WO-100 deliverable 1/2, charter 38 sec. 1 decision
5): resolves pinned STEP bytes, runs OCCT's `HLRBRep` to project
front/top/side/isometric views (visible edges solid, hidden edges a
deterministically dashed layer). Every tunable is a named module
constant and every coordinate is quantized so two runs are
byte-identical (proven by `tests/backends/test_wo100_projection.py`).
Falls back to the v1 bbox stand-in plus a loud annotation when STEP
bytes or OCP are absent -- never crashes, never passes the stand-in off
silently.

<a id="drawings-layout"></a>
### `backends/drawings/layout.py`

Deterministic mechanical layout helper (WO-58 deliverable 3, D165
"mechanical, not aesthetic"): layered DAG placement + orthogonal edge
routing + standoff label ladders, one shared home for every
payload-derived diagram producer needing a node/edge graph on a grid.
No aesthetic search: node position is a pure function of caller-supplied
node/edge order (AD-6); overlapping labels break by a fixed step
ladder, never a solver.

<a id="drawings-renderer"></a>
### `backends/drawings/renderer.py`

The SVG reference renderer (charter sec. 1 decision 2, mandatory):
deterministic text output, same `DrawingModel` -> byte-identical SVG
(AD-6). Consumes only `DrawingModel`, no geometry computation, no
re-reading of source (AD-27).

<a id="drawings-renderer-dxf"></a>
### `backends/drawings/renderer_dxf.py`

The DXF renderer: a sibling of the SVG renderer over the same
`DrawingModel` IR. Minimal ASCII DXF R12 (AC1009), hand-written,
dependency-free; reuses the SVG renderer's own view grid-cell layout
math so both renderers place the same entity at the same sheet-space
point (no second layout mechanism).

<a id="drawings-renderer-pdf"></a>
### `backends/drawings/renderer_pdf.py`

The PDF renderer: a sibling of the SVG renderer over the same
`DrawingModel` IR. Minimal, dependency-free, hand-rolled PDF 1.4;
deterministic byte output (no `/CreationDate`, no `/ID`); reuses the
SVG renderer's own layout math.

<a id="drawings-style"></a>
### `backends/drawings/style.py`

Style records (WO-99 D7, charter 38 sec. 1.12): drafting aesthetic
constants as hash-pinnable data. `NEUTRAL_STYLE` reproduces every
historical hard-coded renderer constant exactly (byte-identical to the
pre-style output, proven by `tests/backends/test_style.py`); renderers
hold no aesthetic constant beyond this default.

<a id="drawings-attest"></a>
### `backends/drawings/attest.py`

Human sign-off over `DrawingModel` content (charter sec. 1.7,
AD-20/INV-28): a release drawing may carry a reviewer's signed
attestation over the sheet set's content address; regeneration that
changes content changes the address, so re-signing a stale attestation
is impossible by construction. Mirrors `regolith.harness.attest`'s
envelope pattern generalized to any addressable payload.

<a id="drawings-audit"></a>
### `backends/drawings/audit.py`

Drawing quality audit (charter sec. 1.7, AD-27): the seed drafting rule
pack, contract-coverage check, and `ship --explain` audit report. Each
rule is an ordinary Python predicate over `DrawingModel` with a `per:`
citation -- a precursor rule runner, structurally identical in shape to
what the future WO-28 in-language engine will run, not a second engine.

## 3D artifacts

<a id="three-d-init"></a>
### `backends/three_d/__init__.py`

The 3D artifact family (WO-100 deliverable 3/4, charter 38 sec. 1
decision 6): a deterministic GLB plus a self-contained HTML viewer, per
`RealizedGeometry` part and per `RealizedAssembly`, registered like any
renderer through the WO-99 registry seam.

<a id="three-d-backend"></a>
### `backends/three_d/backend.py`

`ThreeDBackend`: the ship/preview consumer emitting the 3D artifact
family. Walks the `RendererRegistry.register_realized` seam -- adding a
format is one registration, zero edits here. A subject with no native
STEP bytes, or a host without OCP, is logged and skipped honestly
(never crashed on).

<a id="three-d-glb"></a>
### `backends/three_d/glb.py`

Deterministic binary glTF (GLB) writer over canonical triangle meshes
(WO-100 deliverable 3): 12-byte header + JSON chunk + BIN chunk, no
timestamp, fixed generator string, sorted/canonical buffers, stable
float32/uint32 packing -- byte-identical GLB proven by
`tests/backends/test_wo100_glb.py`. Only POSITION + indices are
emitted; the viewer computes flat normals in-shader.

<a id="three-d-tessellate"></a>
### `backends/three_d/tessellate.py`

OCCT incremental-mesh tessellation of pinned STEP bytes into a
deterministic triangle mesh (WO-100 deliverable 3, the GLB's front
end). Fixed tessellation parameters and full coordinate quantization +
canonical ordering make the emitted mesh reproducible across runs
(AD-6). OCP is imported lazily; a host without it emits no 3D artifact
rather than failing import.

<a id="three-d-viewer"></a>
### `backends/three_d/viewer.py`

A single self-contained HTML viewer for a GLB (WO-100 deliverable 4,
charter 38 sec. 1 decision 6, the graphite/AD-31 posture): the GLB is
embedded as base64 (zero network requests), decoded and drawn with a
small dependency-free WebGL2 renderer (orbit/pan/zoom, in-shader flat
shading, per-part color, id-color-picking hover). Generated source is
ASCII-only with no `http`/`//` host reference, asserted by
`tests/backends/test_wo100_viewer.py`.
