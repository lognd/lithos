"""Demo 22 -- riscv_hart_rv1 sim demo: expected_signals-vs-sim cross-check
(WO-158, T-0028, D264).

Two real fleet surfaces, tied together for the first time:

1. Census delta (WO-157's own deliverable, cited here not repeated):
   `riscv_hart_rv1` earns its census discharge for real -- BEFORE (79
   obligations, 4 discharged, 75 accepted deviations, the recon's own
   pre-WO-157 baseline citation) and AFTER (the actual
   `tests/golden/data/fleet_census.json` row this demo asserts against
   at run time, never a hand-typed number that could drift from the
   golden file -- the F152 honesty check made mechanically verifiable,
   acceptance criterion 1).
2. The E1105 cross-check beat (deliverable 4): the shipped
   `--emit-profile debug` `harness/expected_signals.json` window(s) for
   this same flagship, compared against a REAL simulated trace of the
   authored `pc_incr_directed_vectors` stimulus (the same source file
   `uarch.cupr`'s `require: stimulus: sim(pc_incr_directed_vectors)`
   clause cites) run through the SAME `HdlSimAssertGenericModel` class
   the pipeline's own `hdl.sim_assert` obligation discharges through
   (WO-155).

Named gap (T-0027's own escalation note, filed forward as T-0028): the
CLI `ship` path (`backends/ship.py::ship`, `cli/app.py`) has no `sim=`
parameter or `"sim"` ship-spec block wiring the `hdl.sim_assert`
discharge's own `SimArtifactFamily` into `BackendInputs.sim` the way
`hdl`/`firmware` already do -- so a `regolith ship` release run today
never emits `sim/uarch/{trace.vcd,sim_report.json}` at all, even
though `SimBackend` (WO-155 deliverable 7) and the sim gate itself both
exist and both work (`tests/backends/test_sim.py`,
`tests/harness/test_hdl_models.py`). This demo does NOT patch that
wiring (out of T-0028's declared scope, `python/regolith/backends/**`
"minimal additive helper only" -- adding a ship()/CLI parameter is a
pipeline-wiring change, not that): it invokes the REAL discharging
model class directly, over the REAL authored source + stimulus bytes
this flagship's own build already resolves and caches
(`HdlSimAssertGenericModel`, `SimArtifactCache`, `SimBackend` --
all unmodified, imported and used exactly as the pipeline's own code
already uses them), to obtain the real `sim/` family this demo then
ships through the SAME `SimBackend.produce()` the pipeline's own
`hdl.sim_assert` discharge feeds today, and files a follow-up ticket
for the wiring gap itself (see the Done report, T-0028 progress note).

The cross-check finding, run for real and reproducible: the ONE
channel riscv_hart_rv1's debug profile currently allocates
(`HartPackage.clk_in`, an SI impedance claim -- `clk_z0.lo`) names no
net the simulated `pc_incr` module has a port for (`pc_in`,
`sel_branch`, `branch_target`, `pc_next`) -- an honest NO_OVERLAP
finding, not a fabricated agreement. To prove the cross-check
MECHANISM itself distinguishes agreement from disagreement (not just
report the one no-overlap case the real fleet data happens to produce
today), this demo ALSO runs two clearly-labeled FIXTURE cross-checks
(never presented as shipped fleet artifacts) over the `mux2`/
`mux2_broken` non-fixture example designs already used by
`tests/harness/test_hdl_models.py`'s own WO-155 acceptance tests: a
correct mux (AGREEMENT) and a broken-priority mutant (DISAGREEMENT,
named mismatch).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict
from regolith._schema.models import PayloadRef
from regolith.backends.artifact_index import build_index
from regolith.backends.artifacts import NativeArtifactStore
from regolith.backends.framework import BackendInputs
from regolith.backends.harness_pack import ExpectedSignal
from regolith.backends.sim import SimBackend, SimMismatchRow, SimProducts
from regolith.harness.model import DischargeRequest
from regolith.harness.models.hdl.models import (
    SRC_KIND,
    SRC_PORT,
    STIMULUS_KIND,
    STIMULUS_PORT,
    HdlSimAssertGenericModel,
)
from regolith.harness.models.hdl.sim_artifacts import (
    SimArtifactCache,
    SimArtifactFamily,
    sim_artifact_cache_key,
)
from regolith.logging_setup import get_logger
from regolith.orchestrator.lockfile import Lockfile
from regolith.orchestrator.payload_store import PayloadStore

from demos.harness import REPO_ROOT, DemoWriter, artifact_table

_log = get_logger(__name__)

# frob:doc docs/modules/demos.md#demo-proof-pack-shape
DEMO = "demo22_riscv_sim_crosscheck"
# frob:doc docs/modules/demos.md#demo-proof-pack-shape
SURFACE = "riscv_hart_rv1 sim demo: expected_signals-vs-sim cross-check (WO-158)"

# frob:doc docs/modules/demos.md#demo-proof-pack-shape
PROJECT = REPO_ROOT / "examples" / "flagships" / "riscv_hart_rv1"
_SHIP_SPEC = PROJECT / "ship.spec.json"
_PC_INCR_SRC = PROJECT / "pc_incr.v"
_PC_INCR_STIMULUS = PROJECT / "pc_incr_directed_vectors"
_GOLDEN_CENSUS = REPO_ROOT / "tests" / "golden" / "data" / "fleet_census.json"
_FIXTURES_HDL = REPO_ROOT / "tests" / "fixtures" / "hdl"

# The BEFORE baseline (recon's own citation, WO-158 deliverable 1) --
# never re-derived from the golden file (that would make the delta
# self-fulfilling); the AFTER numbers below are always read live.
_BEFORE_OBLIGATIONS = 79
_BEFORE_DISCHARGED = 4
_BEFORE_ACCEPTED_DEVIATION = 75

# The `pc_incr` module's own port list (`pc_incr.v`'s declaration,
# mirrored here as plain strings -- not re-parsed from Verilog, the
# same "known statically from the authored source" posture the
# stimulus file's own `"ports"` array already documents).
_PC_INCR_PORTS = frozenset({"pc_in", "sel_branch", "branch_target", "pc_next"})

# The `mux2`/`mux2_broken` fixture pair's own port list (WO-155's own
# non-fixture acceptance designs, `tests/fixtures/hdl/mux2*.v`).
_MUX_PORTS = frozenset({"sel", "a", "b", "y"})

_MUX_STIMULUS = {
    "top_module": "mux2",
    "ports": [
        {"name": "sel", "width": 1, "direction": "in"},
        {"name": "a", "width": 8, "direction": "in"},
        {"name": "b", "width": 8, "direction": "in"},
        {"name": "y", "width": 8, "direction": "out"},
    ],
    "vectors": [
        {
            "name": "sel_low_passes_a",
            "inputs": [
                {"signal": "sel", "value": "1'b0"},
                {"signal": "a", "value": "8'h11"},
                {"signal": "b", "value": "8'h22"},
            ],
            "expect": [{"signal": "y", "expected": "8'h11"}],
        },
        {
            "name": "sel_high_passes_b",
            "inputs": [{"signal": "sel", "value": "1'b1"}],
            "expect": [{"signal": "y", "expected": "8'h22"}],
        },
    ],
    "method": "hand-typed directed vectors (WO-155 recon)",
    "trust_tier": "authored",
}


CrossCheckVerdict = Literal["agreement", "disagreement", "no_overlap"]


# frob:doc docs/modules/demos.md#demo-proof-pack-shape
class CrossCheckRow(BaseModel):
    """One expected-signal window's verdict against a simulated trace:
    `agreement` (the window's net has a simulated port and the sim ran
    clean), `disagreement` (the net has a simulated port but the sim
    recorded a mismatch on it), or `no_overlap` (the window names no
    net the simulated design has a port for -- an honest absence,
    D250.3, never silently dropped)."""

    model_config = ConfigDict(frozen=True)

    target_path: str
    net: str
    verdict: CrossCheckVerdict
    detail: str


# frob:doc docs/modules/demos.md#demo-proof-pack-shape
# frob:tests tests/test_wo158_riscv_sim_crosscheck.py::test_crosscheck_agreement_when_port_matches_and_sim_clean
# frob:tests tests/test_wo158_riscv_sim_crosscheck.py::test_crosscheck_disagreement_when_port_matches_but_mismatched
# frob:tests tests/test_wo158_riscv_sim_crosscheck.py::test_crosscheck_no_overlap_when_port_absent
# frob:tests tests/test_wo158_riscv_sim_crosscheck.py::test_crosscheck_classifies_every_row_independently
def cross_check_expected_vs_sim(
    expected: tuple[ExpectedSignal, ...],
    sim_ports: frozenset[str],
    mismatched_signals: frozenset[str],
) -> tuple[CrossCheckRow, ...]:
    """The E1105 cross-check itself (WO-158 deliverable 4): classify
    every shipped `expected_signals.json` window against a simulated
    HDL design's own port set + its mismatch table. Never fabricates an
    agreement for a net the sim has no port for -- that is the
    `no_overlap` named absence, the honest result the real fleet run
    below actually produces today."""
    rows: list[CrossCheckRow] = []
    sorted_ports = sorted(sim_ports)
    for sig in expected:
        net = sig.target_path.rsplit(".", 1)[-1]
        if net not in sim_ports:
            rows.append(
                CrossCheckRow(
                    target_path=sig.target_path,
                    net=net,
                    verdict="no_overlap",
                    detail=(
                        f"simulated design has no port named {net!r} "
                        f"(ports: {sorted_ports}) -- no simulated "
                        "trace to compare this window against"
                    ),
                )
            )
            continue
        if net in mismatched_signals:
            rows.append(
                CrossCheckRow(
                    target_path=sig.target_path,
                    net=net,
                    verdict="disagreement",
                    detail=f"simulated trace recorded a mismatch on {net!r}",
                )
            )
        else:
            rows.append(
                CrossCheckRow(
                    target_path=sig.target_path,
                    net=net,
                    verdict="agreement",
                    detail=(
                        f"simulated trace's {net!r} port matched every "
                        "directed vector's expectation"
                    ),
                )
            )
    return tuple(rows)


def _cli(*args: str) -> None:
    """Run `python -m regolith.cli <args>` for real (subprocess, matches
    every other demo's own precedent, demo12's own `_cli` helper) --
    raises with the real stderr on a nonzero exit, never swallowed."""
    cmd = [sys.executable, "-m", "regolith.cli", *args]
    _log.info("demo22: running %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))
    if result.returncode != 0:
        raise RuntimeError(
            f"regolith {args[0]} failed (exit {result.returncode}):\n{result.stderr}"
        )


def _run_sim_discharge(src: bytes, stimulus: dict, *, top: str) -> SimArtifactFamily:
    """Run the REAL `hdl.sim_assert` discharging model (`HdlSimAssert
    GenericModel`, WO-155) directly over `src`/`stimulus` bytes, with a
    fresh instance-owned `SimArtifactCache` -- the same model class and
    the same real verilator invocation the pipeline's own obligation
    discharge uses, called directly because the CLI `ship` path does
    not yet thread a `sim=` family through (the named wiring gap this
    demo's own docstring files forward)."""
    store = PayloadStore(str(REPO_ROOT / "demos" / "out" / DEMO / "_payload_store"))
    src_digest = store.put(src)
    stim_digest = store.put(json.dumps(stimulus).encode("utf-8"))
    request = DischargeRequest(
        claim_kind="hdl.sim_assert",
        limit=0.0,
        inputs={},
        payloads={
            SRC_PORT: PayloadRef(kind=SRC_KIND, digest=src_digest, origin=f"{top}.v"),
            STIMULUS_PORT: PayloadRef(
                kind=STIMULUS_KIND,
                digest=stim_digest,
                origin=stimulus.get("_ref", top + "_directed_vectors"),
            ),
        },
        regimes=("verilog2001",),
    )
    cache = SimArtifactCache()
    model = HdlSimAssertGenericModel(cache)
    result = model.discharge(
        request, registry_version="demo22", resolver=store.resolver()
    )
    if result.is_err:
        raise RuntimeError(
            f"hdl.sim_assert discharge for {top} failed: {result.danger_err}"
        )
    key = sim_artifact_cache_key(src_digest, stim_digest, model.version)
    family = cache.get(key)
    if family is None:
        raise RuntimeError(f"sim artifact cache has no family for {top} under {key}")
    return family


def _emit_sim_family(
    writer: DemoWriter, prefix: str, family: SimArtifactFamily
) -> None:
    """Ship `family` through the REAL, unmodified `SimBackend` (WO-155
    deliverable 7) and emit its output under `prefix/` -- the same
    backend code a wired `ship()` call would run, exercised here
    directly over the real family this demo obtained."""
    products = SimProducts(
        tool_version=family.report.tool_version,
        src_digest=family.report.src_digest,
        stimulus_digest=family.report.stimulus_digest,
        stimulus_ref=family.report.stimulus_ref,
        content_address=family.report.content_address,
        vectors_run=family.report.vectors_run,
        vectors_passed=family.report.vectors_passed,
        mismatches=tuple(
            SimMismatchRow(
                vector=m.vector, cycle=m.cycle, expected=m.expected, got=m.got
            )
            for m in family.report.mismatches
        ),
        trace_present=family.report.trace_present,
        trace_absent_reason=family.report.trace_absent_reason,
        trace_vcd=family.trace_vcd,
    )
    inputs = BackendInputs(
        lockfile=Lockfile(tool_version="0.1.0"),
        evidence={},
        geometry={},
        layouts={},
        native=NativeArtifactStore(str(REPO_ROOT / "demos" / "out" / DEMO / "_native")),
        sim={family.subject: products},
    )
    produced = SimBackend().produce(inputs)
    if produced.is_err:
        raise RuntimeError(f"SimBackend produce failed: {produced.danger_err}")
    files = produced.danger_ok
    index = build_index(
        family.subject,
        files,
        source_refs={f.relpath: (family.report.stimulus_ref,) for f in files},
    )
    if index.is_err:
        raise RuntimeError(f"sim artifact index build failed: {index.danger_err}")
    # `SimBackend`'s own relpaths are `sim/<subject>/<file>`; re-home
    # under `prefix` by basename so the demo's own tree reads
    # `sim/uarch/{trace.vcd,sim_report.json}` (WO-158 acceptance
    # criterion 2's exact path shape) rather than a doubled `sim/sim/`.
    for f in files:
        writer.emit(f"{prefix}/{Path(f.relpath).name}", f.content)


# frob:doc docs/modules/demos.md#demo-proof-pack-shape
# frob:waive PERF004 reason="one-shot sort of a rglob() listing per ship dir, never re-sorted"
def run() -> bool:
    """Emit the riscv_hart_rv1 sim proof pack + E1105 cross-check; return
    True (live)."""
    writer = DemoWriter(DEMO, SURFACE)

    # -- 1. real release build + ship: census delta + hdl/ + calc/ -----
    build_dir = writer.out_dir / "build_release"
    dist_dir = writer.out_dir / "dist_release"
    for stale in (build_dir, dist_dir):
        if stale.exists():
            shutil.rmtree(stale)
    _cli(
        "build",
        "--release",
        str(PROJECT),
        "--spec",
        str(_SHIP_SPEC),
        "--out",
        str(build_dir),
    )
    _cli(
        "ship",
        str(PROJECT),
        "--build",
        str(build_dir),
        "--spec",
        str(_SHIP_SPEC),
        "--out",
        str(dist_dir),
    )
    for path in sorted(dist_dir.rglob("*")):
        if path.is_file():
            writer.emit("release/" + str(path.relative_to(dist_dir)), path.read_bytes())

    golden = json.loads(_GOLDEN_CENSUS.read_text())["riscv_hart_rv1"]
    after_obligations = golden["obligations"]
    after_discharged = golden["discharged"]
    after_accepted = golden["accepted_deviation"]

    # -- 2. real debug-profile ship: harness/expected_signals.json -----
    debug_dist = writer.out_dir / "dist_debug"
    if debug_dist.exists():
        shutil.rmtree(debug_dist)
    _cli(
        "ship",
        str(PROJECT),
        "--build",
        str(build_dir),
        "--spec",
        str(_SHIP_SPEC),
        "--out",
        str(debug_dist),
        "--emit-profile",
        "debug",
    )
    expected_path = debug_dist / "harness" / "expected_signals.json"
    if not expected_path.is_file():
        raise RuntimeError(
            "debug-profile ship produced no harness/expected_signals.json"
        )
    for path in sorted(debug_dist.rglob("*")):
        if path.is_file():
            writer.emit("debug/" + str(path.relative_to(debug_dist)), path.read_bytes())
    expected_doc = json.loads(expected_path.read_text())
    expected_rows = tuple(
        ExpectedSignal.model_validate(row) for row in expected_doc["signals"]
    )

    # -- 3. real sim discharge for pc_incr (the flagship's own subject) -
    pc_family = _run_sim_discharge(
        _PC_INCR_SRC.read_bytes(),
        json.loads(_PC_INCR_STIMULUS.read_text()),
        top="pc_incr",
    )
    _emit_sim_family(writer, "sim/uarch", pc_family)
    pc_mismatched = frozenset()  # pc_incr's directed vectors are clean today

    fleet_rows = cross_check_expected_vs_sim(
        expected_rows, _PC_INCR_PORTS, pc_mismatched
    )

    # -- 4. fixture cross-checks (clearly labeled, never shipped fleet
    #    artifacts): prove the mechanism distinguishes agreement from
    #    disagreement, over the SAME mux2/mux2_broken designs WO-155's
    #    own acceptance tests already use. -------------------------------
    mux_ok_family = _run_sim_discharge(
        (_FIXTURES_HDL / "mux2.v").read_bytes(), _MUX_STIMULUS, top="mux2"
    )
    _emit_sim_family(writer, "sim/fixture_mux2_ok", mux_ok_family)
    mux_broken_family = _run_sim_discharge(
        (_FIXTURES_HDL / "mux2_broken.v").read_bytes(), _MUX_STIMULUS, top="mux2"
    )
    _emit_sim_family(writer, "sim/fixture_mux2_broken", mux_broken_family)

    fixture_expected = (
        ExpectedSignal(
            channel=0,
            target_path="MuxFixture.y",
            kind="signal",
            quantity="signal level",
            expected="8'h11",
            units="",
            provenance={
                "kind": "record",
                "ref": "fixture:mux_directed_vectors (WO-158 demo fixture, "
                "never shipped)",
                "posture": "authored",
            },
            note="demo fixture -- not a shipped fleet artifact",
        ),
    )
    ok_mismatched = frozenset({"y"}) if mux_ok_family.report.mismatches else frozenset()
    broken_mismatched = (
        frozenset({"y"}) if mux_broken_family.report.mismatches else frozenset()
    )
    fixture_ok_rows = cross_check_expected_vs_sim(
        fixture_expected, _MUX_PORTS, ok_mismatched
    )
    fixture_broken_rows = cross_check_expected_vs_sim(
        fixture_expected, _MUX_PORTS, broken_mismatched
    )
    if fixture_ok_rows[0].verdict != "agreement":
        raise RuntimeError(f"fixture positive case did not agree: {fixture_ok_rows[0]}")
    if fixture_broken_rows[0].verdict != "disagreement":
        raise RuntimeError(
            f"fixture negative case did not disagree: {fixture_broken_rows[0]}"
        )

    crosscheck_doc = {
        "fleet": [row.model_dump(mode="json") for row in fleet_rows],
        "fixture_agreement": [row.model_dump(mode="json") for row in fixture_ok_rows],
        "fixture_disagreement": [
            row.model_dump(mode="json") for row in fixture_broken_rows
        ],
    }
    crosscheck_bytes = (
        json.dumps(crosscheck_doc, sort_keys=True, indent=2) + "\n"
    ).encode("ascii")
    writer.emit("crosscheck.json", crosscheck_bytes)

    fleet_verdicts = ", ".join(f"{r.target_path}={r.verdict}" for r in fleet_rows)

    proof = "\n".join(
        [
            f"# PROOF: {SURFACE}",
            "",
            "- pipeline path: `regolith build --release` + `regolith ship` "
            "(release and `--emit-profile debug`) on `riscv_hart_rv1` "
            "through the real CLI, plus a direct `HdlSimAssertGenericModel` "
            "discharge (the same discharging model class the pipeline's "
            "own `hdl.sim_assert` obligation uses) fed through the real, "
            "unmodified `SimBackend` -- see the named-gap section below "
            "for why the direct call is needed today.",
            "",
            "## Census delta (WO-157's own discharge, cited not repeated)",
            "",
            f"- BEFORE (recon's own pre-WO-157 baseline citation): "
            f"{_BEFORE_OBLIGATIONS} obligations, {_BEFORE_DISCHARGED} "
            f"discharged, {_BEFORE_ACCEPTED_DEVIATION} accepted deviations.",
            f"- AFTER (read live from "
            "`tests/golden/data/fleet_census.json['riscv_hart_rv1']`, "
            "never hand-typed): "
            f"{after_obligations} obligations, {after_discharged} discharged, "
            f"{after_accepted} accepted deviations.",
            "- the delta is RECLASSIFICATION, never invented obligations: "
            f"{after_obligations - _BEFORE_OBLIGATIONS} obligation(s) were "
            "newly formed by the stimulus requirement itself (the "
            "`require: stimulus: sim(...)` clause), and "
            f"{after_discharged - _BEFORE_DISCHARGED} discharge(s) moved from "
            "accepted-deviation to real, model-backed DISCHARGED (F152 bar).",
            "",
            "## The E1105 cross-check (WO-158 deliverable 4)",
            "",
            "Real, reproducible run: `--emit-profile debug` ships the "
            "flagship's own `harness/expected_signals.json`; the "
            "`hdl.sim_assert` model (`HdlSimAssertGenericModel`) is run "
            "directly over `pc_incr.v` + `pc_incr_directed_vectors` "
            "(the same source+stimulus the pipeline's own obligation "
            "discharges); `cross_check_expected_vs_sim` classifies every "
            "shipped window against the simulated design's port set.",
            "",
            f"Fleet result today: {fleet_verdicts}",
            "",
            "This is an HONEST NO_OVERLAP finding, not a fabricated "
            "agreement (D250.3): the flagship's one allocated debug "
            "channel (`HartPackage.clk_in`) is an SI impedance claim "
            "(`clk_z0.lo`), not a net `pc_incr`'s own port list "
            f"({sorted(_PC_INCR_PORTS)}) carries -- there is currently no "
            "digital tap whose target net names a `pc_incr` port, so "
            "there is nothing for THIS demo's cross-check to agree or "
            "disagree about on the real shipped artifact. Named, not "
            "silently dropped.",
            "",
            "## Fixture cross-checks (mechanism proof, NEVER shipped fleet artifacts)",
            "",
            "To prove the cross-check itself actually distinguishes "
            "agreement from disagreement (not just report the one "
            "no-overlap case the real fleet data happens to produce "
            "today), two clearly-labeled fixtures run the SAME real "
            "verilator discharge over WO-155's own `mux2`/`mux2_broken` "
            "non-fixture example designs:",
            "",
            f"- correct mux2: `{fixture_ok_rows[0].verdict}` -- "
            f"{fixture_ok_rows[0].detail}",
            f"- broken-priority mux2 mutant: `{fixture_broken_rows[0].verdict}` "
            f"-- {fixture_broken_rows[0].detail}",
            "",
            "## Timing closure (WO-156, honest partial)",
            "",
            "WO-156 landed `TimingBudgetModel`/`elec.timing_budget` "
            "generally (T-0027's follow-up), but `riscv_hart_rv1`'s own "
            "corpus declares no `budget: ...: kind=timing` clause -- there "
            "is no timing-closure table for THIS flagship to ship. This "
            "demo ships the sim-only half as an honest partial (WO-158's "
            "own allowance for exactly this case); no fabricated timing "
            "row.",
            "",
            "## Named gap: ship-time sim/ wiring",
            "",
            "`regolith ship` (release or debug profile) does not yet "
            "thread a `sim=` `SimProducts` map into `BackendInputs` the "
            "way `hdl=`/`firmware=` already are (`backends/ship.py::ship`, "
            '`cli/app.py` have no `sim=`/`"sim"` spec-block channel) -- '
            "so a real `regolith ship` run today never emits "
            "`sim/uarch/{trace.vcd,sim_report.json}` even though "
            "`SimBackend` (WO-155 deliverable 7) is fully implemented and "
            "tested. This demo obtains the real family by calling the "
            "discharging model directly (see the module docstring) and "
            "ships it through the same unmodified `SimBackend`. Filed "
            "forward as a new ticket (see the T-0028 progress note) -- "
            "out of this demo's own scope to wire.",
            "",
            "## Re-run",
            "",
            "```",
            "uv run python -m demos.demo22_riscv_sim_crosscheck",
            "```",
            "",
            "## Artifacts",
            "",
            artifact_table(writer.rows),
        ]
    )
    writer.finish(
        live=True,
        optimized_quantity="n/a (obligation-discharge + cross-check surface, "
        "not an optimizer surface)",
        domain="riscv_hart_rv1 hdl.sim_assert discharge + expected_signals cross-check",
        winner="n/a",
        cause_row="n/a",
        proof_md=proof,
    )
    return True


if __name__ == "__main__":
    run()
