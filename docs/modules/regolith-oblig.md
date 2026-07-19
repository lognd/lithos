# regolith-oblig

Obligation, evidence, payload, and lockfile-row wire shapes plus
canonical CBOR encoding and domain-tagged content addressing (AD-5).
Regolith reference: `docs/spec/regolith/07-claims-and-evidence.md` and
the invariant ledger in `docs/spec/regolith/13-invariants.md` (INV-2
ladder safety, INV-10 hash stability, INV-12 waiver honesty). These
types are the single source of truth that crosses the FFI and lands on
disk: defined once here, generated into pydantic on the Python side
(WO-18). Claims lower to self-contained, serializable `Obligation`s;
`Evidence` is the only return type of discharge (WO-13). Every payload
kind below rides the D96 payload-ref channel and defines a WIRE SHAPE
only -- elaboration/lowering/solving lives in Python or `regolith-lower`,
never in this crate.

## assembly

`RealizedAssembly`: the mech realized-assembly payload (AD-25/AD-32,
WO-62 slice B deliverable 4; charter `30-geometry-lowering.md` sec.
1.4). One more first-class L4 IR by the AD-25 growth rule: a mating
graph over parts with `geometry::RealizedGeometry` digests that a
Python realizer (`regolith.realizer.mech.assembly`) solves to a placed
part set, dof states, extracted mass/COM, and pairwise interference
facts. Defines the wire shape only; nothing here reads source, touches
IO, solves a mate graph, or emits diagnostics.

## attestation

<a id="attestation"></a>

`Attestation`: an envelope over evidence (WO-21/AD-20; design in
`docs/spec/toolchain/20-solver-abstraction.md` sec. D-E/3). The
signature covers the evidence's existing content address and is never
a hash input itself, so a signed and an unsigned copy of the same
evidence key identically -- the envelope property this WO's acceptance
test proves. Signing/verification (ed25519, `cryptography`) lives in
Python (`harness/attest.py`); this crate defines the wire shape only
(AD-1: keys and processes talk to the world).

## claim

The claim AST: what `require <Group>:` bodies say (`docs/spec/regolith/
07-claims-and-evidence.md`, and `02` sec. 5 for time/frequency forms).
Claims lower to obligations (`obligation.rs`); evidence is the only
return type. Time and frequency claims (`peak`, `settles`, `rms(band=)`,
`stays_within(mask)`) are one family with different harness models;
windows (`during`, `within .. after`, `until`) build on events.

## contract_graph

`ContractGraphPayload`: the readable L2 contract-graph surface (WO-61;
interaction-surface/29 sec. 1.6 NORMATIVE; design-log D165/D167, the
WO-58 D2 completion). `BuildPayload` gains this schema-versioned record
so the `diagram.contract_graph` producer (a consumer, AD-22) binds to a
real payload instead of reaching into `regolith-ir`'s own `Interface`/
`Mating` types directly: nodes name every interface (with its
promise-slot count) and every artifact/part a system names; edges name
every mating (with side names and a connection-kind label). Mirrors the
`FlownetPayload`/`FramePayload` precedent (AD-5/AD-18).

## cost

`std.cost` record wire shapes (WO-54 deliverable 2; toolchain/27 sec.
1.2-1.3, 1.5; D147). AD-29's ledger rule: cost is a claim, an estimate
is evidence, and every priced number comes from a profile-selected,
hash-pinned record -- the compiler contains no prices, rates, or
currencies beyond unit machinery. Defines a rate record (shop/labor/
regional rates), a pricing record (vendor price breaks by quantity,
hash-pinned quotes/catalogs, `valid_until`-windowed), a unit-cost
record (RSMeans-shaped assemblies for civil takeoffs), and the
itemized-estimate `table`-kind payload that is a cost claim's evidence.
No prices, rates, or currency conversions are literal anywhere in the
compiler (AD-29, grep-provable).

## drawing

`DrawingModel`: the one documentation IR for shipped engineering
drawings, diagrams, and schedules (AD-27/D140, WO-50 deliverable 1;
`docs/spec/toolchain/25-drawings-and-artifacts.md` sec. 1.1). Per-track
producers (`regolith.backends.drawings`) project realized IRs
(`RealizedGeometry`, `RealizedLayout`, `FlownetPayload`) into this
schema; renderers (SVG mandatory, DXF/PDF siblings) serialize only this
IR to a page format -- no producer emits page description, no renderer
computes geometry. Every `Dimension` carries a `Provenance` field: the
schema makes an unattributable number on a sheet unrepresentable
(charter sec. 1 decision 3).

## encoding

