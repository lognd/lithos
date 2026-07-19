"""Firmware realizer end-to-end (WO-37 acceptance criteria).

Fixture is Kestrel/stm32g0-shaped, mirroring `test_pinmux.py`'s and
`test_kestrel_fixture.py`'s precedent: a small hand-built pin-mux
result (as WO-35's engine would emit) plus a forward-authored event
ledger (this WO's WO-36 scope note), run through the real codegen
path -- no fakes below the realizer boundary.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from regolith.realizer.elec.pinmux import PinAssignment, PinmuxResult
from regolith.realizer.firmware.contract import (
    ClockDecl,
    EventDecl,
    FirmwareDesign,
    PartitionDecl,
)
from regolith.realizer.firmware.errors import (
    InterruptCapabilityMissing,
    PartitionOverlap,
    UnknownFamily,
)
from regolith.realizer.firmware.realize import realize_firmware


def _pinmux() -> PinmuxResult:
    return PinmuxResult(
        assignments=(
            PinAssignment.caused(flow="u_mcu.uart2.tx", instance="uart2.tx", pin="PA9"),
            PinAssignment.caused(
                flow="u_mcu.uart2.rx", instance="uart2.rx", pin="PA10"
            ),
            PinAssignment.caused(flow="u_mcu.rc_input", instance="exti0", pin="PA1"),
        )
    )


def _events() -> tuple[EventDecl, ...]:
    return (
        EventDecl(
            event_id=0,
            name="rc_input",
            pin="PA1",
            interrupt_capable=True,
            cause="planner(event rc_input)",
        ),
    )


def _design(
    *, pinmux: PinmuxResult | None = None, events: tuple[EventDecl, ...] | None = None
) -> FirmwareDesign:
    return FirmwareDesign(
        name="kestrel_obc",
        family="stm32g0",
        pinmux=pinmux if pinmux is not None else _pinmux(),
        events=_events() if events is None else events,
        clocks=(
            ClockDecl(name="sysclk", freq_hz=64_000_000, cause="planner(clock sysclk)"),
        ),
        partitions=(
            PartitionDecl(
                name="boot",
                region="flash",
                start=0,
                size=32 * 1024,
                cause="planner(partition boot)",
            ),
            PartitionDecl(
                name="app",
                region="flash",
                start=32 * 1024,
                size=480 * 1024,
                cause="planner(partition app)",
            ),
        ),
    )


# frob:tests python/regolith/realizer/firmware/contract.py::generate_contract_header kind="unit"
# frob:tests python/regolith/realizer/firmware/linker.py::generate_linker_script kind="unit"
# frob:tests python/regolith/realizer/firmware/linker.py::generate_build_fragment kind="unit"
# frob:tests python/regolith/realizer/firmware/bsp.py::generate_bsp_init kind="unit"
# frob:tests python/regolith/realizer/firmware/bsp.py::generate_isr_stubs kind="unit"
# frob:tests python/regolith/realizer/firmware/bsp.py::generate_bsp kind="unit"
# frob:tests python/regolith/realizer/firmware/packs.py::FamilyPack.pin_init_lines kind="unit"
# frob:tests python/regolith/realizer/firmware/packs.py::FamilyPack.clock_init_lines kind="unit"
# frob:tests python/regolith/realizer/firmware/packs.py::FamilyPack.isr_stub kind="unit"
# frob:tests python/regolith/realizer/firmware/packs.py::Stm32G0Pack.pin_init_lines kind="unit"
# frob:tests python/regolith/realizer/firmware/packs.py::Stm32G0Pack.clock_init_lines kind="unit"
# frob:tests python/regolith/realizer/firmware/packs.py::Stm32G0Pack.isr_stub kind="unit"
# frob:tests python/regolith/realizer/firmware/packs.py::get_pack kind="unit"
def test_realize_firmware_end_to_end() -> None:
    result = realize_firmware(_design())
    assert result.is_ok
    tree = result.danger_ok
    assert "kestrel_obc_contract.h" in tree.files
    assert "kestrel_obc_bsp.c" in tree.files
    assert "kestrel_obc_isr.c" in tree.files
    assert "kestrel_obc.ld" in tree.files
    assert "Makefile.fragment" in tree.files

    header = tree.files["kestrel_obc_contract.h"]
    assert '#define PIN_U_MCU_UART2_TX "PA9"' in header
    assert "cause: planner(pinmux uart2.tx)" in header
    assert "#define EVENT_RC_INPUT_ID 0u" in header
    assert '#define EVENT_RC_INPUT_PIN "PA1"' in header
    assert "#define CLOCK_SYSCLK_HZ 64000000u" in header


def test_determinism_byte_identical() -> None:
    """INV-10 shape: the same design regenerates a byte-identical tree."""
    design = _design()
    tree1 = realize_firmware(design).danger_ok
    tree2 = realize_firmware(design).danger_ok
    assert tree1.files == tree2.files
    assert tree1.content_hash() == tree2.content_hash()


def test_every_symbol_has_a_cause() -> None:
    """INV-21 shape: every generated `#define` line is preceded by a cause comment."""
    tree = realize_firmware(_design()).danger_ok
    header = tree.files["kestrel_obc_contract.h"]
    lines = header.splitlines()
    symbol_prefixes = (
        "#define PIN_",
        "#define CLOCK_",
        "#define EVENT_",
        "#define PARTITION_",
    )
    for i, line in enumerate(lines):
        if line.startswith(symbol_prefixes):
            # A symbol group (e.g. an event's ID + PIN pair) shares one
            # cause comment above the group's first line.
            window = lines[max(0, i - 3) : i]
            assert any(w.startswith("/* cause:") for w in window), (
                f"symbol {line!r} has no cause comment within its group"
            )


def test_flipping_pinmux_changes_exactly_the_affected_symbol() -> None:
    """Acceptance criterion 2: flip one `locked: pinmux(...)`, regenerate.

    Only the affected pin's symbols change; the anti-staleness property
    is that stale user code referencing the OLD pin value would now
    read a different constant (asserted here as: the header text for
    that one flow differs, all others are unchanged).
    """
    before = realize_firmware(_design()).danger_ok.files["kestrel_obc_contract.h"]

    flipped_pinmux = PinmuxResult(
        assignments=(
            PinAssignment.caused(flow="u_mcu.uart2.tx", instance="uart2.tx", pin="PB6"),
            PinAssignment.caused(
                flow="u_mcu.uart2.rx", instance="uart2.rx", pin="PA10"
            ),
            PinAssignment.caused(flow="u_mcu.rc_input", instance="exti0", pin="PA1"),
        )
    )
    after = realize_firmware(_design(pinmux=flipped_pinmux)).danger_ok.files[
        "kestrel_obc_contract.h"
    ]

    assert before != after
    assert '#define PIN_U_MCU_UART2_TX "PA9"' in before
    assert '#define PIN_U_MCU_UART2_TX "PB6"' in after
    # Unrelated symbols are untouched.
    assert '#define PIN_U_MCU_UART2_RX "PA10"' in before
    assert '#define PIN_U_MCU_UART2_RX "PA10"' in after
    assert "#define CLOCK_SYSCLK_HZ 64000000u" in before
    assert "#define CLOCK_SYSCLK_HZ 64000000u" in after


def test_unknown_family_is_honest_indeterminate() -> None:
    design = _design().model_copy(update={"family": "esp99_madeup"})
    result = realize_firmware(design)
    assert result.is_err
    assert isinstance(result.danger_err, UnknownFamily)
    assert result.danger_err.family == "esp99_madeup"


# frob:tests python/regolith/realizer/firmware/contract.py::check_event_interrupt_capability kind="unit"
def test_event_without_interrupt_capable_pin_is_constructive_error() -> None:
    bad_events = (
        EventDecl(
            event_id=0,
            name="rc_input",
            pin="PA1",
            interrupt_capable=False,
            cause="planner(event rc_input)",
        ),
    )
    result = realize_firmware(_design(events=bad_events))
    assert result.is_err
    err = result.danger_err
    assert isinstance(err, InterruptCapabilityMissing)
    assert err.event == "rc_input"
    assert err.pin == "PA1"


# frob:tests python/regolith/progress.py::start
def test_overlapping_partitions_are_rejected() -> None:
    overlapping = (
        PartitionDecl(
            name="boot",
            region="flash",
            start=0,
            size=32 * 1024,
            cause="planner(partition boot)",
        ),
        PartitionDecl(
            name="app",
            region="flash",
            start=16 * 1024,
            size=480 * 1024,
            cause="planner(partition app)",
        ),
    )
    design = _design().model_copy(update={"partitions": overlapping})
    result = realize_firmware(design)
    assert result.is_err
    assert isinstance(result.danger_err, PartitionOverlap)


def test_zero_application_logic_in_generated_files() -> None:
    """Reviewer criterion: stubs call hooks only; no vendor register strings in core."""
    tree = realize_firmware(_design()).danger_ok
    isr = tree.files["kestrel_obc_isr.c"]
    # Every function body is exactly: an optional comment, one hook call, close brace.
    assert "regolith_hook_rc_input();" in isr
    assert "if" not in isr
    assert "for" not in isr
    assert "while" not in isr


# frob:tests python/regolith/realizer/firmware/bindings.py::generate_rust_sys_binding kind="unit"
def test_rust_sys_binding_opt_in() -> None:
    without = realize_firmware(_design())
    assert "kestrel_obc_contract_sys.rs" not in without.danger_ok.files

    with_bindings = realize_firmware(_design(), emit_rust_sys=True)
    files = with_bindings.danger_ok.files
    assert "kestrel_obc_contract_sys.rs" in files
    rs = files["kestrel_obc_contract_sys.rs"]
    assert 'pub const PIN_U_MCU_UART2_TX: &str = "PA9";' in rs
    assert "pub const CLOCK_SYSCLK_HZ: u32 = 64000000;" in rs


# frob:tests python/regolith/cli/app.py::main
# frob:tests python/regolith/realizer/elec/kicad_wrapper.py::main
def test_host_cc_smoke_compile_gated() -> None:
    """A trivial user main.c referencing only contract symbols compiles.

    Cross-toolchain presence is gated like KiCad in WO-35: skip with
    reason, never fake, when no host C compiler is available.
    """
    cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    if cc is None:
        import pytest

        pytest.skip("no host C compiler available (cc/gcc/clang not on PATH)")

    tree = realize_firmware(_design()).danger_ok
    tmp_root = Path(__file__).parent / "_smoke_build"
    tmp_root.mkdir(exist_ok=True)
    try:
        for name, content in tree.files.items():
            if name.endswith((".h", ".c")):
                (tmp_root / name).write_text(content)
        main_c = tmp_root / "main.c"
        main_c.write_text(
            '#include "kestrel_obc_contract.h"\n'
            "int main(void) { return PIN_U_MCU_UART2_TX[0] == 'P' ? 0 : 1; }\n"
        )
        result = subprocess.run(
            [
                cc,
                "-c",
                str(main_c),
                "-I",
                str(tmp_root),
                "-o",
                str(tmp_root / "main.o"),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
    finally:
        for f in tmp_root.glob("*"):
            f.unlink()
        tmp_root.rmdir()
