"""WO-37 close-out follow-up: `EventDecl` built from the real typed
`on <event>:` CST (`OnBlock`), not a forward-authored placeholder.

Mirrors `test_realize.py`'s precedent (real codegen path, no fakes)
but exercises `events_from_on_blocks` against a real `.cupr` fixture
through the full FFI crossing (`regolith.compiler.on_events` ->
`regolith._core.on_events` -> `regolith_api::on_events` ->
`regolith_lower::converter::collect_on_events`).
"""

from __future__ import annotations

from pathlib import Path

from regolith.realizer.firmware.contract import EventDecl, events_from_on_blocks

_SOURCE = (
    "block Regulator:\n"
    "    ports:\n"
    "        ctrl_clk: clock(200kHz)\n"
    "    spec:\n"
    "        on ctrl_clk.rise:\n"
    "            a = b\n"
)


def _write_fixture(tmp_path: Path) -> str:
    path = tmp_path / "m.cupr"
    path.write_text(_SOURCE)
    return str(path)


def test_events_read_from_real_on_block_cst(tmp_path: Path) -> None:
    path = _write_fixture(tmp_path)
    result = events_from_on_blocks(
        (path,),
        pins={"ctrl_clk": "PA1"},
        interrupt_capable={"ctrl_clk": True},
    )
    assert result.is_ok
    events = result.danger_ok
    assert events == (
        EventDecl(
            event_id=0,
            name="ctrl_clk",
            pin="PA1",
            interrupt_capable=True,
            cause="lower(on Regulator.ctrl_clk)",
        ),
    )


def test_events_default_to_no_pin_and_not_interrupt_capable(tmp_path: Path) -> None:
    path = _write_fixture(tmp_path)
    result = events_from_on_blocks((path,))
    assert result.is_ok
    events = result.danger_ok
    assert len(events) == 1
    assert events[0].pin is None
    assert events[0].interrupt_capable is False


def test_causes_override_is_honored(tmp_path: Path) -> None:
    path = _write_fixture(tmp_path)
    result = events_from_on_blocks(
        (path,), causes={"ctrl_clk": "planner(event ctrl_clk)"}
    )
    assert result.is_ok
    assert result.danger_ok[0].cause == "planner(event ctrl_clk)"


def test_no_on_blocks_yields_empty_tuple(tmp_path: Path) -> None:
    path = tmp_path / "empty.cupr"
    path.write_text("block Idle:\n    spec:\n        a = b\n")
    result = events_from_on_blocks((str(path),))
    assert result.is_ok
    assert result.danger_ok == ()
