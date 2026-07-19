"""WO-151/D263.1: the waveform/mask record class + posture taxonomy.

Every posture path is exercised both ways (construct/refuse): `authored`
succeeds through the only constructor an authoring-surface code path
can reach; `measured` refuses without instrument-provenance fields;
`model_derived` refuses without a resolving calc-sheet hash;
posture-less construction is unrepresentable (pydantic refuses it
outright, not a runtime `if` check).
"""

from __future__ import annotations

from typing import Literal

import pytest
from pydantic import ValidationError
from regolith.magnetite.waveform import (
    Axes,
    Segment,
    WaveformEvidence,
    WaveformMaskRecord,
    load_waveform_mask_records,
    resolve_mask_ref,
)


def _axes() -> Axes:
    return Axes(t="s", value="V")


def _segments() -> tuple[Segment, ...]:
    return (Segment(t=0.0, v=0.0), Segment(t=0.005, v=1.0))


def _evidence() -> WaveformEvidence:
    return WaveformEvidence(
        method="analysis", trust_tier="community", reference="design intent"
    )


# frob:tests python/regolith/magnetite/waveform.py::WaveformMaskRecord.construct_authored kind="unit"
# frob:tests python/regolith/magnetite/waveform.py::WaveformMaskRecord.construct_measured kind="unit"
# frob:tests python/regolith/magnetite/waveform.py::WaveformMaskRecord.construct_model_derived kind="unit"
def test_waveform_record_authored_construction_succeeds() -> None:
    record = WaveformMaskRecord.construct_authored(
        package="p",
        key="monotonic_rise",
        record_class="mask",
        quantity="elec.voltage",
        axes=_axes(),
        kind="envelope",
        interp="linear",
        segments=_segments(),
        tool="hand-drawn",
        author="reviewer",
        date="2026-07-19",
        evidence=_evidence(),
    )
    assert record.provenance.posture == "authored"
    assert record.content_hash.startswith("sha256:")


def test_waveform_record_measured_construction_refuses_without_instrument_fields() -> (
    None
):
    with pytest.raises(TypeError):
        WaveformMaskRecord.construct_measured(  # ty: ignore[missing-argument]  # proving the constructor refuses without instrument fields
            package="p",
            key="k",
            record_class="mask",
            quantity="elec.voltage",
            axes=_axes(),
            kind="envelope",
            interp="linear",
            segments=_segments(),
            evidence=_evidence(),
        )


def test_waveform_record_measured_construction_succeeds_with_instrument_fields() -> (
    None
):
    record = WaveformMaskRecord.construct_measured(
        package="p",
        key="k",
        record_class="mask",
        quantity="elec.voltage",
        axes=_axes(),
        kind="envelope",
        interp="linear",
        segments=_segments(),
        instrument="MSO5204",
        date="2026-07-19",
        operator="bench-tech",
        evidence=_evidence(),
    )
    assert record.provenance.posture == "measured"


def test_waveform_record_model_derived_construction_refuses_without_resolving_hash() -> (
    None
):
    result = WaveformMaskRecord.construct_model_derived(
        package="p",
        key="k",
        record_class="mask",
        quantity="elec.voltage",
        axes=_axes(),
        kind="envelope",
        interp="linear",
        segments=_segments(),
        calc_sheet_hash="",
        evidence=_evidence(),
    )
    assert result.is_err
    assert result.danger_err.kind == "model_derived_unresolvable_hash"


def test_waveform_record_model_derived_construction_succeeds_with_resolving_hash() -> (
    None
):
    result = WaveformMaskRecord.construct_model_derived(
        package="p",
        key="k",
        record_class="mask",
        quantity="elec.voltage",
        axes=_axes(),
        kind="envelope",
        interp="linear",
        segments=_segments(),
        calc_sheet_hash="sha256:" + "a" * 64,
        evidence=_evidence(),
    )
    assert result.is_ok
    assert result.danger_ok.provenance.posture == "model_derived"


def test_waveform_record_posture_less_construction_is_unrepresentable() -> None:
    # `class` is a reserved word and can't be a normal kwarg -- unpack a
    # dict typed to the field's real `Literal["waveform", "mask"]` alias
    # type instead of losing it to `str`.
    class_kwarg: dict[str, Literal["waveform", "mask"]] = {"class": "mask"}
    with pytest.raises(ValidationError):
        WaveformMaskRecord(
            package="p",
            key="k",
            **class_kwarg,
            quantity="elec.voltage",
            axes=_axes(),
            kind="envelope",
            interp="linear",
            segments=_segments(),
            evidence=_evidence(),
            content_hash="sha256:" + "a" * 64,
        )


def test_load_waveform_mask_records_reads_the_real_corpus_row() -> None:
    result = load_waveform_mask_records(
        "examples/tracks/cuprite/records/masks.toml", "examples.tracks.cuprite"
    )
    assert result.is_ok
    records = result.danger_ok
    assert len(records) == 1
    assert records[0].key == "monotonic_rise"
    assert records[0].record_class == "mask"
    assert records[0].provenance.posture == "authored"


def test_resolve_mask_ref_strips_call_args_and_resolves_the_real_corpus_row() -> None:
    result = resolve_mask_ref(
        "monotonic_rise(5ms)",
        ("examples/tracks/cuprite/records",),
        package="examples.tracks.cuprite",
    )
    assert result.is_ok
    assert result.danger_ok.key == "monotonic_rise"


def test_resolve_mask_ref_reports_not_found_for_an_unknown_name() -> None:
    result = resolve_mask_ref(
        "nonexistent_mask",
        ("examples/tracks/cuprite/records",),
        package="examples.tracks.cuprite",
    )
    assert result.is_err
    assert result.danger_err.kind == "not_found"


def test_resolve_mask_ref_refuses_a_model_derived_row_with_an_unresolving_hash(
    tmp_path,
) -> None:
    records_dir = tmp_path / "records"
    records_dir.mkdir()
    (records_dir / "masks.toml").write_text(
        """
[[waveform]]
key = "bad_derived"
class = "mask"
quantity = "elec.voltage"
axes = { t = "s", value = "V" }
kind = "envelope"
interp = "linear"
segments = [{ t = 0.0, v = 0.0 }, { t = 1.0, v = 1.0 }]

[waveform.provenance]
posture = "model_derived"
calc_sheet_hash = "sha256:deadbeef"

[waveform.evidence]
method = "analysis"
trust_tier = "community"
reference = "x"
""",
        encoding="ascii",
    )
    result = resolve_mask_ref(
        "bad_derived", (str(records_dir),), package="p", calc_sheet_digests=frozenset()
    )
    assert result.is_err
    assert result.danger_err.kind == "model_derived_unresolvable_hash"
