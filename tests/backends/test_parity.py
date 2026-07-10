"""Tests for the WO-63 parity ledger (`regolith ship --explain`, AD-33).

Three layers, per the WO's acceptance criteria:

1. Unit coverage of every provenance class + the injection test proving
   the "unclassifiable cause is a loud REPORT ERROR" honesty path.
2. The demand table / assumed-waived ledger over a fabricated
   `WaiveLedger` (mirrors `tests/backends/test_ship.py`'s own
   dependency-injection discipline for T3-unreachable-in-sandbox
   fixtures).
3. Real corpus designs: `coolant_gallery` (a real `realizer(...)`
   cause via `staged_build`) and `ebi_decode` (a real
   `optimize(...)` cause via the landed WO-56 discrete driver,
   mirroring `tests/test_wo56_ebi_decode.py`) prove the classifier
   against actual build output, not just fixtures.

Escalated gap (recorded in `parity.py`'s own module docstring and
`docs/workflow/design-log/2026-07-09-cycle-31.md` addendum D170-a):
no corpus member named `duct_vane` exists yet (WO-57's own exemplar,
"todo" in this tree) -- the "duct_vane's dims show optimize causes"
acceptance line is proven here with `ebi_decode`'s real `select`
optimize winner instead, the same provenance-class shape (`optimize(
<objective>, trace=<digest>)`) a staged-loop continuous winner would
produce.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from regolith import compiler
from regolith._schema.models import (
    Evidence,
    Status1,
    Status2,
    WaiveLedger,
)
from regolith.backends.parity import (
    ProvenanceClass,
    build_parity_report,
    classify_cause,
    gate_summary_line,
    render_parity_report,
)
from regolith.orchestrator.discharge import ObligationResult
from regolith.orchestrator.lockfile import Lockfile, LockRow, LockSection
from regolith.orchestrator.nogood_cache import NogoodCache
from regolith.orchestrator.optimize import (
    domains_from_choice_points,
    optimize_discrete,
    store_trace,
    winner_lock_row,
)
from regolith.orchestrator.orchestrate import staged_build
from regolith.orchestrator.payload_store import PayloadStore
from regolith.orchestrator.tiers import BuildTier

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
EBI_DECODE_SOURCE = REPO_ROOT / "examples" / "tracks" / "cuprite" / "ebi_decode.cupr"
COOLANT_GALLERY_SOURCE = (
    REPO_ROOT / "examples" / "tracks" / "hematite" / "coolant_gallery.hema"
)

_GALLERY_LOOP_FLUO = (
    "medium Water: liquid\n"
    "    props: registry(potable_water_nist)\n"
    "flownet CoolantLoop(medium=Water):\n"
    "    reference: ambient(101kPa, 293K)\n"
    "    nodes: a, b\n"
    "    edges:\n"
    "        gallery: Pipe(from=milled.wetted) (a -> b)\n"
    "require Margin:\n"
    "    dp: fluids.dp(a -> b) <= 40kPa\n"
)


# --- 1. classification unit coverage ----------------------------------


@pytest.mark.parametrize(
    ("cause", "expected"),
    [
        ("dfm(sheet.min_bend_radius)", ProvenanceClass.rule),
        ("drc(jlc_2l.current_capacity)", ProvenanceClass.rule),
        ("erc(single_driver)", ProvenanceClass.rule),
        ("budget(mesh_alignment)", ProvenanceClass.budget),
        ("planner(route wire_1)", ProvenanceClass.planner),
        ("policy(prefer low_cost)", ProvenanceClass.planner),
        ("obligation(housing.seat.stiffness)", ProvenanceClass.derived),
        ("derived(intent duty_cycle)", ProvenanceClass.derived),
        ("topology(fillet_boundary)", ProvenanceClass.derived),
        ("process(laser_cut(sheet=1.5mm))", ProvenanceClass.process),
        ("realizer(std.mech.realize)", ProvenanceClass.process),
        ("extern(vendor_step)", ProvenanceClass.process),
        ("cost_profile(cli)", ProvenanceClass.process),
        (
            "optimize(mass, trace=blake3:deadbeef)",
            ProvenanceClass.optimize,
        ),
    ],
)
def test_classify_cause_every_known_prefix(
    cause: str, expected: ProvenanceClass
) -> None:
    assert classify_cause(cause) is expected


def test_classify_cause_unrecognized_prefix_is_report_error() -> None:
    """Deliverable 4's injection test: a cause this classifier has never
    seen is loudly a REPORT ERROR, never silently bucketed."""
    assert classify_cause("mystery(nobody_knows)") is ProvenanceClass.report_error


def test_build_parity_report_surfaces_injected_report_error() -> None:
    lockfile = Lockfile(
        tool_version="0.1.0",
        sections=(
            LockSection(
                name="",
                rows=(
                    LockRow(slot="a.x", value="1mm", cause="dfm(rule)"),
                    LockRow(slot="a.y", value="2mm", cause="mystery(rule)"),
                ),
            ),
        ),
    )
    report = build_parity_report(lockfile, (), WaiveLedger(entries=[]))
    assert len(report.report_errors) == 1
    assert "mystery(rule)" in report.report_errors[0]
    assert gate_summary_line(report) == "parity: failing(1)"
    rendered = render_parity_report(report)
    assert "mystery(rule)" in rendered
    assert "report_error" in {r.provenance_class.value for r in report.rows}


# --- 2. demand table / assumed-waived over a fabricated ledger --------


def _evidence(status) -> Evidence:  # type: ignore[no-untyped-def]
    from regolith._schema.models import Coverage
    from regolith.harness.quantity import f64_to_bits

    return Evidence(
        cost=0,
        coverage=Coverage(fraction_bits=f64_to_bits(1.0), axes=[]),
        eps_bits=0,
        hash="blake3:evidence",
        margin_bits=0,
        model_id="test.model",
        status=status,
        value_bits=0,
    )


def test_demand_table_discharged_indeterminate_violated_deviation() -> None:
    discharged = ObligationResult(
        key="k.discharged",
        subject_ref="blake3:aaa",
        evidence=_evidence(Status1.discharged),
    )
    violated_target = ObligationResult(
        key="k.violated",
        subject_ref="blake3:bbb",
        evidence=_evidence(Status2.violated),
    )
    indeterminate = ObligationResult(key="k.indeterminate", subject_ref="blake3:ccc")
    deviated = ObligationResult(
        key="k.deviated",
        subject_ref="blake3:ddd",
        evidence=_evidence(Status2.violated),
    )

    from regolith._schema.models import Waiver, WaiverKind1, WaiverRecord

    ledger = WaiveLedger(
        entries=[
            {
                "waived": WaiverRecord(
                    kind=WaiverKind1.matched,
                    matched=["k.deviated"],
                    waiver=Waiver(
                        basis="vendor-confirmed capability, quote Q-2214",
                        evidence="test(first_article)",
                        target="Manufacture.makeable",
                    ),
                ).model_dump(mode="json")
            }
        ]
    )

    lockfile = Lockfile(tool_version="0.1.0", sections=())
    report = build_parity_report(
        lockfile,
        (discharged, violated_target, indeterminate, deviated),
        ledger,
    )
    statuses = {d.key: d.status.value for d in report.demands}
    assert statuses == {
        "k.discharged": "discharged",
        "k.violated": "violated",
        "k.indeterminate": "indeterminate",
        "k.deviated": "deviation",
    }
    deviated_row = next(d for d in report.demands if d.key == "k.deviated")
    assert deviated_row.basis == "vendor-confirmed capability, quote Q-2214"
    assert gate_summary_line(report) == "parity: failing(1)"  # the raw violation


def test_assume_and_bare_waive_land_in_assumed_waived_and_attention() -> None:
    from regolith._schema.models import Waiver, WaiverKind1, WaiverRecord

    ledger = WaiveLedger(
        entries=[
            {"assume": "housing.seat.stiffness: treat as true; risk accepted"},
            {
                "waived": WaiverRecord(
                    kind=WaiverKind1.matched,
                    matched=["k.bare"],
                    waiver=Waiver(
                        basis="fab-confirmed 0.1mm ring at this drill class",
                        evidence=None,
                        target="drc(min_annular_ring)",
                    ),
                ).model_dump(mode="json")
            },
        ]
    )
    lockfile = Lockfile(tool_version="0.1.0", sections=())
    report = build_parity_report(lockfile, (), ledger)
    kinds = {(a.kind, a.target) for a in report.assumed_waived}
    assert ("assume", "housing.seat.stiffness: treat as true; risk accepted") in kinds
    assert ("waived", "drc(min_annular_ring)") in kinds
    # no violated demand, no report error -> attention only (2 entries)
    assert gate_summary_line(report) == "parity: attention(2)"


# --- 3. real corpus designs --------------------------------------------


def test_coolant_gallery_realizer_cause_classifies_as_process(tmp_path) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / "coolant_gallery.hema").write_text(
        COOLANT_GALLERY_SOURCE.read_text(encoding="ascii"), encoding="ascii"
    )
    (tmp_path / "coolant_loop.fluo").write_text(_GALLERY_LOOP_FLUO, encoding="ascii")

    result = staged_build(
        (
            str(tmp_path / "coolant_gallery.hema"),
            str(tmp_path / "coolant_loop.fluo"),
        ),
        BuildTier.BUILD,
    )
    assert result.is_ok, result.danger_err
    staged_report = result.danger_ok
    assert staged_report.lock_rows, "must produce a realizer(...) lock row"

    lockfile = Lockfile(
        tool_version="0.1.0",
        sections=(LockSection(name="", rows=staged_report.lock_rows),),
    )
    payload = (
        json.loads(staged_report.final.payload_json)
        if staged_report.final.payload_json
        else {}
    )
    ledger = WaiveLedger.model_validate(payload.get("ledger", {"entries": []}))
    results = tuple(staged_report.final.results) + tuple(staged_report.final.unresolved)
    report = build_parity_report(lockfile, results, ledger)
    assert not report.report_errors, report.report_errors
    classes = {r.provenance_class for r in report.rows}
    assert ProvenanceClass.process in classes


def test_pillow_block_demand_table_has_zero_report_errors() -> None:
    """`pillow_block.hema` (a corpus flagship-precursor design, WO-63's
    own acceptance list) never realizes geometry at T2 `BUILD` without
    a supplied `FeatureProgram` (no `realizer(...)` lock row lands), so
    this proves the OTHER half of the honesty bar: every one of its
    real deferred/indeterminate obligations still renders through the
    demand table with zero report errors -- an empty lockfile is not
    the same as a broken classifier.
    """
    result = staged_build(
        (str(REPO_ROOT / "examples" / "tracks" / "hematite" / "pillow_block.hema"),),
        BuildTier.BUILD,
    )
    assert result.is_ok, result.danger_err
    staged_report = result.danger_ok
    assert staged_report.final.results or staged_report.final.unresolved

    payload = (
        json.loads(staged_report.final.payload_json)
        if staged_report.final.payload_json
        else {}
    )
    ledger = WaiveLedger.model_validate(payload.get("ledger", {"entries": []}))
    results = tuple(staged_report.final.results) + tuple(staged_report.final.unresolved)
    lockfile = Lockfile(
        tool_version="0.1.0",
        sections=(LockSection(name="", rows=staged_report.lock_rows),),
    )
    report = build_parity_report(lockfile, results, ledger)
    assert not report.report_errors, report.report_errors
    assert report.demands, "pillow_block must carry real obligations"


def test_ebi_decode_optimize_cause_classifies_as_optimize(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Stands in for duct_vane (WO-57's own exemplar, not yet landed in
    this tree, see module docstring): proves a real `optimize(...)`
    lockfile cause -- the same shape a staged-loop continuous winner
    over duct_vane's dims would carry -- classifies correctly."""
    result = compiler.check((str(EBI_DECODE_SOURCE),))
    assert result.is_ok, result
    outcome = result.danger_ok
    assert outcome.ok, "ebi_decode.cupr must check clean"
    payload = json.loads(outcome.payload_json)
    choice_points = payload["choice_points"]
    assert choice_points

    costs = {
        "decoder_board.AddressDecodeGlue": {
            "nor_glue": 2.40,
            "cpld": 1.10,
            "mcu_chip_selects": 0.0,
        }
    }
    domains, evaluator, screen, objective = domains_from_choice_points(
        choice_points, costs
    )
    trace = optimize_discrete(
        domains,
        evaluator,
        objective,
        seed=0,
        budget_evals=100,
        screen=screen,
        nogood_cache=NogoodCache(),
    )
    assert trace.winner is not None

    store = PayloadStore(str(tmp_path))
    digest = store_trace(store, trace)
    row_result = winner_lock_row(
        trace, "decoder_board.AddressDecodeGlue", "declared_objective", digest
    )
    assert row_result.is_ok, row_result
    row = row_result.danger_ok

    lockfile = Lockfile(
        tool_version="0.1.0", sections=(LockSection(name="", rows=(row,)),)
    )
    report = build_parity_report(lockfile, (), WaiveLedger(entries=[]))
    assert not report.report_errors
    assert report.decisions
    assert report.decisions[0].provenance_class is ProvenanceClass.optimize