Canonical encoding and domain-tagged content addressing (AD-5/AD-6).
The encoder itself lives in `regolith_util::canon` (AD-18, the bottom
of the layering, shared by `regolith-sem` snapshot hashes and
`regolith-oblig` obligation keys); this module re-exports it unchanged
so no downstream caller (`regolith-api`, `regolith-py`, the Python
facade, `make schema`) sees a path change, and owns the schemars export
that stays in `regolith-oblig` per AD-5 (`export_schemas`, feeding the
WO-18 pydantic codegen for obligations, evidence, claims, and lockfile
rows).

## evidence

`Evidence`: the only return type of discharge, and the generic margin
rule that decides a claim from a model result (`docs/spec/regolith/
07-claims-and-evidence.md`). Indeterminate is distinct from violated in
every surface (status, report, exit code). The margin rule is
implemented once, generically: `value + eps_model <= limit`; one toy
closed-form model is wired end-to-end (WO-13) to prove claim ->
obligation -> evidence -> cache. Structured coverage domains (D95 sec.
8.2) are either a continuous interval or an enumerated discrete set.

## field

`FieldDatum`: the datum-ledger entry a `compute` claim produces (WO-33
D98; `docs/spec/regolith/02` sec. 4/5, `07` sec. 2). A `compute` claim
lowers to one obligation whose successful evidence carries a `field`
payload (the WO-30 `PayloadRef` channel, `kind: "field"`); this type is
the ledger entry that names the datum, states its index axis, and
(once discharged) points at that payload. `payload: None` is the
honest pre-discharge state: with no field-producing model registered
in this repo's harness, it never resolves and consumers referencing it
stay `Indeterminate` (the chain rule of the ledger).

## flownet

`FlownetPayload`: the fluorite flownet payload (fluorite/03 sec. 2).
One schema-versioned, Rust-sourced record (AD-5 precedent) riding the
D96 payload-ref channel as the `flownet` payload kind: elaboration
(WO-32 deliverable 3) turns a `.fluo` flownet's geometry and topology
into this serialized, content-addressed record, and every fluid claim
lowers to an ordinary obligation carrying a `PayloadRef { kind:
"flownet", .. }` pointing at it. Solver packs (feldspar `fluids`/`prop`)
consume the payload and solve the network entirely pack-side. Nodes,
edges (`FlowEdge`/`EdgeKind`/`EdgeParams`/`Compliance`), state domains,
and scalar intervals are all defined here as wire shapes only.

## frame

`FramePayload`: the calcite structural frame payload (calcite/03 sec.
4). One schema-versioned, Rust-sourced record (AD-25 growth rule, kind
string `frame`, DECIDED D139/D145, single-homed in feldspar's kind
table): elaboration (WO-48 deliverable 3) turns a `.calx` structure's
members/transfers/loads into this serialized, content-addressed
record, and every structural claim lowers to an obligation carrying a
`PayloadRef { kind: "frame", .. }`. Closed-form beam checks and
feldspar's direct-stiffness frame analysis both consume the payload;
joints, member roles, releases, supports, load kinds, and frame
transfers are all wire shapes defined here, nothing solved.

## geometry

`RealizedGeometry`: the mech realized-geometry payload (AD-25/D128,
WO-42 deliverable 1; unified per D131). Promotes WO-22's Python forward
contract (`regolith.realizer.mech.interpreter.RealizedGeometry`/
`TopologySummary`) per the AD-22 promotion rule: this is now the source
of truth, and the hand-written Python mirror is deleted in the same
change. D131 (design-log 2026-07-08-cycle-25) fixed this as the one
wire shape for realized mech geometry after an earlier `stages`/
`RoughnessClass` shape drifted from the WO-32 `regolith-lower::extract`
seam's consumed record shape. `TopologySummary`, `Bounds`, `Bend`,
`Wall`, `PathSegment`, and `RoutedPath` are the constituent wire types.

## harness

`HarnessPayload`: the cuprite wiring-harness routed-runs payload
(WO-34, D99). One schema-versioned, Rust-sourced record (mirrors
`flownet::FlownetPayload`) content-addressed and carried on
`obligation::Obligation` payload refs: elaboration
(`regolith_lower::harness_lower`) turns a `harness:` block's declared
runs into this serialized record via the WO-32 extraction seam
(`regolith_lower::extract`) -- the same module a fluid edge reads, never
a second copy. Rule packs (E06xx ampacity rules) and mass budgets read
`run.length`/`run.bundle` off this payload (AD-22). Wire shape only.

## layout

