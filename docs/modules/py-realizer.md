# py-realizer

`python/regolith/realizer` -- the L3 -> L4 structural realizers, one
submodule per domain (`regolith.realizer.mech` WO-22,
`regolith.realizer.elec` WO-24, `regolith.realizer.firmware` WO-37).
AD-4 is the shared boundary: every realizer consumes ONLY a serialized,
schema-versioned IR (never the CST or `regolith._core`); AD-7 is the
shared error discipline: every fallible realizer API returns a typani
`Result` whose `Err` is a frozen error VALUE, never a bare exception.
Language/architecture normative sources are pointed at, not restated:
`docs/spec/regolith/08-realization.md` (L4), `docs/spec/toolchain/
00-architecture.md` AD-1/AD-4/AD-6/AD-7, and per-domain spec sections
cited inline below. This doc is a symbol-level index; see
`AUDIT-2026-07-16.md` for the realizer-domain-conventions recon this
pass draws on for prose accuracy.

## Package root

<a id="realizer-root"></a>
### `realizer/__init__.py`

Realizer package root: holds no shared logic of its own (WO-22/24/37
are siblings by convention, not a formal registry). Adding a new
realizer domain means a new sibling subpackage with its own `schema.py`
(serialized IR, AD-4) and an interpreter/realize module, wired by
direct import at each caller's call site -- there is no central
realizer registry (unlike `regolith.backends`' producer/renderer
registries).

## Elec realizer

<a id="elec-init"></a>
### `realizer/elec/__init__.py`

Elec structural realizer: bind -> netlist -> layout (WO-24; cuprite/04
step order, cuprite/06 lowering table, regolith/08 sec. L4, regolith/07
sec. 7 allocation search). Submodules: `binding`, `netlist`, `kicad`,
`extraction`.

<a id="elec-errors"></a>
### `realizer/elec/errors.py`

Elec realizer error VALUES (AD-7 house style): every fallible realizer
API returns a typani `Result[T, E]` whose `E` is one of these frozen
models; exceptions are reserved for programmer bugs.

<a id="elec-binding"></a>
### `realizer/elec/binding.py`

Component binding: allocation search over registry records
(regolith/07 sec. 7). Binds abstract blocks to concrete registry
records screened by capability arithmetic and aggregate design
budgets; a budget-blowing candidate is a NOGOOD (D75, solver state
only, never lockfile-written) and the search backtracks until feasible
or exhausted. `NogoodCache` lets a nogood survive across runs, keyed so
a changed blamed record naturally misses. Every successful binding
becomes a `PlannerPin` (lockfile cause `planner`).

<a id="elec-bridge"></a>
### `realizer/elec/bridge.py`

The binding-requirement bridge (WO-29 deliverable 4): turns raw
capability demands from the Rust lowering (D90 split) into the numeric
`BlockRequirement`/`ComponentCandidate` shapes `binding.py`'s
allocation search consumes, deriving candidates from magnetite
`RecordStore` records. Only `>=`/`>` demands become screening minimums
today; ceiling/equality demands are logged and skipped (a named,
honest scope cut, not an invented two-directional screen).

<a id="elec-debug-placement"></a>
### `realizer/elec/debug_placement.py`

Debug-profile tap placements (WO-125 deliverable 4, charter 40 sec. 1):
given an allocated `TapSet` and the tap-header pinout record, derives
one placed tap header plus one labeled test point per allocated tap as
`Placement`-shaped emission-layer data (no schema change, D239), plus
silkscreen channel-label rows. Placement is a DECLARED decision
(`placement_rule`), never a measured/verified geometry claim.

<a id="elec-extraction"></a>
### `realizer/elec/extraction.py`

Post-route extraction surface (WO-24 deliverable 4): shapes
layout-dependent measurements (net lengths, copper areas) as
model-pack inputs. `extract_from_pcb` walks a real `.kicad_pcb` via
`pcbnew` when importable; on a `pcbnew`-less host it is an honest
`Err(ToolUnavailable)`, never a faked measurement.

