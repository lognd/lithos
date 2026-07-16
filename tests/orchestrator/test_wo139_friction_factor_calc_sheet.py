"""WO-139 (D258.3/F158 GAP a1) end-to-end: a real `.fluo` project's
`fluids.dp(...)` claim discharges with a DERIVED friction factor (no
inline `friction_factor=`), and the calc package produced from a real
RELEASE build carries both the model's own citation ("Haaland 1983")
and the consumed roughness record's content hash -- the WO's own
acceptance criterion, checked directly against the real stdlib
records and the real `staged_build`/`build_calc_book` pipeline (the
`tests/golden/test_calc_corpus.py` pattern, applied to this fixture).
"""

from __future__ import annotations

import json
from pathlib import Path

from regolith._schema.models import Obligation
from regolith.backends.calc import build_calc_book, calc_book_json_bytes
from regolith.harness.registry import default_registry
from regolith.magnetite.stdlib_resolve import resolve_record_search_paths
from regolith.orchestrator.orchestrate import staged_build
from regolith.orchestrator.tiers import BuildTier

_PROJECT = Path(__file__).parent / "data" / "wo139_friction_factor_project"


def _build_book():  # noqa: ANN202 -- CalcBook
    root = str(_PROJECT)
    record_paths = resolve_record_search_paths(root)
    assert record_paths, "expected the dev-walk stdlib root to resolve for this fixture"
    built = staged_build(
        (root,),
        BuildTier.RELEASE,
        cost_record_paths=record_paths,
        frame_record_paths=record_paths,
        plan_record_paths=record_paths,
    )
    assert built.is_ok, f"staged_build failed: {built}"
    final = built.danger_ok.final
    payload = json.loads(final.payload_json)
    obligations = tuple(
        Obligation.model_validate(raw) for raw in payload["obligations"]
    )
    snapshots = {s["hash"]: s["scope"] for s in payload.get("snapshots", ())}
    registry = default_registry()
    return build_calc_book(
        "wo139_friction_factor_fixture",
        obligations,
        tuple(final.results),
        final.acceptance,
        snapshots=snapshots,
        citations=registry.citations(),
        input_units=registry.input_units(),
        output_units=registry.output_units(),
        tier="release",
        record_pins=final.fluid_record_pins,
        notes=final.fluid_derived_notes,
    )


def test_dp_claim_discharges_with_a_derived_friction_factor() -> None:
    """The `dp:` claim discharges (a derived `friction_factor`, no
    inline declaration) -- exactly one calc sheet, one discharged row."""
    book = _build_book()
    assert book.index.summary.discharged == 1, book.index
    assert len(book.sheets) == 1
    sheet = book.sheets[0]
    assert sheet.verdict == "discharged"
    assert sheet.model_id.startswith("fluid_darcy_weisbach_dp@")


def test_calc_package_cites_haaland_1983_and_the_roughness_record_hash() -> None:
    """The calc package's own bytes (the sheet's `citation` field +
    the WO-139 consumed-record-pin appendix) carry BOTH strings the
    WO's acceptance criterion greps for."""
    book = _build_book()
    book_bytes = calc_book_json_bytes(book)
    text = book_bytes.decode("utf-8")

    assert "Haaland" in text
    assert "1983" in text

    roughness_pin = next(
        (digest for key, digest in book.record_pins if "roughness" in key), None
    )
    assert roughness_pin is not None, book.record_pins
    assert roughness_pin in text
    assert any("roughness.commercial_steel" in key for key, _ in book.record_pins)
