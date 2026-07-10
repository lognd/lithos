# WO-64: flagship-1, the FDM printer (phase A: contract-first)

Status: todo (phase A dispatchable NOW; phases B/C gated on
WO-62 + WO-63 and dispatched as separate slices against this file)
Depends: phase A -- nothing beyond the landed toolchain (authoring
only). Phase B: WO-62 (assemblies), WO-63 (parity), stdlib as
landed. Phase C: phase B. NO schema bump any phase.
Language: corpus authoring (`.hema`/`.cupr`/`.fluo` +
magnetite.toml + records) + Python only for golden/corpus test
enrollment.
Spec: docs/spec/toolchain/31-flagships.md (NORMATIVE),
00-architecture.md AD-33 (+ AD-22's escalation discipline),
design-log 2026-07-09-cycle-31 D172; regolith/08 sec. 3
(contract-first = L0->L2 only); the track guides (01-04) for
authoring conventions.

## Goal (phase A)

`examples/flagships/printer_k1/` -- a complete FDM printer
architecture at L0->L2, `regolith check` clean with ZERO artifacts:
the machine exists as interfaces, budgets, promises, and claims
before any part is drawn, proving contract-first at machine scale
and producing the walls list that gates phase B.

## Phase A deliverables

1. **Project skeleton**: `examples/flagships/printer_k1/` with
   magnetite.toml (profiles: cost + mass), a README naming the
   machine's envelope targets (220x220x250 build volume class,
   24V system, single direct-drive extruder) as asserted givens
   with source positions (the parity attention list will show
   them -- that is correct and honest).
2. **System architecture** (the L2 deliverable): frames +
   interfaces for: base/frame structure, XY gantry motion, Z bed
   motion, extruder+hotend, bed (heated), electronics bay
   (controller board boundary as a cuprite interface), PSU,
   harness boundary, enclosure-optional seam. Budgets: total mass,
   BOM cost (magnetite cost profile), wall power, 24V rail current,
   hotend + bed thermal watts. Promise-backed claims wherever a
   number is demanded of a not-yet-designed artifact (derived
   (sf=...) loads on gantry members, motion accel targets ->
   force promises, melt-rate -> hotend watt promise).
3. **Track stubs with contracts, not bodies**: mech artifacts
   declared with `impl ... = todo!` where phase B will realize
   (honest deferral, ledgered); the controller board as a cuprite
   artifact with its port contract + an EBI decode `by select`
   carried over from the ebi_decode shape; the hotend melt path +
   part-cooling air path as fluorite nets at contract level; the
   harness as declared runs.
4. **Corpus enrollment**: flagship registered in the corpus test
   dicts (clean-check + fmt only at phase A -- goldens that pin
   diagnostics-empty state); contract-graph sheet ship-spec block
   (the WO-61 producer's machine-scale test) with its golden.
5. **The walls list**: every place the author WANTED a construct
   and stopped (missing vocabulary, missing solver, missing
   record) recorded in this WO's ledger as findings with spec
   citations -- the phase-B/C gate input and the real deliverable
   beside the architecture. NO side channels, NO invented syntax:
   a wall stops the leaf (AD-22/F96).

## Phase A acceptance criteria

- `regolith check` clean (zero diagnostics, zero waivers) over the
  whole flagship; budgets sum and close; every interface two-sided;
  `impl todo!` count = the declared artifact count (nothing
  realized, nothing skipped silently).
- Contract-graph sheet renders the machine legibly (golden);
  fmt-idempotent; ASCII.
- The walls list exists in the ledger (even if empty -- state so);
  every entry cites the spec section that governs the gap.
- `make check` green with the flagship enrolled; Status line
  updated to `phase A done (B/C gated)`.
