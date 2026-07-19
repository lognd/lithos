# The lithos system model (`design/lithos.strata`)

This document explains `design/lithos.strata`: what it models, why the
node partition is shaped the way it is, and the known gaps between what
a `frob sys audit` capability scanner can see and what the code actually
does. It exists because `frob sys audit`'s finding messages point here
(`frob:doc docs/workflow/strata-system-model.md#<anchor>` on every node/
flow/claim/assume/waive in the model) -- read this before touching the
model, not the other way around.

House style follows `../../../feldspar/design/feldspar.strata` (a sibling
repo's already-landed model): every node/flow/claim carries a
`frob:doc` edge into this file plus a `frob:ticket` edge to the ticket
that landed it (T-0034 for the whole model; T-0035 for the follow-on
kill-switch work).

## What this is

`design/lithos.strata` is lithos's real system topology, not an
aspirational one -- every `code` glob, every `may` capability, and every
`flow` was checked against the actual source before being written down
(see the model file's own header comment for the verification log: AD-4
confirmed by direct grep, the regolith_py partition checked against the
real cross-import graph, every capability traced to a call site).

### The nodes

- **rust_core** (`crates/**`, `fuzz/**`): the Rust compiler workspace --
  parse/sem/lower/schema/oblig/diag/qty/util/ls/py-bindings. Pure compute,
  plus a few real capabilities documented below.
- **ffi_bridge** (`python/regolith/compiler.py` only): the ONE file that
  imports `regolith._core` (AD-4). Split out of `regolith_py` specifically
  so the code-binding partition has exactly one node per file (tier-2
  code binding, `SYS003`, requires this) and so AD-4's intent is visible
  in the model's shape even though the flow-graph claim for it had to be
  dropped (see "AD-4's actual guarantee" below).
- **regolith_py** (everything else under `python/regolith/**`): kept as
  ONE node rather than split by subpackage. `backends`, `cli`,
  `harness`, `orchestrator`, `realizer`, `magnetite`, and `docgen`
  cross-import each other in both directions (e.g. `cli` imports
  `orchestrator`+`backends`+`harness`; `orchestrator` imports
  `harness.models`+`magnetite`; `realizer` imports `harness`+`backends`).
  A node-per-subpackage partition would fight this real cycle and
  surface as `SYS003` tier-2 conformance noise for zero design payoff --
  the coarsening the draft asked for.
- **stdlib_records** (`stdlib/**`, `tools/stdlib/**`): committed record
  packages (fastener series, IAPWS water properties, E-series resistor
  values, etc.) plus their generators. Data, never executed.
- **tooling** (`tools/health/**`, `tools/codegen/**`): fleet-census/QA
  and schema-generation scripts.
- **demos** (`demos/**`, `examples/**`): end-to-end proof packs.
- **vscode_ext** (`editors/vscode/**`): the VS Code extension, talking to
  `regolith-ls` over LSP stdio at runtime, plus its own dev/test tooling.
- **feldspar_pack**, **kicad_cli**, **hdl_tools**: external dependencies
  with no `code` glob (see "known gaps" below).
- **operator**: the human/CI entry point (`frob sys audit`'s THREAT003
  check requires a real `foreign`-trust source for a `weakness:CWE-78`
  discharge to prove a mitigation chokepoint rather than being vacuously
  accepted -- see feldspar's `regolith_consumer` for the same pattern).

### AD-4's actual guarantee vs. what the flow graph can prove

The coordinator draft proposed `assert c_only_bridge_ffi noflow
regolith_py -> rust_core`. `frob sys audit` REFUTED this the first time
it ran: `regolith_py` legitimately reaches `rust_core` through
`f_py_bridge` + `f_bridge_rust` (`regolith_py` calls into `ffi_bridge`,
which calls into `rust_core`) -- that path IS the point of the bridge,
not a violation of it. AD-4's real guarantee is narrower and is a
code-level property, not a flow-graph one: no file OTHER than
`compiler.py` ever contains `from regolith import _core`. That was
verified directly (`grep -rn "_core" python/regolith --include=*.py`
shows exactly one non-comment, non-`.pyi` hit, at `compiler.py:23`) and
is enforced continuously by `make guard-core`'s grep gate -- not
something this flow-graph model can independently express, because the
compiled `_core.abi3.so` extension lives at
`python/regolith/_core.abi3.so`, outside the `crates/**` glob, so
tier-2 import conformance can't see that import either. The model
instead carries `assert c_reaches_rust_via_bridge reach regolith_py ->
rust_core`, documenting the intended (and only legitimate) path.

## Known gaps, not gamed away

Every gap below is either a real, intentional model limitation or a
scanner blind spot -- discharged honestly (fixed where fixable, waived
in-design with a written reason and a follow-on ticket where not),
never worked around by weakening a claim or deleting a `may`.

- **`ffi` is scanner-invisible.** Neither `ffi_bridge` (Python side:
  `from regolith import _core`, importing a compiled `.abi3.so`) nor the
  Rust-side `regolith-py` pyo3 crate under `rust_core` has an import
  pattern the capability scanner's needle set recognizes for a compiled
  extension. Both keep `may "ffi"` declared anyway (the capability is
  real); `ffi_bridge` additionally carries `waive "SYS101:ffi"` since the
  scanner will never observe it -- the exact same posture feldspar's
  `core_api` node documents for its own `_feldspar` import.
- **Scanner substring false positives on "eval".** `ffi_bridge`
  (`compiler.py`), `stdlib_records` (`tools/stdlib/gen_iapws_water.py`),
  and `demos` (optimizer callback naming: `evaluator`,
  `thickness_evaluator_for`) all trip the scanner's `eval` needle on the
  English words "evaluated"/"evaluator"/"evaluate" inside comments,
  docstrings, and identifiers -- never a builtin `eval()` call (verified
  by direct grep: no `eval(` call site exists in any of these trees).
  Each carries an in-design `waive "SYS100:eval"` with the exact false-
  positive site named. This is the same class of gap feldspar's
  `domains` node documents for `calib/harness.py`'s `.eval(` method
  calls on its own `Expr` type.
- **`regolith_py`'s real `eval` capability is dynamic-load, not
  builtin-eval.** `plugins.py`'s `entry_points(group=
  PLUGIN_ENTRY_POINT_GROUP)` (AD-26's `regolith.plugins` discovery seam)
  is genuine dynamic code loading -- the same "eval" capability kind
  feldspar's `solve/packs.py` declares for the identical
  `importlib.metadata` entry-point pattern. Declared for that reason,
  not for a literal `eval()` call (there is none in the package).
- **External dependency nodes have no `code` glob.** `feldspar_pack`
  (discovered via the `regolith.plugins` entry point, lives in its own
  sibling repo), `kicad_cli`, and `hdl_tools` (external binaries resolved
  via `toolenv.py`) are genuinely external -- there is no lithos-owned
  source tree to bind a glob to. Same posture as feldspar's
  `regolith_consumer`/`ccx_solver`/`ngspice_solver` nodes.
- **`operator` is a synthetic entry point, not a code node.** THREAT003's
  mitigation-chokepoint check requires a real `foreign`-trust source for
  a `weakness:CWE-78:<node>` `NoFlow` claim to prove anything (rather
  than being vacuously accepted) -- there is no other node in this model
  representing "whoever runs `regolith build`, `make health`, a demo
  script, or opens the VS Code extension", so `operator` was added
  (`trust foreign`, no code glob) purely to give those four assumptions
  a real foreign source, mirroring feldspar's `regolith_consumer`.
- **No real kill-switch flag exists yet for `exec`/`net` (LINT004).**
  `regolith_py`, `demos`, `tooling`, and `vscode_ext` all hold `exec`
  (and `regolith_py` also holds `net`, via `magnetite/client.py`'s
  `RegistryClient`) with no declared `attr flag=<id>` disable switch.
  The existing `REGOLITH_*` env vars (`REGOLITH_LOG`,
  `REGOLITH_UPDATE_GOLDEN`, `REGOLITH_OPTIMIZE_BUDGET_EVALS`,
  `REGOLITH_DEBUG_TAPS`) are unrelated knobs -- none of them gate
  subprocess spawning or network fetches. Each node carries an in-design
  `waive "LINT004"` naming this gap honestly, with **T-0035** filed as
  the follow-on ticket to add a real `REGOLITH_NO_EXEC`/
  `REGOLITH_OFFLINE` flag -- the same "a path override is not a disable
  flag" precedent feldspar's `fea`/`elec` nodes set for
  `FELDSPAR_CCX`/`FELDSPAR_NGSPICE` (T-0016 there).

## Runtime-dispatch edges

Unlike feldspar's `plan -> fea`/`plan -> elec` registry-dispatch edges
(no import, but a real call through a frozen `SolverRegistry`), lithos's
current flow set has no non-import runtime-dispatch edges to document --
every declared flow corresponds to a real import or subprocess spawn.
If a future model revision adds one (e.g. a plugin-discovered backend
called only through `regolith.plugins`' `register_fn`), document it here
under this heading, following feldspar's `#what-this-is` precedent for
its `f_plan_fea`/`f_plan_elec` flows.
