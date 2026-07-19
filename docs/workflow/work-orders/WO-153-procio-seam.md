# WO-153 -- the in-house process-I/O seam: `regolith.procio` (D264 ruling 1)

Status: done (landed cycle-37: python/regolith/procio.py -- ToolArgs/
  ToolFailure/run_tool/expect_json -- all six call sites migrated
  [verilator_adapter.py, hdl/models.py, elec/kicad.py,
  elec/kicad_wrapper.py, toolenv.py, harness/adapter.py], docs/guide/
  18-external-tools.md updated, tests/test_procio.py green)
Language: Python (`python/regolith/procio.py`, new; call-site
  migrations across `harness/`, `realizer/elec/`, `toolenv.py`;
  docs update).
Spec: D264 ruling 1 (`docs/workflow/design-log/2026-07-16-cycle-37.md`:
  the process seam is IN-HOUSE, adopting lograder's two proven ideas
  -- typed-argv models, invocation-as-data with mandatory timeouts --
  on typani `Result` + the existing `toolenv` posture, WITHOUT
  depending on or vendoring lograder; six shipped call sites migrate;
  the AD-19 wire protocol is kept VERBATIM; `tools/health` stays raw,
  a recorded exception); `scratch_recon_cuprite_sim_gate.md` secs.
  3c/3d (the full subprocess call-site census and the seam design
  this WO implements, not re-derives -- `ToolArgs`/`run_tool`/
  `expect_json`, the migration list of six sites); `python/regolith/
  toolenv.py:1-18,102-199,231` (the existing tool-resolution registry
  this seam completes with the invocation half; toolenv itself is
  UNCHANGED except its version-probe internals route through the new
  seam); `python/regolith/harness/adapter.py:103`
  (`solve_via_subprocess`, the AD-19 wire-protocol gold standard whose
  contract -- JSON envelope in, one pydantic-validated
  `SolverResponse` out, typed `AdapterError` arms, schema-version
  handshake -- is preserved VERBATIM; only the spawn call moves);
  workflow README ground rule 1 (typani `Result` everywhere; pydantic
  v2 `ConfigDict(frozen=True)` models).

## Goal

No shipped `python/regolith` code (outside `tools/health` and
`tools/codegen`, a named exception) calls `subprocess.run`/`Popen`
directly; every tool invocation goes through one typed seam that
resolves through `toolenv`, requires an explicit timeout, and
returns a typani `Result`.

## Deliverables

1. `python/regolith/procio.py`: new module, module docstring citing
   lograder (`../lograder`) as the design precedent (proven ideas
   adopted, package not depended on) and the AD-19 contract as the
   shape it generalizes.
   - `ToolArgs`: a pydantic v2 frozen base class for typed per-verb
     argument models, each with an `emit() -> tuple[str, ...]`
     method; no call site concatenates raw flag strings after this
     WO. At minimum: `VerilatorLintArgs`, `VerilatorBinaryArgs`,
     `KicadDrcArgs`, `KicadLayoutArgs` (one model per (tool, verb)
     migrated in deliverable 2).
   - `ToolFailure`: the generalized failure type (tool name, resolved
     version if known, argv, returncode, bounded stderr excerpt,
     kind: not-found/timeout/nonzero), subsuming
     `verilator_adapter.py`'s existing `ToolFailure` shape and
     `kicad.py`'s `ToolUnavailable`/`LayoutFailed` union where their
     semantics coincide (a failure the seam itself detects, e.g.
     not-found or timeout, is ONE type; a domain-specific failure a
     caller derives from a zero-exit-code-but-wrong-output case may
     still be the caller's own error type built from a successful
     `ToolOutput`).
   - `run_tool(name: str, args: ToolArgs, *, cwd: Path, stdin: bytes
     = b"", timeout_s: float) -> Result[ToolOutput, ToolFailure]`:
     resolves the binary through `toolenv.resolve` (missing binary
     produces a `ToolFailure` carrying the EXISTING teaching message
     verbatim, never an auto-install attempt), spawns with the
     mandatory timeout (no default-`None` overload exists -- the
     parameter is positional-or-keyword REQUIRED), captures
     stdout/stderr + returncode, and DEBUG-logs every invocation
     (argv, cwd, resolved version, returncode) through the module
     logger per `~/.claude/refs/logging.md`.
   - `expect_json(output: ToolOutput, model: type[M]) ->
     Result[M, ToolFailure]`: validates stdout as the given pydantic
     model, wrapping a `ValidationError` into `ToolFailure` rather
     than letting it escape as a bare exception.
