"""Calc-package golden (WO-114, D221): the calc book + audit index for two
fleet projects -- one mech-heavy (cnc_router_r1), one civil/schedule
(timber_pavilion) -- frozen as canonical bytes.

Each project is built at its real RELEASE tier (the only tier that
discharges obligations, so the only tier a calc book has sheets for),
its own obligations/results/acceptance feed `build_calc_book`, and the
canonical ``calc_book.json`` + ``audit_index.json`` bytes are the golden.
The suite also proves, per project:

* determinism -- the same design builds byte-identical calc bytes twice
  (AD-6/INV-10);
* zero unexplained rows -- every obligation has exactly one audit row and
  the row partition balances;
* census reconciliation -- the audit summary's census-shape projection
  matches the committed ``fleet_census.json`` row field for field, so the
  audit index and the fleet census can never silently disagree.

Regeneration: never hand-edit. Run
``REGOLITH_UPDATE_GOLDEN=1 pytest tests/golden/test_calc_corpus.py``
and diff-review the change like any other generated artifact.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from regolith._schema.models import Obligation
from regolith.backends.calc import (
    audit_index_json_bytes,
    build_calc_book,
    calc_book_json_bytes,
)
from regolith.harness.registry import default_registry
from regolith.magnetite.stdlib_resolve import resolve_record_search_paths
from regolith.orchestrator.orchestrate import staged_build
from regolith.orchestrator.tiers import BuildTier

_DATA_DIR = Path(__file__).parent / "data"
_CENSUS_GOLDEN = _DATA_DIR / "fleet_census.json"

# One mech-heavy project + one civil/schedule project (WO-114 deliverable 5).
_CORPUS: dict[str, str] = {
    "cnc_router_r1": "examples/flagships/cnc_router_r1",
    "timber_pavilion": "examples/flagships/timber_pavilion",
}


def _build_book(name: str):  # noqa: ANN202 -- CalcBook
    """Build ``name`` at RELEASE tier and assemble its calc book."""
    root = _CORPUS[name]
    record_paths = resolve_record_search_paths(root)
    built = staged_build(
        (root,),
        BuildTier.RELEASE,
        cost_record_paths=record_paths,
        frame_record_paths=record_paths,
        plan_record_paths=record_paths,
    )
    assert built.is_ok, f"{name}: staged_build failed: {built}"
    final = built.danger_ok.final
    payload = json.loads(final.payload_json)
    obligations = tuple(
        Obligation.model_validate(raw) for raw in payload["obligations"]
    )
    snapshots = {s["hash"]: s["scope"] for s in payload.get("snapshots", ())}
    return build_calc_book(
        name,
        obligations,
        tuple(final.results),
        final.acceptance,
        snapshots=snapshots,
        citations=default_registry().citations(),
        tier="release",
    )


@pytest.mark.parametrize("name", sorted(_CORPUS))
# frob:tests python/regolith/backends/artifact_index.py::index_bytes kind="unit"
def test_calc_book_golden(name: str) -> None:
    """The canonical calc book + audit index bytes match their goldens."""
    book = _build_book(name)
    book_bytes = calc_book_json_bytes(book)
    index_bytes = audit_index_json_bytes(book)

    book_golden = _DATA_DIR / f"calc_book_{name}.json"
    index_golden = _DATA_DIR / f"calc_audit_{name}.json"

    if os.environ.get("REGOLITH_UPDATE_GOLDEN") == "1":
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        book_golden.write_bytes(book_bytes)
        index_golden.write_bytes(index_bytes)
        pytest.skip(f"REGOLITH_UPDATE_GOLDEN=1: rewrote {name} calc goldens")

    assert book_golden.exists(), (
        f"no golden at {book_golden}; regenerate with REGOLITH_UPDATE_GOLDEN=1"
    )
    assert book_bytes == book_golden.read_bytes(), (
        f"calc-book drift for {name!r} -- if intended, regenerate with "
        "REGOLITH_UPDATE_GOLDEN=1 and review the diff"
    )
    assert index_bytes == index_golden.read_bytes(), (
        f"audit-index drift for {name!r} -- if intended, regenerate with "
        "REGOLITH_UPDATE_GOLDEN=1 and review the diff"
    )


@pytest.mark.parametrize("name", sorted(_CORPUS))
def test_calc_book_deterministic(name: str) -> None:
    """The same design builds byte-identical calc bytes twice (AD-6)."""
    first = calc_book_json_bytes(_build_book(name))
    second = calc_book_json_bytes(_build_book(name))
    assert first == second, f"{name}: calc book is not byte-deterministic"


@pytest.mark.parametrize("name", sorted(_CORPUS))
def test_zero_unexplained_rows(name: str) -> None:
    """Every obligation maps to exactly one audit row; the partition balances."""
    book = _build_book(name)
    summary = book.index.summary
    assert len(book.index.rows) == summary.obligations, (
        f"{name}: {len(book.index.rows)} rows for {summary.obligations} obligations"
    )
    assert summary.balanced(), f"{name}: audit index does not balance"
    assert all(
        row.disposition in ("calc_sheet", "accepted_deviation", "deferred", "violated")
        for row in book.index.rows
    ), f"{name}: an audit row carries an unknown disposition"
    assert len(book.sheets) == summary.discharged, (
        f"{name}: {len(book.sheets)} sheets for {summary.discharged} discharged"
    )


@pytest.mark.parametrize("name", sorted(_CORPUS))
def test_census_reconciliation(name: str) -> None:
    """The audit summary's census-shape row matches ``fleet_census.json``."""
    census = json.loads(_CENSUS_GOLDEN.read_text())
    assert name in census, f"{name} not enrolled in the fleet census golden"
    row = census[name]
    got = _build_book(name).index.summary.census_row()
    for field in ("obligations", "discharged", "accepted_deviation", "violated"):
        assert got[field] == row[field], (
            f"{name}: audit summary {field}={got[field]} disagrees with the "
            f"census golden {field}={row[field]}"
        )
