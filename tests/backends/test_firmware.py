"""Tests for `FirmwareBackend` (WO-102 deliverable 1).

The fixture is `tests/realizer/firmware/test_realize.py`'s own
Kestrel/stm32g0-shaped design run through the REAL WO-37 realizer (no
fakes below the realizer boundary): the WO-37 exemplar the WO body
names for the "a firmware fixture ships `firmware/` with a verifiable
content address" acceptance test.
"""

from __future__ import annotations

from regolith.backends.artifacts import NativeArtifactStore
from regolith.backends.firmware import NO_ELF_REASON, FirmwareArtifact, FirmwareBackend
from regolith.backends.framework import BackendInputs
from regolith.orchestrator.lockfile import Lockfile
from regolith.realizer.elec.pinmux import PinAssignment, PinmuxResult
from regolith.realizer.firmware.contract import ClockDecl, EventDecl, FirmwareDesign
from regolith.realizer.firmware.realize import realize_firmware


def _design() -> FirmwareDesign:
    return FirmwareDesign(
        name="kestrel_obc",
        family="stm32g0",
        pinmux=PinmuxResult(
            assignments=(
                PinAssignment.caused(
                    flow="u_mcu.uart2.tx", instance="uart2.tx", pin="PA9"
                ),
            )
        ),
        events=(
            EventDecl(
                event_id=0,
                name="rc_input",
                pin="PA1",
                interrupt_capable=True,
                cause="planner(event rc_input)",
            ),
        ),
        clocks=(
            ClockDecl(name="sysclk", freq_hz=64_000_000, cause="planner(clock sysclk)"),
        ),
        partitions=(),
    )


def _inputs(
    *, project_root: str, firmware: dict[str, FirmwareArtifact]
) -> BackendInputs:
    return BackendInputs(
        lockfile=Lockfile(tool_version="0.1.0"),
        evidence={},
        geometry={},
        layouts={},
        native=NativeArtifactStore(project_root),
        firmware=firmware,
    )


def test_firmware_backend_ships_generated_tree_and_report(tmp_path) -> None:
    tree = realize_firmware(_design()).danger_ok
    artifact = FirmwareArtifact(tree=tree, toolchain=None)
    inputs = _inputs(project_root=str(tmp_path), firmware={"kestrel_obc": artifact})

    produced = FirmwareBackend().produce(inputs)
    assert produced.is_ok, produced

    files = {f.relpath: f for f in produced.danger_ok}
    assert "firmware/kestrel_obc/build_report.json" in files
    for name in tree.files:
        assert f"firmware/kestrel_obc/generated/{name}" in files
    # No ELF was pinned: the report names the honest reason, never a
    # fabricated image, and no image.elf file is emitted at all.
    report = files["firmware/kestrel_obc/build_report.json"].content
    assert b'"present":false' in report
    assert NO_ELF_REASON.encode("ascii") in report
    assert not any(p.endswith("image.elf") for p in files)


def test_firmware_backend_is_deterministic() -> None:
    """Same design realized twice -> byte-identical shipped tree (INV-10
    shape, WO-37's own guarantee, carried through unchanged by this
    backend since it only serializes)."""
    tree_a = realize_firmware(_design()).danger_ok
    tree_b = realize_firmware(_design()).danger_ok
    assert tree_a.content_hash() == tree_b.content_hash()

    inputs = _inputs(
        project_root="/tmp/unused-firmware-determinism",
        firmware={"kestrel_obc": FirmwareArtifact(tree=tree_a)},
    )
    first = FirmwareBackend().produce(inputs)
    second = FirmwareBackend().produce(inputs)
    assert first.is_ok and second.is_ok
    first_hashes = {f.relpath: f.sha256 for f in first.danger_ok}
    second_hashes = {f.relpath: f.sha256 for f in second.danger_ok}
    assert first_hashes == second_hashes


def test_firmware_backend_ships_pinned_elf(tmp_path) -> None:
    """A caller that persisted ELF bytes into the `NativeArtifactStore`
    at realize time (WO-99 D5 precedent) gets them resolved and
    packaged -- never recompiled."""
    tree = realize_firmware(_design()).danger_ok
    store = NativeArtifactStore(str(tmp_path))
    digest = store.put(b"\x7fELF-fake-image-bytes")
    artifact = FirmwareArtifact(
        tree=tree,
        toolchain="riscv32-unknown-elf-gcc",
        toolchain_version="13.2.0",
        flags=("-Os", "-mcpu=cortex-m0"),
        elf_content_hash=digest,
        link_map="kestrel_obc.ld map\n.text 0x08000000 4096\n",
    )
    inputs = _inputs(project_root=str(tmp_path), firmware={"kestrel_obc": artifact})

    produced = FirmwareBackend().produce(inputs)
    assert produced.is_ok, produced
    files = {f.relpath: f for f in produced.danger_ok}
    assert (
        files["firmware/kestrel_obc/image.elf"].content == b"\x7fELF-fake-image-bytes"
    )
    assert "firmware/kestrel_obc/link_map.txt" in files
    report = files["firmware/kestrel_obc/build_report.json"].content
    assert b'"present":true' in report
    assert digest.encode("ascii") in report


def test_firmware_backend_pinned_elf_missing_from_store_is_named_err(tmp_path) -> None:
    """A digest the caller claims is pinned but the store cannot resolve
    is an honest `Err` (WO-99 D5 persistence did not happen), never a
    silent skip or a fabricated image."""
    tree = realize_firmware(_design()).danger_ok
    artifact = FirmwareArtifact(tree=tree, elf_content_hash="deadbeef" * 8)
    inputs = _inputs(project_root=str(tmp_path), firmware={"kestrel_obc": artifact})

    produced = FirmwareBackend().produce(inputs)
    assert produced.is_err
    assert produced.danger_err.kind == "native_artifact_not_found"


def test_firmware_backend_no_subjects_ships_nothing() -> None:
    inputs = _inputs(project_root="/tmp/unused-firmware-empty", firmware={})
    produced = FirmwareBackend().produce(inputs)
    assert produced.is_ok
    assert produced.danger_ok == ()
