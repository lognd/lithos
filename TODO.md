# TODO -- the live queue

## START HERE (note to a fresh instance)

You are (probably) reading this with no memory of earlier cycles.
Orientation, in order:

1. `docs/README.md` -- what this project is (four declarative
   engineering languages over one shared regolith + the toolchain).
2. `docs/spec/regolith/` 01 -> 13; `13-invariants.md` is the ledger of
   every guarantee (INV-1..30) with its proof argument -- normative.
3. The language tracks: `docs/spec/hematite/` (mech, `.hema`),
   `docs/spec/cuprite/` (elec/computer, `.cupr`), `docs/spec/fluorite/`
   (fluid, `.fluo`, ratified cycle 20), `docs/spec/calcite/`
   (civil/architectural, `.calx`, chartered cycle 26, ELABORATED
   cycle 27 -- 02/03/04 + corpus exist, awaiting owner
   ratification).
4. `docs/spec/toolchain/00-architecture.md` -- NORMATIVE (AD-1..39);
   wins over any WO body it conflicts with. Charters 25 (drawings +
   quality audit), 26 (pattern libraries), 27 (costing) are the
   cycle-27 additions; 28 (optimization engine) and 29 (interaction
   surface: config/TUI/GUI) are cycle 30's; 30 (geometry depth),
   31 (flagships + parity bar), 32 (stdlib depth, cross-repo), and
   33 (CAM verification) are cycle 31's; 34-37 (topology, signal
   integrity, board correctness, design testing) are cycles 32-33's;
   38 (emission + release) is cycle 34's; 39 (stdlib organization)
   is cycle 35's; 40 (debug + bring-up) and 41 (artifact
   presentation) are cycle 36's.
5. `docs/workflow/README.md` -- ground rules + the DISPATCH
   PROTOCOL every agent follows + the WO dependency graph.
6. `docs/workflow/design-log/` -- dated ledgers of every finding (F1..) and
   decision (D1..); THE project history. Nothing here is re-decided
   without new evidence.
7. `examples/` -- the spec pressure corpus and golden workload.
8. SIBLING REPO `feldspar` (github.com/lognd/feldspar; locally
   checked out beside this repo) -- the external solver pack
   (M1 + symbolic core DONE through its WO-11). Its regolith-side
   contract asks live in
   `docs/spec/toolchain/20-solver-abstraction.md` sec. 7.

NAMES (settled; do not re-litigate): hematite / cuprite / fluorite /
calcite the languages; **magnetite** the package manager
(`magnetite.toml`; quarry + lodestone are RETIRED names, cycle 26
D132); **regolith** the toolchain/CLI/import name; **lithos** the
umbrella brand; **feldspar** the sibling solver pack. Dead names
(`mill`, `loom`, `dcad`, `deda`, `quarry`, `lodestone`, and
calcite's old life as the fluid draft with `.calc`) appear verbatim
only in `docs/workflow/design-log/` history and negative tests.

House rules that are easy to violate accidentally: ASCII only
(repo-wide, no exemptions); one word one idea (hematite/04 sec. 1);
every decision argued against the mantras (Unambiguous >
Intent-based > User-friendly); every cycle gets a dated design log;
version-bump the track headers you materially change; new
guarantees enter the invariant ledger WITH a proof argument in the
same change; extension strings live in EXACTLY ONE registry module
(`regolith-syntax`); schemas are single-sourced in Rust (`make
schema`, never hand-edit `_schema/`); only `compiler.py` imports
`regolith._core`; errors are DATA (diagnostics / typani Results);
stdout is data, logs to stderr; `make check` green before any WO
closes, flipping its `Status:` line in the same change. `make health`
(WO-106/D219) is the whole-repo bar -- one command, four legs (check +
fleet + demos + consistency), run it at cycle close to prove everything
still ships, every optimization still has a physical proof, and the
docs/goldens/waivers still agree (guide 23-health-gate.md).

Current state in one line: cycles 1-35 are CLOSED -- the whole
static core + all four tracks + optimization + emission v2 (every
fleet project ships release-clean, 15/15) + the cycle-35 rigor
flip (71 model-backed discharges, QA-verified, calc-book audit
trail, demos 16/16, graphite v0.2.0, feldspar pack 32) are done;
cycle 36 (owner directive 2026-07-15) is OPEN: hardware bring-up
(debug profile + taps + harness + jig, charter 40/AD-38) and
artifact presentation (charter 41/AD-39) -- the live queue is the
cycle-36 block below.

## DISPATCH QUEUE -- now lives in tickets.md (2026-07-18)

The live queue is `tickets.md` (frob-managed). Run `frob ticket
doable` for the current dispatchable set, `frob ticket list` for
everything, `frob ticket show <id>` for one ticket's scope/blockers/
acceptance. Each ticket's `acceptance:` field points at the WO doc
that carries the real spec body (`docs/workflow/work-orders/WO-nnn-*.md`)
-- tickets do not duplicate WO content, they schedule it.

WO `Status:` lines in `docs/workflow/work-orders/*.md` remain
HISTORICAL/narrative (open / honest-partial / done / in-progress as
last written by the dispatching agent) -- they are not re-derived
queue state. The one live queue is the ticket graph; do not read WO
Status lines as a second source of truth for what is dispatchable.

Non-WO queue items (docs sweeps, coordinator acceptance records,
etc.) that used to live inline in this file are also frob tickets
now (docs/feature kind as appropriate) -- see tickets.md.

- History: every completed cycle's ledger is in `docs/workflow/design-log/`;
  completed WO details are in each WO file's close-out. This file
  carries NO history by design (D137).