<a id="elec-fake-kicad"></a>
### `realizer/elec/fake_kicad.py`

The fake-subprocess KiCad layout tier (WO-71 continuation slice 2): a
deterministic, no-install `run_layout` runner for KiCad-less
environments. Never claims `status="routed"` (no netlist bound, no
footprint placed) and emits no DRC report (never a claim of
DRC-clean). Draws a genuine rectangular `Edge.Cuts` outline sized from
the caller's real `outline_w_mm`/`outline_d_mm` (WO-103) as a valid,
parseable `.kicad_pcb`.

<a id="elec-identity"></a>
### `realizer/elec/identity.py`

Board-identity silkscreen geometry: the ONE home for text height,
margin, and placement math shared by every board-authoring leg
(fake_kicad, kicad_wrapper, `backends.elec_fabset`) so the legs cannot
drift apart again (WO-124 visual-pass fix, charter 41 sec. 3, D238.3).

<a id="elec-kicad"></a>
### `realizer/elec/kicad.py`

Layout adapter `realizer.elec.kicad`: KiCad as a subprocess pack
(AD-19), mirroring `regolith.harness.adapter`'s wire discipline. A
wrapper executable reads one `LayoutResponse` JSON document off
stdout; every infrastructure failure (spawn/timeout/malformed
response) is a value, never an exception. `real_kicad_available()`
gates the real vs. fake-subprocess tier.

<a id="elec-kicad-wrapper"></a>
### `realizer/elec/kicad_wrapper.py`

The real KiCad layout wrapper (WO-24 close-out): runnable as `python -m
regolith.realizer.elec.kicad_wrapper`, drives real `pcbnew`/`kicad-cli`
to build a real `pcbnew.BOARD`, draw the caller's real outline, save a
real `.kicad_pcb`, and run a real `kicad-cli pcb drc` pass. Footprint
resolution/placement and routing are not attempted; the response is
always `status="unrouted"` -- never a faked `"routed"`.

<a id="elec-netlist"></a>
### `realizer/elec/netlist.py`

Netlist emission: bound design -> neutral model -> KiCad writer
(cuprite/06). `NetlistModel` is content-addressed L4 data. The
single-driver/arbitration check (AD-23 "one net core") runs BEFORE
emission via `regolith.compiler.check_elec_single_driver` -- the one
door to `regolith._core` -- never reimplemented here.

<a id="elec-pinmux"></a>
### `realizer/elec/pinmux.py`

Pin-mux matcher: flow demands -> function instances -> package pins
(cuprite/04 sec. 1 step 2, cuprite/02 sec. 5). A monomorphized matching
problem over record-declared capability data (GENERALITY RULE, WO-35
deliverable 2) -- no hardcoded vendor shape or fixed resource taxonomy;
every assignment is lockfile-caused (`planner(pinmux <instance>)`); a
failed match names the contended resource.

<a id="elec-realized"></a>
### `realizer/elec/realized.py`

`RealizedLayout` assembly (WO-42 deliverable 4 remainder): builds the
generated `RealizedLayout` payload from a completed `run_layout`/
`extract_from_pcb` pass and `put`s it into the WO-30 payload store
(`kind: layout.realized`), mirroring
`orchestrate.put_realized_geometry`'s fresh-blake3-digest precedent.

