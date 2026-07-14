"""`overrides.toml` ledger: format, ASCII determinism, content hash
(WO-129A deliverable 1, charter 42 sec. 2)."""

from __future__ import annotations

from regolith.orchestrator.overrides import (
    OverrideEntry,
    OverrideLedger,
    ledger_content_hash,
    parse,
    read_ledger,
    render,
    write_ledger,
)


def test_render_is_ascii_and_sorted_by_target() -> None:
    ledger = OverrideLedger(
        overrides=(
            OverrideEntry(target="z.slot", value="1mm", author="a", reason="r"),
            OverrideEntry(target="a.slot", value="2mm", author="a", reason="r"),
        )
    )
    text = render(ledger)
    assert text.isascii()
    assert text.index('target = "a.slot"') < text.index('target = "z.slot"')


def test_render_empty_ledger_is_empty_string() -> None:
    assert render(OverrideLedger()) == ""


def test_parse_render_round_trip() -> None:
    ledger = OverrideLedger(
        overrides=(
            OverrideEntry(
                target="printer_k1.Carriage.rail_span",
                value="240mm",
                author="logan",
                reason="matches the extrusion we already stock",
            ),
        )
    )
    text = render(ledger)
    parsed = parse(text)
    assert parsed.is_ok, parsed
    assert parsed.danger_ok == ledger


def test_content_hash_deterministic_and_order_independent() -> None:
    a = OverrideEntry(target="a", value="1mm", author="x", reason="r")
    b = OverrideEntry(target="b", value="2mm", author="x", reason="r")
    l1 = OverrideLedger(overrides=(a, b))
    l2 = OverrideLedger(overrides=(b, a))
    assert ledger_content_hash(l1) == ledger_content_hash(l2)
    assert ledger_content_hash(l1).startswith("blake3:")


def test_content_hash_differs_for_different_content() -> None:
    empty = OverrideLedger()
    populated = OverrideLedger(
        overrides=(OverrideEntry(target="a", value="1mm", author="x", reason="r"),)
    )
    assert ledger_content_hash(empty) != ledger_content_hash(populated)


def test_duplicate_target_refused() -> None:
    text = (
        '[[override]]\ntarget = "a"\nvalue = "1mm"\nauthor = "x"\nreason = "r"\n\n'
        '[[override]]\ntarget = "a"\nvalue = "2mm"\nauthor = "y"\nreason = "s"\n'
    )
    result = parse(text)
    assert result.is_err
    assert result.danger_err.kind == "duplicate_override_target"


def test_malformed_toml_refused() -> None:
    result = parse("not valid toml [[[")
    assert result.is_err
    assert result.danger_err.kind == "malformed_toml"


def test_read_ledger_missing_file_returns_empty(tmp_path) -> None:
    result = read_ledger(str(tmp_path))
    assert result.is_ok
    assert result.danger_ok == OverrideLedger()


def test_write_then_read_round_trips(tmp_path) -> None:
    ledger = OverrideLedger(
        overrides=(OverrideEntry(target="a.b", value="1mm", author="x", reason="r"),)
    )
    write_result = write_ledger(str(tmp_path), ledger)
    assert write_result.is_ok, write_result
    read_result = read_ledger(str(tmp_path))
    assert read_result.is_ok
    assert read_result.danger_ok == ledger


def test_mode_defaults_to_pin() -> None:
    entry = OverrideEntry(target="a", value="1mm", author="x", reason="r")
    assert entry.mode.value == "pin"