2. Six-site migration (per the recon's checklist, verbatim order):
   - `harness/models/hdl/verilator_adapter.py`: `run_verilator` and
     `verilator_version` route their spawn through `run_tool`; the
     module's existing `ToolFailure` becomes (or delegates to)
     `procio.ToolFailure`; behavior (timeout values, error fields)
     is UNCHANGED from the caller's point of view.
   - `harness/models/hdl/models.py`: `_run_testbench`'s inline
     `import subprocess` / bare `subprocess.run` call replaced by
     `run_tool` with the SAME timeout value it hardcodes today (60s),
     now declared as a named constant rather than a magic number
     inline.
   - `realizer/elec/kicad.py`: `run_layout`'s default runner goes
     through the seam; the injected-runner test/fake-KiCad seam
     (`realizer/elec/fake_kicad.py`) is UNCHANGED -- it keeps working
     because it is injected at a layer above `run_tool`, not replaced
     by it.
   - `realizer/elec/kicad_wrapper.py`: `_run_drc`'s raw
     `subprocess.run` (kicad-cli) and its warn-and-degrade-on-nonzero
     posture move onto `run_tool`; the degrade behavior itself is
     UNCHANGED, only the spawn call moves.
   - `toolenv.py`: `_probe_version`'s internals route through
     `run_tool` (this is the one call site inside `toolenv.py`
     itself; `toolenv.resolve` remains the registry `run_tool`
     resolves through -- no circular redesign, `_probe_version` is a
     leaf that happens to also want the seam's timeout/logging
     discipline).
   - `harness/adapter.py`: `solve_via_subprocess`'s spawn call moves
     onto `run_tool`; the AD-19 wire protocol (JSON envelope on
     stdin, one pydantic-validated `SolverResponse` on stdout, stderr
     bridged to logs, the 5 typed `AdapterError` arms, schema-version
     handshake) is preserved VERBATIM -- this WO changes the spawn
     mechanism underneath the contract, never the contract itself.
3. Docs: `docs/guide/18-external-tools.md` (or the project's
   equivalent external-tools guide page) gains a section naming
   `procio` as the one process seam, the `tools/health`/
   `tools/codegen` exception, and a pointer to `ToolArgs` as the
   pattern for adding a new tool verb.
4. Python unit tests for `procio.py` itself: `run_tool` on a
   not-found binary returns `Err(ToolFailure)` carrying the teaching
   message (no auto-install attempted, no exception raised); a
   timeout returns `Err(ToolFailure)` with `kind="timeout"`;
   `expect_json` on malformed stdout returns `Err`, not a raised
   `ValidationError`.

## Out of scope

- `tools/health/{check,fleet,demos,consistency}.py` and
  `tools/codegen/generate_codes.py` -- named exception (D264 ruling
  1): dev tooling outside the shipped package, migrating them buys
  nothing and couples the health harness to the package under test.
- Any new tool registration in `toolenv.py` (no new tools this WO --
  only routing existing spawns through the seam).
- lograder as a real dependency -- the owner item recorded in the
  recon sec. 9.1 is NOT re-opened here; this WO implements the
  in-house recommendation. If the owner overrides the posture call,
  that is a future WO, not a mid-flight scope change to this one.
- Any schema change (this WO adds no wire-format or `SCHEMA_VERSION`
  surface at all).
- WO-154..158 (spec deltas, the sim gate itself, timing closure,
  fleet adoption, the demo) -- this WO only builds the seam they all
  depend on.

## Acceptance

- `grep -rn 'subprocess\.\(run\|Popen\|call\|check_call\|check_output\)' python/regolith`
  returns NO hits outside `python/regolith/procio.py` itself (the
  seam's own internals are the only place a raw subprocess call may
  appear).
- `grep -rn 'subprocess\.\(run\|Popen\|call\|check_call\|check_output\)' tools/health tools/codegen`
  is UNCHANGED from pre-WO state (the recorded exception; this grep
  documents it is intentional, not a residual).
- `uv run pytest tests -k procio -q` green, covering: not-found
  (no auto-install), timeout, nonzero-exit, malformed-JSON-stdout.
- `uv run pytest tests/harness tests/realizer -q` green (all six
  migrated call sites' existing test coverage passes unchanged --
  proves the migration preserved behavior).
- `uv run pytest tests -k adapter_wire_protocol -q` (or the AD-19
  wire-protocol test's actual name) green with no change to its
  assertions -- proves `solve_via_subprocess`'s contract is verbatim.
- `docs/guide/18-external-tools.md` (or equivalent) has a `procio`
  section, checkable by `grep -q procio docs/guide/18-external-tools.md`
  or the project's actual guide filename.
- `make check` green.

## Escalation

If a migrated call site's existing error-handling behavior cannot be
preserved exactly under the seam's generalized `ToolFailure` shape
(a caller relies on a field or exception type `procio.ToolFailure`
does not carry), escalate to the coordinator before narrowing the
seam's contract or leaving the call site unmigrated -- do not invent
a seventh bespoke failure type.
