"""Tests for WO-152: waveform/mask record rendering + AUTHORED badge.

Covers `regolith.backends.drawings.producers.waveform_chart` (deliverable
1: a real axes-with-ticks chart through the SAME renderer `opt_trace`
uses) and the AUTHORED badge (deliverable 2, D260 ruling 3) and mask-
overlay (deliverable 3) behavior it drives in `renderer.py`/
`renderer_pdf.py`.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from regolith.backends.debug_taps import Tap
from regolith.backends.drawings.producers import waveform_chart
from regolith.backends.drawings.renderer import render_svg
from regolith.backends.drawings.renderer_pdf import render_pdf
from regolith.backends.harness_pack import bringup_waveform_view
from regolith.magnetite.waveform import (
    Axes,
    Segment,
    WaveformEvidence,
    WaveformMaskRecord,
)


def _record(
    *,
    posture: str = "authored",
    key: str = "monotonic_rise",
    values: tuple[tuple[float, float], ...] = ((0.0, 0.0), (1.0, 1.0)),
) -> WaveformMaskRecord:
    """A `WaveformMaskRecord` fixture, one per posture (mirrors WO-151's
    own `tests/magnetite/test_waveform.py` fixture shapes)."""
    segments = tuple(Segment(t=t, v=v) for t, v in values)
    evidence = WaveformEvidence(
        method="analysis", trust_tier="community", reference="ref"
    )
    axes = Axes(t="s", value="V")
    if posture == "authored":
        return WaveformMaskRecord.construct_authored(
            package="std.elec",
            key=key,
            record_class="mask",
            quantity="elec.voltage",
            axes=axes,
            kind="envelope",
            interp="linear",
            segments=segments,
            tool="hand-drawn",
            author="logan",
            date="2026-07-19",
            evidence=evidence,
        )
    if posture == "measured":
        return WaveformMaskRecord.construct_measured(
            package="std.elec",
            key=key,
            record_class="waveform",
            quantity="elec.voltage",
            axes=axes,
            kind="nominal",
            interp="linear",
            segments=segments,
            instrument="scope-1",
            date="2026-07-19",
            operator="logan",
            evidence=evidence,
        )
    raise ValueError(posture)


class TestWaveformChartProducer:
    # frob:tests python/regolith/backends/drawings/producers.py::waveform_chart kind="unit"
    def test_deterministic_across_two_runs(self):
        record = _record()
        m1 = waveform_chart("demo", record)
        m2 = waveform_chart("demo", record)
        assert m1.model_dump_json(by_alias=True) == m2.model_dump_json(by_alias=True)
        assert render_svg(m1) == render_svg(m2)

    def test_svg_is_valid_xml(self):
        model = waveform_chart("demo", _record())
        ET.fromstring(render_svg(model))

    def test_chart_axes_and_record_name_present(self):
        # Deliverable 1 / charter 41 rule 6: axes/ticks, unit-labeled
        # title, and the record's own name -- "a polyline is not a
        # chart".
        model = waveform_chart("demo", _record())
        svg = render_svg(model)
        assert b"chart-axis" in svg
        assert b"chart-tick" in svg
        assert b"chart-axis-title" in svg
        assert b"monotonic_rise" in svg

    def test_one_view_source_kind_waveform_record(self):
        model = waveform_chart("demo", _record())
        assert model.sheets[0].views[0].source.source_kind == "waveform.record"

    # frob:tests python/regolith/backends/drawings/producers.py::_waveform_authored_annotation kind="unit"
    def test_authored_posture_renders_the_authored_badge(self):
        model = waveform_chart("demo", _record(posture="authored"))
        svg = render_svg(model)
        assert b"AUTHORED (design intent)" in svg
        assert b"authored-badge" in svg

    def test_measured_posture_renders_no_authored_badge(self):
        # D263.1/D260 ruling 3 provenance honesty: the badge is driven
        # by the record's OWN posture field, never assumed -- a
        # measured record renders visibly differently (no badge at
        # all), proving the two postures are not visually confusable.
        model = waveform_chart("demo", _record(posture="measured"))
        svg = render_svg(model)
        assert b"AUTHORED (design intent)" not in svg
        assert b"authored-badge" not in svg

    def test_authored_vs_measured_render_different_bytes(self):
        authored = render_svg(waveform_chart("demo", _record(posture="authored")))
        measured = render_svg(waveform_chart("demo", _record(posture="measured")))
        assert authored != measured

    def test_authored_badge_also_renders_in_pdf(self):
        model = waveform_chart("demo", _record(posture="authored"))
        pdf = render_pdf(model)
        assert b"AUTHORED" in pdf

    def test_measured_pdf_has_no_authored_text(self):
        model = waveform_chart("demo", _record(posture="measured"))
        pdf = render_pdf(model)
        assert b"AUTHORED" not in pdf


class TestWaveformMaskOverlay:
    # frob:tests python/regolith/backends/drawings/renderer.py::_chart_polylines kind="unit"
    def test_mask_overlay_renders_on_the_same_axes_not_a_second_figure(self):
        # Deliverable 3: a claim citing a mask overlays it on the
        # signal's OWN discharge chart -- one <g class="chart">, two
        # series, not a second sheet/view.
        signal = _record(key="signal", values=((0.0, 0.0), (1.0, 1.0)))
        mask = _record(key="ovp_mask", values=((0.0, 1.2), (1.0, 1.2)))
        model = waveform_chart("demo", signal, overlay=mask)
        assert len(model.sheets) == 1
        assert len(model.sheets[0].views) == 1
        svg = render_svg(model)
        assert svg.count(b'<g class="chart"') == 1
        assert b"chart-series-overlay" in svg

    def test_overlay_authored_badge_names_the_mask(self):
        signal = _record(
            key="signal", posture="measured", values=((0.0, 0.0), (1.0, 1.0))
        )
        mask = _record(
            key="ovp_mask", posture="authored", values=((0.0, 1.2), (1.0, 1.2))
        )
        model = waveform_chart("demo", signal, overlay=mask)
        svg = render_svg(model)
        assert b"AUTHORED (design intent)" in svg
        assert b"mask: std.elec/ovp_mask" in svg

    def test_no_overlay_yields_a_single_series(self):
        model = waveform_chart("demo", _record())
        svg = render_svg(model)
        assert b"chart-series-overlay" not in svg

    def test_pdf_mask_overlay_two_series_no_crash(self):
        signal = _record(key="signal", values=((0.0, 0.0), (1.0, 1.0)))
        mask = _record(key="ovp_mask", values=((0.0, 1.2), (1.0, 1.2)))
        model = waveform_chart("demo", signal, overlay=mask)
        pdf = render_pdf(model)
        assert pdf.startswith(b"%PDF-1.4")


class TestBringupWaveformView:
    """Deliverable 5: the same mask beside a tap's expected scalar, in
    the SAME view (`bringup_waveform_view`, `harness_pack.py`)."""

    # frob:tests python/regolith/backends/harness_pack.py::bringup_waveform_view kind="unit"
    def test_tap_table_and_chart_share_one_sheet(self):
        tap = Tap(
            channel=3,
            kind="rail",
            target_path="net.vout",
            why="claim rail_ripple",
            source="derived",
        )
        signal = _record(key="signal", values=((0.0, 0.0), (1.0, 1.0)))
        mask = _record(key="ovp_mask", values=((0.0, 1.2), (1.0, 1.2)))
        model = bringup_waveform_view(tap, "1.0", "V", signal, overlay=mask)
        assert len(model.sheets) == 1
        sheet = model.sheets[0]
        assert any(t.title == "Tap 3" for t in sheet.tables)
        svg = render_svg(model)
        assert b"chart-series-overlay" in svg
        assert b"net.vout" in svg


class TestOptTraceUnaffectedByWaveformChanges:
    """WO-152 generalized the chart branch (`_chart_polylines`/
    `_chart_labels`) for `optimize.trace` too -- these pin that the
    existing opt-trace golden behavior is byte-identical (backward
    compatibility by construction, since a continuous chain never
    splits and a non-waveform view keeps its hardcoded labels)."""

    # frob:tests python/regolith/backends/drawings/renderer.py::_chart_labels kind="unit"
    def test_opt_trace_chart_still_labeled_objective_vs_candidate_index(self):
        from regolith._schema.models import (
            AssignmentItem,
            CandidateEntry,
            ObjectiveDirection1,
            OptimizationTrace,
            TerminationStatus1,
        )
        from regolith.backends.drawings.producers import opt_trace

        trace = OptimizationTrace(
            strategy_id="optimize_discrete",
            strategy_version="1",
            seed=42,
            budget_declared=10,
            budget_spent=2,
            objective=[ObjectiveDirection1.minimize],
            candidates=[
                CandidateEntry(
                    assignment=[AssignmentItem(["choice.a", "vendor_a"])],
                    objective_vector=[3.0],
                    feasible=True,
                    verdict_summary="all demands dischargeable",
                    evidence_digests=["blake3:aa"],
                ),
                CandidateEntry(
                    assignment=[AssignmentItem(["choice.a", "vendor_b"])],
                    objective_vector=[1.5],
                    feasible=True,
                    verdict_summary="all demands dischargeable",
                    evidence_digests=["blake3:bb"],
                ),
            ],
            nogood_keys=[],
            winner=1,
            termination=TerminationStatus1.converged,
        )
        model = opt_trace("gearbox_ratio", trace)
        svg = render_svg(model)
        assert b"candidate index" in svg
        assert b"objective" in svg