`RealizedLayout`: the elec realized placed/routed board payload
(AD-25/D128, WO-42 deliverable 2), mirroring `geometry::
RealizedGeometry`. Covers the placed/routed board content WO-24's
KiCad layout adapter produces: board outline reference, component
placements, routed segments, a copper summary, extracted parasitic
slots, and a `.kicad_pcb` content-hash pin. Unlike deliverable 1, this
schema was built fresh from WO-42's own field list rather than
promoting an existing Python forward contract, since WO-24's
KiCad-unavailable deferral left no landed placement/routing model to
promote.

## lib

Crate root: obligation, evidence, and lockfile-row schemas; canonical
CBOR encoding; domain-tagged content addressing; schemars export
(`docs/spec/regolith/07-claims-and-evidence.md`). These types are the
single source of truth that crosses the FFI and lands on disk (AD-5):
defined once here, generated into pydantic on the Python side (WO-18).
Claims lower to self-contained, serializable `obligation::Obligation`s;
`evidence::Evidence` is the only return type of discharge (WO-13). This
section covers the module declarations and crate-level constants
(`SCHEMA_VERSION` and friends) that every payload module below builds
on.

## obligation

`Obligation`: the self-contained, serializable unit a claim lowers to;
its JSON serialization is the interchange format, golden-filed
(`docs/spec/regolith/07-claims-and-evidence.md` sec. 2). An obligation
carries everything a discharger needs with no back-reference to the
compiler: the claim, a content-addressed subject ref (`Given`), hints,
and any `sweep:` domain (`SweepDomain`). One obligation carries one
domain of a sweep. `content_hash`, `evidence_cache_key`, and
`evidence_cache_key_for_pack` derive the cache identity a discharger
looks up before re-running a model; `SnapshotRecord` is the lockfile
row shape this obligation resolves against.

## optimize

`OptimizationTrace`/`ChoicePoint` wire shapes (WO-55 deliverable 1;
toolchain/28-optimization.md; D159/D160). AD-30's ledger rule: the
optimization engine proposes candidates and evaluates them only
through the real pipeline (`build`/`staged_build` plus discharge) --
there is no private scoring path. `OptimizationTrace` is the search's
audit surface, checkpoint, and resume input; `ChoicePoint` is the D161
`by select` candidate set a discrete decision lowers to. Both are
payload kinds on the D96 ref channel (`optimize.trace`,
`optimize.choice`); the orchestrator (`regolith.orchestrator.optimize`,
Python) is the only writer.

## payload

`PayloadRef`: the generalized payload-ref channel (D96, sec. 8.3). One
channel carries hash-pinned, content-addressed payload refs of several
kinds -- realized/parametric geometry, meshes, tables, time/frequency
objects (spectra, profiles, masks), computed fields, flownets, and
plans -- so an external pack can compete across a fidelity hierarchy
without a new payload schema per kind. Refs are by digest only, never
inline bytes; resolution is an orchestrator-owned content-addressed
store (`orchestrator/payload_store.py`), never a pack's own IO.

## signature

Signature registry: the physics-model contract between the modeling
language and the harness, plus `impl <sig> by` records (data only;
`docs/spec/regolith/02` sec. 7). A signature names inputs, outputs, and
a validity domain; harness packs provide impls with a cost, an error
model, and a domain. Neither side sees the other's internals. No
harness code lives here (WO-13) -- just the records the orchestrator
matches on.

## solver

`SolverResponse`: the wire response an out-of-process solver returns
over the WO-20 subprocess adapter (AD-19; `docs/spec/toolchain/
20-solver-abstraction.md` sec. D-C/3). A non-Python solver receives a
serialized `DischargeRequest` on stdin and answers with one
`SolverResponse` JSON document on stdout; stderr is logs. Exit code 0
covers every COMPUTED outcome, including a violated claim -- the
response is a worst-corner prediction the shared margin rule decides,
never a verdict the solver decides for itself. Floats travel as exact
`u64` bit patterns (the `Evidence` convention) so text formatting can
never move a hash (INV-10).

## waiver

The todo/assume/waive ledger and `--release` refusal semantics
(`docs/spec/regolith/07-claims-and-evidence.md` and `12` sec. 3). A
`--release` build refuses while any todo/assume/unwaived-indeterminate
remains. Waivers match scoped against claims/rules; an evidence-
carrying waiver yields a deviation status; a waiver matching nothing is
an error (stale waiver). INV-2 (ladder safety) and INV-12 (waiver
honesty) live on this ledger's shape: a `WaiverRecord` carries the
accepted match set (obligation content hashes) and a `WaiverKind`
classification, and nothing here can carry a `Status` -- an acceptance
record references evidence but never modifies it, so no waiver can
convert `violated` into `discharged`.
