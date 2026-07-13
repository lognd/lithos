"""Demo 12 -- the computer track ships: firmware tree + HDL evidence.

WO-115 deliverable 6 (charter 38 sec. 1.9). Two real fleet surfaces:

HDL (riscv_hart_rv1): `build --release` discharges the flagship's own
`hdl.build` obligation through the std.hdl verilator pack against its
`pc_incr.v` source (verilator 5.047 via toolenv), and `ship` emits the
`hdl/` family: the source manifest, the source itself, and
`tier_report.json` carrying the DISCHARGED build tier plus the honest
named absences (no `hdl.sim_assert`/`hdl.equiv_directed` evidence on
this subject; netlist absent because no synthesis-to-netlist model
exists in std.hdl -- WO-82/D202's own words, shipped verbatim).

Firmware (espresso_machine): `control_board.cupr` declares
`u_mcu = vendor(stm32g071cb)` running `BrewCtl` (`bind BrewCtl:
cpu0 = pcb.u_mcu`), and `examples/registry/stm32g0.cupr` carries the
family's REAL per-pin alternate-function table (pa2/pa3/pb6/pb7). The
demo drives the real chain end to end:

    registry AF table (mirrored verbatim below, cited)
    -> `assign_pinmux` (the REAL WO-35 deterministic solver) for the
       uart2 debug-console demand pair
    -> `FirmwareDesign` (family stm32g0 -- the design's own vendor
       part family; no invented clocks/events: the design declares
       none in `on`-block/clock form)
    -> `realize_firmware` (the REAL WO-37 codegen: contract header,
       family-pack BSP, linker script, build fragment; byte-identical
       across runs)
    -> `regolith ship --spec` with the `"firmware"` block (the WO-102
       CLI channel) -> the shipped `firmware/` family whose
       `build_report.json` names the honest ELF absence (no toolchain
       invocation pinned an image -- never a fabricated binary).

WO115-F2 (named gap): no lowering pass derives `FirmwareDesign` from
`computer`/`bind` declarations yet (the WO-37 realizer's input is
caller-supplied by design, v1), and the cubesat OBC's stm32l496 family
has no registered family pack (only the stm32g0 reference pack exists)
-- so fleet packages ship firmware only through this caller channel.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys

from regolith.backends.firmware import NO_ELF_REASON, FirmwareArtifact
from regolith.logging_setup import get_logger
from regolith.realizer.elec.pinmux import (
    AlternateFunctionTable,
    FlowDemand,
    FunctionInstance,
    PinOption,
    assign_pinmux,
)
from regolith.realizer.firmware.contract import FirmwareDesign
from regolith.realizer.firmware.realize import realize_firmware

from demos.harness import REPO_ROOT, DemoWriter, artifact_table

_log = get_logger(__name__)

DEMO = "demo12_firmware_hdl"
SURFACE = "shipped firmware tree + HDL tier evidence (computer track)"

HDL_PROJECT = REPO_ROOT / "examples" / "flagships" / "riscv_hart_rv1"
FW_PROJECT = REPO_ROOT / "examples" / "flagships" / "espresso_machine"

# examples/registry/stm32g0.cupr's own pin table, mirrored verbatim
# (pins legitimately live in the registry record -- its own NOTE):
#   pa2: {uart2.tx, tim15.ch1, adc.in2}
#   pa3: {uart2.rx, tim15.ch2, adc.in3}
#   pb6: {twi1.scl, uart1.tx, tim16.ch1}
#   pb7: {twi1.sda, uart1.rx}
_STM32G0_PIN_TABLE = {
    "pa2": ("uart2.tx", "tim15.ch1", "adc.in2"),
    "pa3": ("uart2.rx", "tim15.ch2", "adc.in3"),
    "pb6": ("twi1.scl", "uart1.tx", "tim16.ch1"),
    "pb7": ("twi1.sda", "uart1.rx"),
}


def _cli(*args: str) -> None:
    cmd = [sys.executable, "-m", "regolith.cli", *args]
    _log.info("demo12: running %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))
    if result.returncode != 0:
        raise RuntimeError(
            f"regolith {args[0]} failed (exit {result.returncode}):\n{result.stderr}"
        )


def _build_and_ship(writer: DemoWriter, tag: str, project, spec_path) -> None:
    build_dir = writer.out_dir / f"build_{tag}"
    dist_dir = writer.out_dir / f"dist_{tag}"
    for stale in (build_dir, dist_dir):
        if stale.exists():
            shutil.rmtree(stale)
    _cli(
        "build",
        "--release",
        str(project),
        "--spec",
        str(spec_path),
        "--out",
        str(build_dir),
    )
    _cli(
        "ship",
        str(project),
        "--build",
        str(build_dir),
        "--spec",
        str(spec_path),
        "--out",
        str(dist_dir),
    )


def _af_table() -> AlternateFunctionTable:
    """The registry record's table in WO-35 shape. The record's own
    NOTE says the G0's functions are ATOMIC (uart2.tx is one assignable
    thing), so each instance's kind is its own id."""
    instances: dict[str, FunctionInstance] = {}
    pins: list[PinOption] = []
    for pin, funcs in sorted(_STM32G0_PIN_TABLE.items()):
        for func in funcs:
            instances.setdefault(func, FunctionInstance(id=func, kind=func))
        pins.append(PinOption(pin=pin, functions=funcs))
    return AlternateFunctionTable(
        package="stm32g071cb",
        pins=tuple(pins),
        instances=tuple(instances.values()),
    )


