"""The std.hdl `Model` pack (WO-82 deliverables 1-3; AD-19/AD-35;
D202 cycle 33 source-generic `hdl.build`).

Three check-mode claim kinds (`hdl.build`/`hdl.sim_assert`/
`hdl.equiv_directed`), backed by a MIX of source-generic and
fixture-bound `regolith.harness.model.Model`s. `hdl.build` (D202) is
SOURCE-GENERIC: ONE model instance verilates whatever bytes and
filename the REQUEST itself carries, with NO fixture identity and no
hardcoded top module (see `HdlBuildModel`'s docstring for the WO-89
collision this closes). `hdl.sim_assert` gained a SECOND,
source-generic model in WO-155 (D264): `HdlSimAssertGenericModel`
discharges any request naming a declared `sim_stimulus`
(`signal_table`) payload by generating a testbench harness FROM its
directed vectors (`build_generated_testbench`) rather than reading a
hand-authored fixture file -- the same D202 generalization applied
one claim kind later. `hdl.sim_assert`/`hdl.equiv_directed` ALSO stay
registered fixture-bound (registered per `examples/hdl/` fixture with
a landed testbench, the cuprite/09 D120 calibration corpus) for the 5
existing calibration fixtures -- WO-155 is additive, not a
replacement: a request with no declared stimulus never matches the
generic model's signature, so the fixture path is unchanged.
All share the ONE discharge/margin path (`Model.discharge`): value=excess
(count of failures), eps=0.0, limit=0.0 (upper-bound sense -- "zero
verilator/testbench failures"); a tool failure or an unsupported regime
(VHDL: no front-end in this environment) short-circuits to
`Err(DomainError)` so the registry renders indeterminate evidence, never
a false pass (conservative-or-silent, charter D3 precedent).

Payload port: `hdl_src` (kind `hdl_source`) carries the hash-pinned raw
HDL bytes (D96 payload channel, matching std.cam's `plan` port shape),
and its `PayloadRef.origin` carries the source's own filename -- what
`hdl.build` reads to pick the `-sv` flag, since it no longer has a
fixture to read one from. The dialect/regime is a REQUIRED regime tag
for `hdl.sim_assert`/`hdl.equiv_directed` (matches the `.cupr`
fixture's own `by extern(ref, <regime>)` tag); `hdl.build` checks the
regime itself at `estimate` time instead (only to route the VHDL
deferral -- every other regime verilates the same way).
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from typani.result import Err, Ok, Result

from regolith.harness.errors import DomainError, HarnessError
from regolith.harness.model import DischargeRequest, Model, Prediction
from regolith.harness.models.hdl.fixtures import (
    VHDL_REGIMES,
    FixtureSpec,
)
from regolith.harness.models.hdl.signal_table import (
    SignalTable,
    check_signal_table_provenance,
)
from regolith.harness.models.hdl.verilator_adapter import (
    ToolFailure,
    run_verilator,
    verilator_version,
)
from regolith.harness.signature import ClaimSense, ModelSignature
from regolith.logging_setup import get_logger
from regolith.procio import VerilatorBinaryArgs, VerilatorLintArgs, run_argv
from regolith.toolenv import resolve as resolve_tool

# `_run_testbench`'s compiled sim-binary run (WO-153 deliverable 2): the
# SAME 60s value this module hardcoded inline before the seam existed,
# now a named constant instead of a magic number.
_TESTBENCH_RUN_TIMEOUT_S = 60.0

if TYPE_CHECKING:
    from regolith.orchestrator.payload_store import PayloadResolver

_log = get_logger(__name__)

# frob:doc docs/modules/py-harness.md#models-hdl
SRC_PORT = "hdl_src"
# frob:doc docs/modules/py-harness.md#models-hdl
SRC_KIND = "hdl_source"

# WO-155 (D264): the `sim_stimulus` payload port (kind `signal_table`,
# charter 38 sec. 5 registry addition) beside `hdl_src` -- the
# hash-pinned directed stimulus/expectation vector table a `require:
# sim(<stimulus-ref>)` clause resolves by digest
# (cuprite/03-behavioral-layer.md sec. 2).
# frob:doc docs/modules/py-harness.md#models-hdl
STIMULUS_PORT = "sim_stimulus"
# frob:doc docs/modules/py-harness.md#models-hdl
STIMULUS_KIND = "signal_table"

# frob:doc docs/modules/py-harness.md#models-hdl
CLAIM_BUILD = "hdl.build"
# frob:doc docs/modules/py-harness.md#models-hdl
CLAIM_SIM_ASSERT = "hdl.sim_assert"
# frob:doc docs/modules/py-harness.md#models-hdl
CLAIM_EQUIV_DIRECTED = "hdl.equiv_directed"

_PASS_RE = re.compile(r"^PASS (\S+) cycle=(\d+) value=(-?\d+)$")
_FAIL_RE = re.compile(r"^ASSERT FAIL (\S+) cycle=(\d+) expected=(-?\d+) got=(-?\d+)$")
_SIM_OK_RE = re.compile(r"^SIM_OK vectors=(\d+)$")
_SIM_FAIL_RE = re.compile(r"^SIM_FAIL vectors=(\d+) errors=(\d+)$")


def _tool_failure_message(fail: ToolFailure) -> str:
    """One rendering for a `ToolFailure` -> a `DomainError` message
    (AD-19: adapter failure is INDETERMINATE evidence, stderr cited)."""
    return (
        f"verilator {fail.version} failed (argv={list(fail.argv)}, "
        f"returncode={fail.returncode}): {fail.stderr_excerpt}"
    )


def _resolve_payload(
    request: DischargeRequest,
    resolver: PayloadResolver | None,
    *,
    port: str,
    model_id: str,
) -> Result[bytes, HarnessError]:
    """Resolve any one of this request's payload ports to bytes (WO-155:
    generalized from the `hdl_src`-only `_resolve_src` so the same
    digest-resolution path serves the new `sim_stimulus` port too --
    NO DUPLICATION of the resolver-call/error-wrapping idiom)."""
    ref = request.payloads.get(port)
    if ref is None:  # pragma: no cover -- signature match guarantees it
        return Err(DomainError(model_id=model_id, message=f"no {port} payload"))
    if resolver is None:
        return Err(
            DomainError(
                model_id=model_id, message="no payload store resolver configured"
            )
        )
    resolved = resolver(ref.digest)
    if resolved.is_err:
        return Err(
            DomainError(
                model_id=model_id,
                message=(
                    f"payload {ref.digest} did not resolve: "
                    f"{resolved.danger_err.message}"
                ),
            )
        )
    return Ok(resolved.danger_ok)


def _resolve_src(
    request: DischargeRequest,
    resolver: PayloadResolver | None,
    *,
    model_id: str,
) -> Result[bytes, HarnessError]:
    return _resolve_payload(request, resolver, port=SRC_PORT, model_id=model_id)


class _HdlModel(Model):
    """Shared spine for the FIXTURE-BOUND `hdl.sim_assert`/
    `hdl.equiv_directed` models (one instance per fixture -- they
    genuinely need a per-fixture hand-authored testbench, D202's
    "sim/equiv keep fixtures" carve-out). `hdl.build` (D202) is
    source-generic and does NOT extend this spine -- see
    :class:`HdlBuildModel`."""

    _fixture: FixtureSpec
    _claim_kind: str

    def __init__(self, fixture: FixtureSpec) -> None:
        self._fixture = fixture

    @property
    # frob:doc docs/modules/py-harness.md#models-hdl
    def version(self) -> str:
        """Model version folds the verilator version (AD-19 cache-key
        law: an upgraded tool invalidates exactly its own cached
        evidence -- resolved once per process, see verilator_adapter)."""
        return f"1+verilator{verilator_version()}"

    @property
    # frob:doc docs/modules/py-harness.md#models-hdl
    def cost(self) -> int:
        """`hdl.build` is cheapest (lint-only); simulation costs more."""
        return 1 if self._claim_kind == CLAIM_BUILD else 3

    @property
    # frob:doc docs/modules/py-harness.md#models-hdl
    def signature(self) -> ModelSignature:
        return ModelSignature(
            name=f"{self._claim_kind.replace('.', '_')}_{self._fixture.fixture_id}",
            claim_kind=self._claim_kind,
            sense=ClaimSense.upper_bound(),
            inputs=(),
            domain=("hdl", self._claim_kind.split(".", 1)[1], self._fixture.fixture_id),
            payload_kinds={SRC_PORT: SRC_KIND},
            required_regimes=(self._fixture.regime,),
        )

    # frob:doc docs/modules/py-harness.md#models-hdl
    # frob:waive TEST005 reason="measured 50.0% branch on 2026-07-19; backfill T-0036"
    def estimate(
        self, request: DischargeRequest, *, resolver: PayloadResolver | None = None
    ) -> Result[Prediction, HarnessError]:
        raise NotImplementedError

    def _vhdl_guard(self) -> Result[Prediction, HarnessError] | None:
        """VHDL fixtures defer EVERY hdl.* claim: no front-end exists in
        this pack for either verilator (VHDL-incapable) or `ghdl` (no
        adapter implemented) regardless of `ghdl`'s PATH state -- the
        deferral is a WO-82 scope cut, not a `ghdl`-absence detection,
        but the message still honestly reports `ghdl`'s live status
        (checked via `regolith.toolenv`, never assumed) plus install
        guidance for a reader who wants to add the front-end."""
        if self._fixture.regime in VHDL_REGIMES:
            ghdl = resolve_tool("ghdl", use_cache=False, probe_version=False)
            ghdl_note = (
                f"ghdl found at {ghdl.path} but no ghdl adapter is wired up"
                if ghdl.available
                else f"ghdl not found either. Install it: {ghdl.spec.install.render()}"
            )
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=(
                        f"{self._fixture.fixture_id}: VHDL ({self._fixture.regime}) "
                        "has no verilator front-end (verilator is Verilog/SV-only); "
                        f"{ghdl_note} -- deferred, not simulated (WO-82 ledger)"
                    ),
                )
            )
        return None


# frob:doc docs/modules/py-harness.md#models-hdl
class HdlBuildModel(Model):
    """`hdl.build` (D202, cycle 33): SOURCE-GENERIC -- ONE model, not
    one per fixture. It verilates the REQUEST's own `hdl_src` bytes
    against whatever top module verilator's OWN elaboration derives
    from those bytes; it never hardcodes a fixture-pinned top-module
    string.

    WO-89 proved the fixture-bound shape broken: `ModelRegistry.select`
    cannot distinguish two `hdl.build` models sharing a dialect
    (regime-subset match, tie broken by cost/id) -- given TWO same-
    dialect `by extern` edges in one build, the wrong model verilated
    the wrong top module. This model has no "wrong fixture" to pick:
    every request carries its own bytes and its own filename (the
    `hdl_src` payload's `PayloadRef.origin`, the SAME extern ref
    `_translate_hdl` resolved), so two requests never collide on a
    shared model instance -- each discharge is independent. Omitting
    `--top-module` is deliberately safe here: every corpus HDL source
    declares exactly one un-instantiated top-level module (helper
    submodules are always instantiated by it), which is exactly the
    shape verilator auto-derives a top from without being told one.

    `is_sv` (the `-sv` flag) is derived from the request's own
    filename extension (`.sv`) rather than a fixture flag -- one more
    piece of per-fixture state this model no longer needs.

    VHDL requests still defer with the named "no VHDL frontend"
    reason (`required_regimes=()` matches every regime tag, including
    `vhdl2008` -- the guard below is what keeps verilator, which has
    no VHDL front-end, from ever being invoked on VHDL bytes)."""

    @property
    # frob:doc docs/modules/py-harness.md#models-hdl
    def version(self) -> str:
        """Model version folds the verilator version (AD-19 cache-key
        law: an upgraded tool invalidates exactly its own cached
        evidence -- resolved once per process, see verilator_adapter)."""
        return f"1+verilator{verilator_version()}"

    @property
    # frob:doc docs/modules/py-harness.md#models-hdl
    def cost(self) -> int:
        """`hdl.build` is cheapest (lint-only)."""
        return 1

    @property
    # frob:doc docs/modules/py-harness.md#models-hdl
    def signature(self) -> ModelSignature:
        return ModelSignature(
            name="hdl_build",
            claim_kind=CLAIM_BUILD,
            sense=ClaimSense.upper_bound(),
            inputs=(),
            domain=("hdl", "build"),
            payload_kinds={SRC_PORT: SRC_KIND},
            # No fixture/dialect to require: this model discharges
            # whatever non-VHDL regime the request names (checked at
            # `estimate` time, D202) -- an empty requirement is a
            # trivial match for every regime tag a request carries.
            required_regimes=(),
        )

    def _vhdl_guard(
        self, regime: str | None
    ) -> Result[Prediction, HarnessError] | None:
        """VHDL requests defer this claim: no front-end exists in this
        pack for either verilator (VHDL-incapable) or `ghdl` (no
        adapter implemented) regardless of `ghdl`'s PATH state -- the
        deferral is a WO-82 scope cut, not a `ghdl`-absence detection,
        but the message still honestly reports `ghdl`'s live status
        (checked via `regolith.toolenv`, never assumed) plus install
        guidance for a reader who wants to add the front-end."""
        if regime in VHDL_REGIMES:
            ghdl = resolve_tool("ghdl", use_cache=False, probe_version=False)
            ghdl_note = (
                f"ghdl found at {ghdl.path} but no ghdl adapter is wired up"
                if ghdl.available
                else f"ghdl not found either. Install it: {ghdl.spec.install.render()}"
            )
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=(
                        f"VHDL ({regime}) has no verilator front-end "
                        f"(verilator is Verilog/SV-only); {ghdl_note} -- "
                        "deferred, not simulated (WO-82 ledger)"
                    ),
                )
            )
        return None

    # frob:doc docs/modules/py-harness.md#models-hdl
    def estimate(
        self, request: DischargeRequest, *, resolver: PayloadResolver | None = None
    ) -> Result[Prediction, HarnessError]:
        regime = request.regimes[0] if request.regimes else None
        guard = self._vhdl_guard(regime)
        if guard is not None:
            return guard
        src = _resolve_src(request, resolver, model_id=self.model_id)
        if src.is_err:
            return Err(src.danger_err)
        ref = request.payloads.get(SRC_PORT)
        filename = Path(ref.origin).name if ref is not None and ref.origin else "src.v"
        is_sv = filename.endswith(".sv")
        with tempfile.TemporaryDirectory(prefix="regolith_hdl_build_") as tmp:
            work = Path(tmp)
            hdl_path = work / filename
            hdl_path.write_bytes(src.danger_ok)
            # `-Wno-DECLFILENAME`: these fixtures deliberately hold
            # multiple modules/interfaces per file (hierarchy rows,
            # cuprite/09 sec. 1) -- verilator's filename-matches-first-
            # module convention is a style lint unrelated to build
            # correctness, so it does not gate `hdl.build`'s verdict.
            # No `--top-module`: verilator derives the sole
            # un-instantiated top module from the request's own bytes
            # (D202 -- the source-generic posture).
            args = VerilatorLintArgs(filename=hdl_path.name, is_sv=is_sv)
            result = run_verilator(args, cwd=work)
            if result.is_err:
                _log.info("%s: verilate failed", self.model_id)
                return Err(
                    DomainError(
                        model_id=self.model_id,
                        message=_tool_failure_message(result.danger_err),
                    )
                )
        _log.debug("%s: verilated cleanly", self.model_id)
        return Ok(Prediction(value=0.0, eps=0.0, coverage=1.0))


def _run_testbench(
    fixture: FixtureSpec, src: bytes, *, model_id: str
) -> Result[tuple[int, int, str], HarnessError]:
    """Build+run the fixture's testbench under `verilator --binary`;
    returns `(vectors, errors, note)` or `Err(DomainError)` on any tool
    failure (build or the run itself -- both are AD-19 adapter seams)."""
    if fixture.testbench_src is None:  # pragma: no cover -- caller-guaranteed
        return Err(
            DomainError(
                model_id=model_id, message=f"{fixture.fixture_id}: no testbench"
            )
        )
    with tempfile.TemporaryDirectory(prefix="regolith_hdl_sim_") as tmp:
        work = Path(tmp)
        (work / fixture.hdl_filename).write_bytes(src)
        tb_path = work / f"{fixture.testbench_top}.sv"
        tb_path.write_text(fixture.testbench_src)
        args = VerilatorBinaryArgs(
            top_module=fixture.testbench_top,
            tb_filename=tb_path.name,
            hdl_filename=fixture.hdl_filename,
        )
        build = run_verilator(args, cwd=work)
        if build.is_err:
            return Err(
                DomainError(
                    model_id=model_id, message=_tool_failure_message(build.danger_err)
                )
            )
        exe = work / "obj_dir" / f"V{fixture.testbench_top}"
        spawned = run_argv(
            (str(exe),), cwd=work, timeout_s=_TESTBENCH_RUN_TIMEOUT_S, tool=exe.name
        )
        if spawned.is_err:
            fail = spawned.danger_err
            return Err(
                DomainError(
                    model_id=model_id,
                    message=f"simulation binary failed to run: {fail.stderr_excerpt}",
                )
            )
        proc = spawned.danger_ok
        lines = proc.stdout.decode("ascii", errors="replace").splitlines()
        first_fail = ""
        vectors = 0
        errors = 0
        for line in lines:
            m = _SIM_OK_RE.match(line)
            if m:
                vectors = int(m.group(1))
                continue
            m = _SIM_FAIL_RE.match(line)
            if m:
                vectors = int(m.group(1))
                errors = int(m.group(2))
                continue
            m = _FAIL_RE.match(line)
            if m and not first_fail:
                name, cycle, expected, got = m.groups()
                first_fail = (
                    f"assertion {name!r} failed at cycle {cycle}: "
                    f"expected={expected} got={got}"
                )
        if vectors == 0:
            return Err(
                DomainError(
                    model_id=model_id,
                    message=(
                        "simulation produced no SIM_OK/SIM_FAIL marker "
                        f"(stdout: {proc.stdout!r})"
                    ),
                )
            )
        note = first_fail or f"{vectors} directed vector(s), 0 failures"
        return Ok((vectors, errors, note))


# frob:doc docs/modules/py-harness.md#models-hdl
class HdlSimAssertModel(_HdlModel):
    """`hdl.sim_assert`: directed fixture vectors + assertions through
    the verilated DUT (deliverable 2). Registered only for fixtures with
    a landed testbench (`SIMULATED_FIXTURE_IDS`, WO-82 scope cut)."""

    _claim_kind = CLAIM_SIM_ASSERT

    # frob:doc docs/modules/py-harness.md#models-hdl
    def estimate(
        self, request: DischargeRequest, *, resolver: PayloadResolver | None = None
    ) -> Result[Prediction, HarnessError]:
        guard = self._vhdl_guard()
        if guard is not None:
            return guard
        src = _resolve_src(request, resolver, model_id=self.model_id)
        if src.is_err:
            return Err(src.danger_err)
        outcome = _run_testbench(self._fixture, src.danger_ok, model_id=self.model_id)
        if outcome.is_err:
            return Err(outcome.danger_err)
        vectors, errors, note = outcome.danger_ok
        _log.debug(
            "%s: %s (vectors=%d errors=%d)", self.model_id, note, vectors, errors
        )
        return Ok(Prediction(value=float(errors), eps=0.0, coverage=1.0))


# frob:doc docs/modules/py-harness.md#models-hdl
class HdlEquivDirectedModel(_HdlModel):
    """`hdl.equiv_directed`: directed input-space equivalence between the
    fixture's paired Verilog and an ORACLE-TRANSCRIBED reference of the
    native `.cupr` `spec:` block (deliverable 3) -- NEVER claimed formal,
    NEVER claimed compiler-executed (see fixtures.py module doc + the
    WO-82 ledger for why: cuprite's ConverterGraph has no Python-
    reachable evaluation FFI yet). The evidence note always states the
    vector count and the "oracle-transcribed, not compiler-executed"
    caveat verbatim so this tier can never be mistaken for more than it
    is; a future FFI (logged as a cycle-33 follow-up) upgrades this
    model in place without changing its claim kind or payload shape."""

    _claim_kind = CLAIM_EQUIV_DIRECTED

    # frob:doc docs/modules/py-harness.md#models-hdl
    def estimate(
        self, request: DischargeRequest, *, resolver: PayloadResolver | None = None
    ) -> Result[Prediction, HarnessError]:
        guard = self._vhdl_guard()
        if guard is not None:
            return guard
        src = _resolve_src(request, resolver, model_id=self.model_id)
        if src.is_err:
            return Err(src.danger_err)
        outcome = _run_testbench(self._fixture, src.danger_ok, model_id=self.model_id)
        if outcome.is_err:
            return Err(outcome.danger_err)
        vectors, errors, note = outcome.danger_ok
        full_note = (
            f"{note} ({self._fixture.oracle_note}, {vectors} directed vector(s), "
            "seed=fixed/hand-authored -- DIRECTED coverage only, never formal)"
        )
        _log.debug("%s: %s", self.model_id, full_note)
        return Ok(Prediction(value=float(errors), eps=0.0, coverage=1.0))


# frob:doc docs/modules/py-harness.md#models-hdl
# frob:waive TEST001 reason="exercised transitively through HdlSimAssertGenericModel.estimate, test_hdl_sim_assert_generic_discharges_a_non_fixture_design; no isolated unit test calls it directly"
def build_generated_testbench(table: SignalTable) -> str:
    """WO-155 (D264) deliverable 4: generate a SystemVerilog testbench
    from a `signal_table`'s directed vectors, PASS/ASSERT-FAIL/SIM_OK
    discipline unchanged (the exact grammar `_run_generated_testbench`
    parses back with the SAME regexes as the hand-authored fixture
    testbenches, `_PASS_RE`/`_FAIL_RE`/`_SIM_OK_RE`/`_SIM_FAIL_RE`) --
    this is the source-generic replacement for a per-fixture hand-
    written testbench, D202's "one model, not one per fixture" pattern
    applied to `hdl.sim_assert`."""
    decl: list[str] = []
    conn: list[str] = []
    for p in table.ports:
        kind = "reg" if p.direction == "in" else "wire"
        width = f" [{p.width - 1}:0]" if p.width > 1 else ""
        decl.append(f"  {kind}{width} {p.name};")
        conn.append(f".{p.name}({p.name})")
    if table.clock is not None and not any(p.name == table.clock for p in table.ports):
        decl.append(f"  reg {table.clock} = 0;")
        conn.append(f".{table.clock}({table.clock})")
    if table.reset is not None and not any(p.name == table.reset for p in table.ports):
        decl.append(f"  reg {table.reset} = 0;")
        conn.append(f".{table.reset}({table.reset})")

    body: list[str] = []
    for vec in table.vectors:
        for a in vec.inputs:
            body.append(f"    {a.signal} = {a.value};")
        if table.clock is not None:
            body.append(f"    @(posedge {table.clock}); #1;")
        else:
            body.append("    #1;")
        for e in vec.expect:
            body.append("    vectors++;")
            body.append(
                f"    if ({e.signal} !== {e.expected}) begin\n"
                f'      errors++;\n      $display("ASSERT FAIL {vec.name} '
                f'cycle=%0d expected=%0d got=%0d", vectors, {e.expected}, '
                f"{e.signal});\n    end else begin\n"
                f'      $display("PASS {vec.name} cycle=%0d value=%0d", '
                f"vectors, {e.signal});\n    end"
            )

    clock_gen = f"  always #5 {table.clock} = ~{table.clock};\n" if table.clock else ""
    return (
        "`timescale 1ns/1ps\n"
        "module tb;\n" + "\n".join(decl) + "\n  int errors = 0;\n  int vectors = 0;\n\n"
        f"  {table.top_module} dut({', '.join(conn)});\n\n"
        f"{clock_gen}"
        "  initial begin\n"
        + "\n".join(body)
        + '\n    if (errors == 0) $display("SIM_OK vectors=%0d", vectors);\n'
        '    else $display("SIM_FAIL vectors=%0d errors=%0d", vectors, errors);\n'
        "    $finish;\n"
        "  end\n"
        "endmodule\n"
    )


def _run_generated_testbench(
    table: SignalTable, hdl_filename: str, src: bytes, *, model_id: str
) -> Result[tuple[int, int, str], HarnessError]:
    """The source-generic sibling of `_run_testbench`: build+run a
    testbench GENERATED from a `signal_table` (rather than reading a
    hand-authored fixture testbench file) -- same build/run/parse shape
    (NO DUPLICATION beyond what the differing testbench SOURCE forces)."""
    tb_src = build_generated_testbench(table)
    with tempfile.TemporaryDirectory(prefix="regolith_hdl_sim_gen_") as tmp:
        work = Path(tmp)
        (work / hdl_filename).write_bytes(src)
        tb_path = work / "tb.sv"
        tb_path.write_text(tb_src)
        args = VerilatorBinaryArgs(
            top_module="tb",
            tb_filename=tb_path.name,
            hdl_filename=hdl_filename,
        )
        build = run_verilator(args, cwd=work)
        if build.is_err:
            return Err(
                DomainError(
                    model_id=model_id, message=_tool_failure_message(build.danger_err)
                )
            )
        exe = work / "obj_dir" / "Vtb"
        spawned = run_argv(
            (str(exe),), cwd=work, timeout_s=_TESTBENCH_RUN_TIMEOUT_S, tool=exe.name
        )
        if spawned.is_err:
            fail = spawned.danger_err
            return Err(
                DomainError(
                    model_id=model_id,
                    message=f"simulation binary failed to run: {fail.stderr_excerpt}",
                )
            )
        proc = spawned.danger_ok
        lines = proc.stdout.decode("ascii", errors="replace").splitlines()
        first_fail = ""
        vectors = 0
        errors = 0
        for line in lines:
            m = _SIM_OK_RE.match(line)
            if m:
                vectors = int(m.group(1))
                continue
            m = _SIM_FAIL_RE.match(line)
            if m:
                vectors = int(m.group(1))
                errors = int(m.group(2))
                continue
            m = _FAIL_RE.match(line)
            if m and not first_fail:
                name, cycle, expected, got = m.groups()
                first_fail = (
                    f"assertion {name!r} failed at cycle {cycle}: "
                    f"expected={expected} got={got}"
                )
        if vectors == 0:
            return Err(
                DomainError(
                    model_id=model_id,
                    message=(
                        "generated simulation produced no SIM_OK/SIM_FAIL "
                        f"marker (stdout: {proc.stdout!r})"
                    ),
                )
            )
        note = first_fail or f"{vectors} directed vector(s), 0 failures"
        return Ok((vectors, errors, note))


# frob:doc docs/modules/py-harness.md#models-hdl
class HdlSimAssertGenericModel(Model):
    """WO-155 (D264): the SOURCE-GENERIC `hdl.sim_assert` model -- ONE
    instance, not one per fixture, mirroring `HdlBuildModel`'s D202
    posture. Discharges any request that carries BOTH the ordinary
    `hdl_src` payload AND the new `sim_stimulus` (`signal_table`)
    payload: the structural trigger this WO's Rust emission
    (`regolith_lower::claims::sim`) requires before it ever forms an
    obligation. A request with no stimulus payload never matches this
    model's signature (`payload_kinds` requires the `sim_stimulus`
    port), so the 5 fixture-bound `HdlSimAssertModel` registrations
    (WO-82) keep discharging their own fixtures completely unchanged --
    this is an ADDITIVE model, not a replacement of the fixture path
    (WO-82's per-fixture hand-authored testbenches are still real
    fixture coverage; this WO does not retire them).

    Cost is DELIBERATELY lower than the fixture-bound spine's (2 < 3):
    `ModelRegistry.select` breaks ties by ascending cost, and a real
    fleet request naming a stimulus could otherwise collide with a
    fixture model sharing the same bare regime tag (`sv2017`,
    `verilog2005`, ...) -- the lower cost guarantees THIS model wins
    whenever its payload requirement (a declared stimulus) is actually
    satisfied, never the wrong fixture's hand-authored testbench run
    against arbitrary bytes."""

    @property
    # frob:doc docs/modules/py-harness.md#models-hdl
    def version(self) -> str:
        return f"1+verilator{verilator_version()}"

    @property
    # frob:doc docs/modules/py-harness.md#models-hdl
    def cost(self) -> int:
        return 2

    @property
    # frob:doc docs/modules/py-harness.md#models-hdl
    def signature(self) -> ModelSignature:
        return ModelSignature(
            name="hdl_sim_assert_generic",
            claim_kind=CLAIM_SIM_ASSERT,
            sense=ClaimSense.upper_bound(),
            inputs=(),
            domain=("hdl", "sim_assert", "generic"),
            payload_kinds={SRC_PORT: SRC_KIND, STIMULUS_PORT: STIMULUS_KIND},
            required_regimes=(),
        )

    # frob:doc docs/modules/py-harness.md#models-hdl
    def estimate(
        self, request: DischargeRequest, *, resolver: PayloadResolver | None = None
    ) -> Result[Prediction, HarnessError]:
        regime = request.regimes[0] if request.regimes else None
        if regime in VHDL_REGIMES:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=(
                        f"VHDL ({regime}) has no verilator front-end -- "
                        "deferred, not simulated (WO-82 ledger, same cut "
                        "hdl.build's VHDL guard names)"
                    ),
                )
            )
        src = _resolve_src(request, resolver, model_id=self.model_id)
        if src.is_err:
            return Err(src.danger_err)
        stimulus_bytes = _resolve_payload(
            request, resolver, port=STIMULUS_PORT, model_id=self.model_id
        )
        if stimulus_bytes.is_err:
            return Err(stimulus_bytes.danger_err)
        parsed = check_signal_table_provenance(stimulus_bytes.danger_ok)
        if parsed.is_err:
            return Err(parsed.danger_err)
        table = parsed.danger_ok
        ref = request.payloads.get(SRC_PORT)
        filename = Path(ref.origin).name if ref is not None and ref.origin else "src.v"
        outcome = _run_generated_testbench(
            table, filename, src.danger_ok, model_id=self.model_id
        )
        if outcome.is_err:
            return Err(outcome.danger_err)
        vectors, errors, note = outcome.danger_ok
        _log.debug(
            "%s: %s (vectors=%d errors=%d, stimulus trust_tier=%s)",
            self.model_id,
            note,
            vectors,
            errors,
            table.trust_tier,
        )
        return Ok(Prediction(value=float(errors), eps=0.0, coverage=1.0))