`realizer/elec/board_assignment.py` (WO-163, A7): the sibling
`board_assignment.realized` kind for board-shaped capabilities OTHER
than an etched-copper KiCad board (perf-board today, WO-165) --
`RealizedBoardAssignment` carries no `copper`/`kicad_pcb_content_hash`
field, since neither applies to a fixed-grid perf-board substrate.
`put_realized_board_assignment` follows `put_realized_layout`'s exact
pattern (`PayloadStore.put`, fresh digest). Defined as a plain pydantic
model rather than a schemars-sourced type for now (D211 sequencing:
WO-147 owns the cycle-37 SCHEMA_VERSION bump and was still open at this
WO's dispatch) -- see the module docstring for the promotion note.

## Firmware realizer

<a id="firmware-init"></a>
### `realizer/firmware/__init__.py`

Firmware realizer: pinned lockfile rows -> generated BSP + contract
header (WO-37; D109). Generates the design-determined code layer only
(hardware contract header, BSP pin/clock/ISR-stub sources via an
MCU-family pack, linker memory map) -- every generated symbol traces
to an upstream planner decision; application logic is never generated.
Submodules: `contract`, `packs`, `bsp`, `linker`, `bindings`,
`realize`, `errors`.

<a id="firmware-errors"></a>
### `realizer/firmware/errors.py`

Firmware realizer error VALUES (AD-7 house style): every fallible
realizer API returns a typani `Result[T, E]`; exceptions are reserved
for programmer bugs.

<a id="firmware-contract"></a>
### `realizer/firmware/contract.py`

The typed firmware design input + the hardware contract header
(deliverable 1; cuprite/04 sec. 1 step 2, cuprite/05 sec. 4, D109).
`FirmwareDesign` aggregates realized decisions (pin assignments, the
typed `EventDecl` ledger from `events_from_on_blocks`, declared clocks,
declared `partitions:`) -- nothing here decides anything, every value
is copied from an upstream cause (INV-10/INV-21).

<a id="firmware-bsp"></a>
### `realizer/firmware/bsp.py`

BSP source generation (deliverable 2): pin config + clock + ISR stubs,
translated through an MCU-family pack. ISR stub signatures come from
the typed event ledger; stub bodies call user-provided hooks by name
and contain no logic (D109, WO-37 acceptance criterion 5).

<a id="firmware-linker"></a>
### `realizer/firmware/linker.py`

Linker memory map + build fragment (deliverable 3): declared
`partitions:` (cuprite/05 sec. 4) emit the linker script; a Make
fragment builds BSP + user sources. Adds zero new claim vocabulary --
the built image re-enters via the existing image/extern hash-pin
machinery.

<a id="firmware-packs"></a>
### `realizer/firmware/packs.py`

The MCU-family pack seam (deliverable 4): vendor HAL idiom as pack
content (D109), mirroring AD-19's model-pack shape. Third-party
mcu-family packs discover via `regolith.plugins` (`kind=mcu_pack`,
WO-44/AD-26); built-ins compose first, then discovered plugins sorted
by id. `FamilyPack` turns one pin/clock/event into vendor-idiom C
lines; an unregistered family is honest indeterminate (`UnknownFamily`),
never a guess.

<a id="firmware-bindings"></a>
### `realizer/firmware/bindings.py`

Cross-language bindings generated FROM the contract header
(deliverable 5): a Rust `-sys`-shaped binding generator re-emits the
same symbols as `pub const` items straight from `FirmwareDesign`
(never parsing the generated C text back) -- one producer-side pass,
two emitted artifacts, no second source of truth. Opt-in via
`emit_rust_sys` on `realize_firmware`.

<a id="firmware-realize"></a>
### `realizer/firmware/realize.py`

Top-level orchestration (deliverable 6): design -> content-addressed
generated tree. `realize_firmware` is a pure function of its input
(INV-10 byte-identical); INV-21 (every generated symbol traces to a
lockfile cause) is composed from `contract`/`bsp`/`linker`/`bindings`,
each of which already holds it. The tree's `content_hash` feeds the
WO-25 ship manifest.

## Mech realizer

<a id="mech-init"></a>
### `realizer/mech/__init__.py`

The mech geometry realizer (WO-22): feature IR -> build123d/OCCT ->
STEP. `schema` is the serialized feature-program IR (AD-4 boundary);
`interpreter` is the build123d/OCCT interpreter (AD-1); `model`/`pack`
register the `geometry_realizable` post-geometry verification model
(AD-19).

<a id="mech-errors"></a>
### `realizer/mech/errors.py`

Realizer error VALUES (AD-7 house style): never a bare exception. An
unsupported op or schema-version skew is a recoverable, honest
deferral; an OCCT boolean-operation failure on well-formed input is
recorded as a value too -- a property of the input geometry, not a
programmer bug.

<a id="mech-schema"></a>
### `realizer/mech/schema.py`

The serialized feature-program IR the mech realizer consumes
(AD-4/AD-5): the FORWARD CONTRACT a future `regolith-lower` pass must
emit; until it lands, the realizer is exercised against hand-built
`FeatureProgram` fixtures. Units are SI base (metres) -- the
interpreter is the one place that converts to build123d's native
millimetre scale. Schema v2 (D130, WO-42 deliverable 4) adds part-level
`flow_paths`/`material_props`: DECLARED design intent (never derived
from the B-rep solid), validate-and-emit, never derive-and-guess.
`schema_version` refuses an unknown version rather than guessing
(AD-5).

<a id="mech-interpreter"></a>
### `realizer/mech/interpreter.py`

The build123d/OCCT interpreter for a resolved v1 `FeatureProgram`
(AD-1: the one module that imports build123d; AD-4: consumes only the
serialized IR; AD-6: the same `FeatureProgram` always drives the exact
same build123d call sequence). `_export_step_bytes` normalizes OCCT's
wall-clock export timestamp to a fixed sentinel so `step_content_hash`
is genuinely byte-deterministic; `TopologySummary.content_hash` is the
cross-platform golden (OCCT's STEP serialization is not byte-stable
across builds/platforms, WO-22 acceptance).

<a id="mech-model"></a>
### `realizer/mech/model.py`

The `geometry_realizable` model pack (AD-19): realized vs. predicted,
wired through the shared harness `Model`/`DischargeRequest`/registry
path (the margin rule lives once, in `regolith.harness.evidence`). The
orchestrator-side wiring to thread a per-part `FeatureProgram` through
`DischargeRequest` does not exist yet (no `regolith-lower` producer
emits `geometry_realizable` obligations); until then this model is
exercised by calling `register_realized_geometry` directly.

<a id="mech-pack"></a>
### `realizer/mech/pack.py`

The mech realizer's model-pack entry point (AD-19/WO-20 D-B): a
`register(registry) -> None` callable discoverable via the
`regolith.plugins` entry point group (`kind=model_pack`), kept in-tree
since this pack ships with the realizer itself.

<a id="mech-assembly"></a>
### `realizer/mech/assembly.py`

The mate-graph solve + STEP assembly export + extraction (WO-62 slice
B deliverable 5; charter `30-geometry-lowering.md` sec. 1.4). Input is
a hand-declared `AssemblyDef` (parts + mates); solve is deterministic
sequential placement over a spanning order of the mate graph
(BFS in declaration order, AD-6); a mate off the spanning tree is
checked for closure within tolerance (`MateLoopResidual` on
disagreement, naming every mate on the loop). STEP export reuses
`interpreter._export_step_bytes`. Mass is the declared per-part mass
sum; COM is the mass-weighted average of each part's own realized
center-of-mass, world-transformed. Interference is a v1
axis-aligned-bounding-box overlap test over placed (non-
underconstrained) parts. INTEGRATION SEAM: a full mating-graph reader
over the compiler's contract-graph payload does not exist yet
(no numeric-mate-transform lowering) -- exercised today by callers that
already know the assembly's mate transforms.

<a id="mech-coverage"></a>
### `realizer/mech/coverage.py`

WO-62 D171/AD-32 deliverable 3: the feature-coverage ledger -- for
every hematite `then:` constructor word, is it realized by the v1 op
set or a NAMED skip (Rust `E0443`, contracts family offset 43)? Single
source of truth is `regolith-sem::EntityKind::from_constructor_word`
plus `regolith-lower::feature_program::project_op`'s literal arms
(mirrored here as committed data, same posture as `_schema/`
mirroring the Rust schemars export); `tests/realizer/mech/
test_coverage.py` verifies this ledger against a live compiler run
over the full corpus, so a diff between them is a definitional drift.