def _firmware_artifact() -> tuple[FirmwareArtifact, tuple[str, ...]]:
    """The real pinmux -> codegen chain; returns (artifact, pin summary)."""
    demands = (
        FlowDemand(flow="u_mcu.uart2.tx", kind="uart2.tx"),
        FlowDemand(flow="u_mcu.uart2.rx", kind="uart2.rx"),
    )
    solved = assign_pinmux(demands, _af_table())
    if solved.is_err:
        raise RuntimeError(f"pinmux solve failed: {solved.danger_err}")
    pinmux = solved.danger_ok
    design = FirmwareDesign(
        name="brewctl",
        family="stm32g0",
        pinmux=pinmux,
        events=(),
        clocks=(),
        partitions=(),
    )
    tree = realize_firmware(design)
    if tree.is_err:
        raise RuntimeError(f"realize_firmware failed: {tree.danger_err}")
    summary = tuple(
        f"{a.flow} -> {a.pin} ({a.cause})" for a in pinmux.assignments
    )
    return FirmwareArtifact(tree=tree.danger_ok, toolchain=None), summary


def run() -> bool:
    """Emit the firmware+HDL proof pack; return True (live)."""
    writer = DemoWriter(DEMO, SURFACE)

    # -- HDL: riscv_hart_rv1's own discharged verilator tier -----------
    _build_and_ship(
        writer, "riscv", HDL_PROJECT, HDL_PROJECT / "ship.spec.json"
    )
    hdl_dir = writer.out_dir / "dist_riscv" / "hdl"
    hdl_count = 0
    for path in sorted(hdl_dir.rglob("*")):
        if path.is_file():
            writer.emit(
                "riscv/hdl/" + str(path.relative_to(hdl_dir)), path.read_bytes()
            )
            hdl_count += 1
    if hdl_count == 0:
        raise RuntimeError("riscv_hart_rv1 shipped no hdl/ family")
    tier_report = json.loads(
        next(hdl_dir.rglob("tier_report.json")).read_text()
    )
    build_tier = next(
        t for t in tier_report["tiers"] if t["claim"] == "hdl.build"
    )
    if build_tier["status"] != "discharged" or build_tier["tool"] != "verilator":
        raise RuntimeError(f"hdl.build tier not a verilator discharge: {build_tier}")
    if tier_report["netlist"]["present"]:
        raise RuntimeError("netlist claimed present; expected the named absence")

    # -- Firmware: espresso's stm32g071cb through pinmux + codegen ------
    artifact, pin_summary = _firmware_artifact()
    spec_data = json.loads((FW_PROJECT / "ship.spec.json").read_text())
    spec_data["firmware"] = {"brewctl": json.loads(artifact.model_dump_json())}
    spec_path = writer.out_dir / "ship.spec.demo12.json"
    spec_path.write_text(json.dumps(spec_data, indent=2, sort_keys=True) + "\n")
    writer.emit("ship.spec.demo12.json", spec_path.read_bytes())
    _build_and_ship(writer, "espresso", FW_PROJECT, spec_path)
    fw_dir = writer.out_dir / "dist_espresso" / "firmware"
    fw_count = 0
    for path in sorted(fw_dir.rglob("*")):
        if path.is_file():
            writer.emit(
                "espresso/firmware/" + str(path.relative_to(fw_dir)),
                path.read_bytes(),
            )
            fw_count += 1
    if fw_count == 0:
        raise RuntimeError("espresso_machine shipped no firmware/ family")
    fw_report = json.loads(next(fw_dir.rglob("build_report.json")).read_text())
    elf = fw_report["elf"]
    if elf["present"] or NO_ELF_REASON not in elf["reason"]:
        raise RuntimeError(f"expected the honest no-ELF surface, got: {elf}")

    proof = "\n".join(
        [
            f"# PROOF: {SURFACE}",
            "",
            "## HDL (riscv_hart_rv1)",
            "",
            "- `build --release` discharges the flagship's `hdl.build` "
            "obligation through the std.hdl verilator pack over its own "
            f"`pc_incr.v`; the shipped tier row: model "
            f"`{build_tier['model_id']}`, tool verilator "
            f"{build_tier['tool_version']}, status DISCHARGED.",
            "- named absences, shipped verbatim in `tier_report.json`: "
            "no sim_assert/equiv_directed evidence on this subject, and "
            "netlist absent because no synthesis-to-netlist model exists "
            "in std.hdl (WO-82/D202) -- the named-absence surface, never "
            "a fabricated netlist.",
            "",
            "## Firmware (espresso_machine BrewCtl / stm32g071cb)",
            "",
            "- pipeline path: the stm32g0 registry record's own pin "
            "table -> `assign_pinmux` (WO-35 deterministic solver) for "
            "the uart2 debug pair -> `FirmwareDesign` -> "
            "`realize_firmware` (WO-37 codegen) -> `regolith ship "
            "--spec` with the `\"firmware\"` block (WO-102 channel).",
            "- pinmux assignments (each lockfile-caused):",
            "",
            "```",
            *pin_summary,
            "```",
            "",
            "- the shipped `build_report.json` names the honest ELF "
            "absence (no toolchain invocation pinned an image) -- the "
            "generated contract header, family-pack BSP, linker script "
            "and build fragment ship; a binary never does unless a real "
            "toolchain produced one.",
            "- no invented clocks/events: the design declares none in "
            "`on`-block/clock form, so those ledgers are empty.",
            "- WO115-F2 (named gap): no lowering pass derives "
            "`FirmwareDesign` from `computer`/`bind` declarations (the "
            "WO-37 input is caller-supplied by design, v1), and the "
            "cubesat OBC's stm32l496 family has no registered family "
            "pack (only the stm32g0 reference pack) -- fleet firmware "
            "ships only through this caller channel today.",
            "",
            "## Re-run",
            "",
            "```",
            "uv run python -m demos.demo12_firmware_hdl",
            "```",
            "",
            "## Artifacts",
            "",
            artifact_table(writer.rows),
        ]
    )
    writer.finish(
        live=True,
        optimized_quantity="n/a (computer-track families, not an optimizer surface)",
        domain="riscv_hart_rv1 hdl/ + espresso_machine firmware/",
        winner="n/a",
        cause_row="n/a",
        proof_md=proof,
    )
    return True


if __name__ == "__main__":
    run()
