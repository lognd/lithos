"""The std.hdl `Model` pack (WO-82 deliverables 1-3; AD-19/AD-35).

Three ordinary `regolith.harness.model.Model`s, one per check-mode claim
kind (`hdl.build`/`hdl.sim_assert`/`hdl.equiv_directed`), registered per
`examples/hdl/` fixture (the cuprite/09 D120 calibration corpus: counter,
alu_generic, fsm_traffic, fifo_cdc, assertions_map) mirroring
`std.cam`'s per-dialect registration shape (`harness/models/cam/models.py`).
All share the ONE discharge/margin path (`Model.discharge`): value=excess
(count of failures), eps=0.0, limit=0.0 (upper-bound sense -- "zero
verilator/testbench failures"); a tool failure or an unsupported regime
(VHDL: no front-end in this environment) short-circuits to
`Err(DomainError)` so the registry renders indeterminate evidence, never
a false pass (conservative-or-silent, charter D3 precedent).

Payload port: `hdl_src` (kind `hdl_source`) carries the hash-pinned raw
HDL bytes (D96 payload channel, matching std.cam's `plan` port shape).
The dialect/regime is a REQUIRED regime tag (matches the `.cupr`
fixture's own `by extern(ref, <regime>)` tag), so a request whose regime
does not match a model's fixture is a non-match, never an assumption
(same pattern as std.cam's dialect regime tag).
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
from regolith.harness.models.hdl.verilator_adapter import (
    ToolFailure,
    run_verilator,
    verilator_version,
)
from regolith.harness.signature import ClaimSense, ModelSignature
from regolith.logging_setup import get_logger

if TYPE_CHECKING:
    from regolith.orchestrator.payload_store import PayloadResolver

_log = get_logger(__name__)

SRC_PORT = "hdl_src"
SRC_KIND = "hdl_source"

CLAIM_BUILD = "hdl.build"
CLAIM_SIM_ASSERT = "hdl.sim_assert"
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


def _resolve_src(
    request: DischargeRequest,
    resolver: PayloadResolver | None,
    *,
    model_id: str,
) -> Result[bytes, HarnessError]:
    ref = request.payloads.get(SRC_PORT)
    if ref is None:  # pragma: no cover -- signature match guarantees it
        return Err(DomainError(model_id=model_id, message="no hdl_src payload"))
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


class _HdlModel(Model):
    """Shared spine: one model instance per fixture (mirrors std.cam's
    one-instance-per-dialect shape)."""

    _fixture: FixtureSpec
    _claim_kind: str

    def __init__(self, fixture: FixtureSpec) -> None:
        self._fixture = fixture

    @property
    def version(self) -> str:
        """Model version folds the verilator version (AD-19 cache-key
        law: an upgraded tool invalidates exactly its own cached
        evidence -- resolved once per process, see verilator_adapter)."""
        return f"1+verilator{verilator_version()}"

    @property
    def cost(self) -> int:
        """`hdl.build` is cheapest (lint-only); simulation costs more."""
        return 1 if self._claim_kind == CLAIM_BUILD else 3

    @property
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

    def estimate(
        self, request: DischargeRequest, *, resolver: PayloadResolver | None = None
    ) -> Result[Prediction, HarnessError]:
        raise NotImplementedError

    def _vhdl_guard(self) -> Result[Prediction, HarnessError] | None:
        """VHDL fixtures defer EVERY hdl.* claim (named reason: no
        verilator VHDL front-end, no `ghdl` in this environment --
        checked, not assumed, per the dispatch prompt's instruction)."""
        if self._fixture.regime in VHDL_REGIMES:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=(
                        f"{self._fixture.fixture_id}: VHDL ({self._fixture.regime}) "
                        "has no verilator front-end and no `ghdl` was found on "
                        "PATH in this environment -- deferred, not simulated "
                        "(WO-82 ledger)"
                    ),
                )
            )
        return None


class HdlBuildModel(_HdlModel):
    """`hdl.build`: the fixture's HDL verilates (lint-elaborates)
    cleanly. Generic over every non-VHDL fixture (deliverable 1)."""

    _claim_kind = CLAIM_BUILD

    def estimate(
        self, request: DischargeRequest, *, resolver: PayloadResolver | None = None
    ) -> Result[Prediction, HarnessError]:
        guard = self._vhdl_guard()
        if guard is not None:
            return guard
        src = _resolve_src(request, resolver, model_id=self.model_id)
        if src.is_err:
            return Err(src.danger_err)
        with tempfile.TemporaryDirectory(prefix="regolith_hdl_build_") as tmp:
            work = Path(tmp)
            hdl_path = work / self._fixture.hdl_filename
            hdl_path.write_bytes(src.danger_ok)
            # `-Wno-DECLFILENAME`: these fixtures deliberately hold
            # multiple modules/interfaces per file (hierarchy rows,
            # cuprite/09 sec. 1) -- verilator's filename-matches-first-
            # module convention is a style lint unrelated to build
            # correctness, so it does not gate `hdl.build`'s verdict.
            argv = ["--lint-only", "-Wall", "-Wno-DECLFILENAME", "--timing"]
            if self._fixture.is_sv:
                argv.append("-sv")
            argv += ["--top-module", self._fixture.top_module, hdl_path.name]
            result = run_verilator(argv, cwd=work)
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
        argv = [
            "--binary",
            "-Wno-fatal",
            "--timing",
            "-O2",
            "--top-module",
            fixture.testbench_top,
            "--Mdir",
            "obj_dir",
            tb_path.name,
            fixture.hdl_filename,
        ]
        build = run_verilator(argv, cwd=work)
        if build.is_err:
            return Err(
                DomainError(
                    model_id=model_id, message=_tool_failure_message(build.danger_err)
                )
            )
        exe = work / "obj_dir" / f"V{fixture.testbench_top}"
        import subprocess

        try:
            proc = subprocess.run(
                [str(exe)], capture_output=True, text=True, timeout=60, check=False
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return Err(
                DomainError(
                    model_id=model_id, message=f"simulation binary failed to run: {exc}"
                )
            )
        lines = (proc.stdout or "").splitlines()
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


class HdlSimAssertModel(_HdlModel):
    """`hdl.sim_assert`: directed fixture vectors + assertions through
    the verilated DUT (deliverable 2). Registered only for fixtures with
    a landed testbench (`SIMULATED_FIXTURE_IDS`, WO-82 scope cut)."""

    _claim_kind = CLAIM_SIM_ASSERT

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
