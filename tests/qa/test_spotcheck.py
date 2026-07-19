"""The D226 QA spot-check harness (WO-117 deliverable 1).

An independent re-computation of the fleet's discharged margins, the
check an engineering firm runs on its own calc book:

* every fleet project builds at its REAL release tier under the
  ``Model.discharge`` capture (``tests/qa/capture.py``), yielding each
  discharge's resolved inputs/payloads next to its evidence;
* every model family that discharges anything fleet-wide has an
  INDEPENDENTLY-WRITTEN closed-form oracle (``tests/qa/oracles/``,
  written fresh from the cited sources) that recomputes the claim's
  value from those same resolved inputs;
* the recomputed value must match the recorded one within the stated
  tolerance, and the recorded margin must equal the single margin rule
  applied to the sheet's own value/eps/limit.

A disagreement FAILS this suite and is a stop-the-line finding
(reported to the coordinator with the sample, the recomputation, and
the delta) -- never tolerance-tuned away.

Independence is enforced STRUCTURALLY: ``test_oracles_are_independent``
scans every oracle source for ``regolith.harness.models`` / ``feldspar``
imports; the oracles consume plain floats/dicts only.

The per-family outcome table is written to
``.regolith/health/qa_family_table.json`` (report artifact, not a
golden) for the WO-117 close-out.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import pytest
from regolith.magnetite.stdlib_resolve import resolve_record_search_paths
from regolith.orchestrator.orchestrate import staged_build
from regolith.orchestrator.tiers import BuildTier

from tests.qa.capture import Capture, CapturedCall, capture_discharge_calls
from tests.qa.oracles import cam, cost, dfm, mech, structural
from tests.qa.oracles import civil_fluid_elec as cfe

_REPO = Path(__file__).resolve().parents[2]
_TABLE_OUT = _REPO / ".regolith" / "health" / "qa_family_table.json"

# Relative tolerance for continuous closed forms: generous headroom
# over reordered-IEEE-double noise (~1e-14), still nine orders below
# any real modeling disagreement.
_REL_TOL = 1e-9
# Absolute floor for values near zero (exact-arithmetic families).
_ABS_TOL = 1e-9

# Every fleet-discharging model family -> (oracle, its cited source).
# An oracle taking ``inputs`` gets the captured scalar intervals; one
# taking ``payloads`` gets the captured raw payload bytes. The survey
# (WO-117 plan step 1) enumerated exactly these families; a NEW
# discharging family fails test_every_family_has_an_oracle until it is
# added here WITH an oracle.
_INPUT_ORACLES = {
    "bearing_basic_rating_life_l10h": (
        mech.bearing_l10h,
        "ISO 281:2007 sec. 6.2 (basic L10/L10h)",
    ),
    "bolted_joint_separation_vdi2230": (
        mech.bolted_joint_residual_clamp,
        "VDI 2230 joint-stiffness diagram",
    ),
    "beam_cantilever_deflection_eb": (
        mech.cantilever_tip_deflection,
        "Euler-Bernoulli cantilever, end load (delta = FL^3/3EI)",
    ),
    "beam_simple_span_deflection_udl": (
        mech.simple_span_udl_deflection,
        "simply-supported UDL midspan (delta = 5wL^4/384EI)",
    ),
    "beam_utilization_interaction": (
        mech.beam_utilization,
        "elastic beam-column interaction (AISC/NDS ASD form)",
    ),
    "mech_shaft_critical_speed": (
        mech.shaft_critical_speed_rpm,
        "Shigley 11e eq. 7-22 (n_c = (60/2pi) sqrt(k/m))",
    ),
    "footing_bearing_pressure": (
        cfe.footing_bearing_pressure,
        "bearing pressure = reaction / area (calcite/03 sec. 5)",
    ),
    "fluid_darcy_weisbach_dp": (
        cfe.darcy_weisbach_dp,
        "White, Fluid Mechanics 8th ed. sec. 6.6 (Darcy-Weisbach)",
    ),
    "thermo_lumped_steady": (
        cfe.lumped_thermal_junction_temp,
        "lumped steady state (T_j = T_amb + P*R_theta)",
    ),
    "elec_si_series_termination_rs": (
        cfe.si_series_termination_rs,
        "Johnson & Graham 1993 ch. 4 (Rs = Z0 - Ro)",
    ),
    # F152: the converter call forms made this family reachable from
    # design source (la_jig8's rail ripple claim), so it discharges
    # fleet-wide and D226 requires its own independent oracle.
    "buck_output_ripple_ccm": (
        cfe.buck_output_ripple_ccm,
        "Erickson & Maksimovic 2e sec. 2.3/ch. 4 (CCM inductor ripple "
        "+ capacitor charge, ESR neglected)",
    ),
    "workload_realization_identity": (
        structural.workload_identity,
        "cuprite/05 sec. 1 rule 3 (verbatim demand copy)",
    ),
    "conformance_refinement_upper": (
        structural.conformance_upper,
        "INV-13 refinement (impl ceiling <= spec ceiling)",
    ),
    "hdl_build": (
        structural.hdl_build_errors,
        "zero-error build identity (re-proven live by the demos leg)",
    ),
}

_PAYLOAD_ORACLES = {
    "mfg_manufacturable_mill": (
        dfm.manufacturable_excess,
        "WO-110 DFM envelope (stock/travel + tool fit containment)",
    ),
    "cam_parse_gcode_fanuc": (
        cam.parse_clean,
        "RS-274/Fanuc subset parse (fresh position tracker)",
    ),
    "cam_envelope_gcode_fanuc": (
        cam.envelope_excess,
        "commanded positions vs travel + stickout (cam charter D2)",
    ),
    "cam_collision_coarse_gcode_fanuc": (
        cam.collision_excess,
        "rapid-into-stock AABB check (cam charter D2)",
    ),
    "cam_removal_gcode_fanuc": (
        cam.removal_excess,
        "deepest-cut vs finished floor envelope (cam charter D3)",
    ),
    "cam_coverage_gcode_fanuc": (
        cam.coverage_excess,
        "feature touch-zone coverage (cam charter D2)",
    ),
    "cost_civil_takeoff": (
        lambda p: cost.cost_value(p, basis="takeoff"),
        "member-length takeoff x per-meter rate (toolchain/27 sec. 1.4)",
    ),
    "cost_elec_bom": (
        lambda p: cost.cost_value(p, basis="bom"),
        "BOM x quantity-break pricing (toolchain/27 sec. 1.4)",
    ),
}

# Families the fleet discharges through NO oracle-checkable route are a
# survey error; keep the union here for the completeness assertion.
_ALL_ORACLES = {**_INPUT_ORACLES, **_PAYLOAD_ORACLES}

_FORBIDDEN_IMPORT = re.compile(
    r"^\s*(import|from)\s+(regolith\.harness\.models|feldspar)", re.MULTILINE
)


def _fleet_projects() -> list[tuple[str, str]]:
    """Every fleet project (name, root), the fleet leg's discovery."""
    return [
        (m.parent.name, str(m.parent.relative_to(_REPO)))
        for m in sorted((_REPO / "examples").rglob("magnetite.toml"))
    ]


@pytest.fixture(scope="session")
def fleet_captures() -> dict[str, Capture]:
    """One release-tier build per fleet project, discharge-captured."""
    captures: dict[str, Capture] = {}
    for name, root in _fleet_projects():
        record_paths = resolve_record_search_paths(root)
        with capture_discharge_calls() as cap:
            built = staged_build(
                (root,),
                BuildTier.RELEASE,
                cost_record_paths=record_paths,
                frame_record_paths=record_paths,
                plan_record_paths=record_paths,
            )
        assert built.is_ok, f"{name}: staged_build failed: {built}"
        captures[name] = cap
    return captures


def _discharged_calls(captures: dict[str, Capture]) -> list[tuple[str, CapturedCall]]:
    """Every captured call that produced DISCHARGED evidence."""
    out: list[tuple[str, CapturedCall]] = []
    for project, cap in captures.items():
        out.extend((project, c) for c in cap.calls if c.status == "discharged")
    return out


def _family(model_id: str) -> str:
    """A captured model id's family key (the id sans ``@version``)."""
    return model_id.partition("@")[0]


def _close(recomputed: float, recorded: float) -> bool:
    """Tolerance compare: rel 1e-9 with a 1e-9 absolute floor."""
    return math.isclose(recomputed, recorded, rel_tol=_REL_TOL, abs_tol=_ABS_TOL)


def test_oracles_are_independent() -> None:
    """No oracle imports the model code it checks -- asserted on source."""
    oracle_dir = Path(__file__).parent / "oracles"
    for path in sorted(oracle_dir.glob("*.py")):
        text = path.read_text()
        match = _FORBIDDEN_IMPORT.search(text)
        assert match is None, (
            f"{path.name} imports the machinery under test "
            f"({match.group(0).strip()!r}) -- oracles must be written "
            "fresh from the cited source (D226)"
        )


def test_every_family_has_an_oracle(fleet_captures: dict[str, Capture]) -> None:
    """The oracle table covers EVERY fleet-discharging model family."""
    families = {_family(c.model_id) for _p, c in _discharged_calls(fleet_captures)}
    missing = sorted(f for f in families if f not in _ALL_ORACLES)
    assert not missing, (
        f"model families discharge fleet-wide with no D226 oracle: {missing}"
    )


def test_spotcheck_all_families(fleet_captures: dict[str, Capture]) -> None:
    """Recompute every sampled discharged value + margin; fail on delta.

    Every discharged call of every family is recomputed (a full sweep,
    not a subsample -- the fleet is small enough to check exhaustively),
    and the per-family outcome table is written for the close-out.
    """
    table: dict[str, dict] = {}
    failures: list[str] = []
    for project, call in _discharged_calls(fleet_captures):
        family = _family(call.model_id)
        entry = _ALL_ORACLES.get(family)
        if entry is None:  # covered by test_every_family_has_an_oracle
            continue
        oracle, source = entry
        if family in _PAYLOAD_ORACLES:
            # `oracle` is one of a heterogeneous union of callables (each
            # family's own oracle signature); the `family in
            # _PAYLOAD_ORACLES` runtime check picks the right arm, but ty
            # cannot narrow a dict-membership test to a callable union
            # member -- a genuine limitation on this dynamic-dispatch
            # test idiom, not a real type error (D226 oracle table).
            recomputed = oracle(call.payloads)  # ty: ignore[invalid-argument-type]
        else:
            recomputed = oracle(call.inputs)  # ty: ignore[invalid-argument-type]
        assert call.value is not None and call.eps is not None
        assert call.margin is not None
        remargin = structural.margin(
            call.value, call.eps, call.limit, upper=call.sense_upper
        )
        value_ok = _close(recomputed, call.value)
        margin_ok = _close(remargin, call.margin)
        row = table.setdefault(
            family,
            {
                "oracle_source": source,
                "samples": 0,
                "max_value_delta": 0.0,
                "max_margin_delta": 0.0,
                "tolerance": f"rel {_REL_TOL:g} / abs {_ABS_TOL:g}",
            },
        )
        row["samples"] += 1
        row["max_value_delta"] = max(
            row["max_value_delta"], abs(recomputed - call.value)
        )
        row["max_margin_delta"] = max(
            row["max_margin_delta"], abs(remargin - call.margin)
        )
        if not value_ok:
            failures.append(
                f"{project}/{family} ({call.claim_kind}): recomputed value "
                f"{recomputed!r} vs recorded {call.value!r} "
                f"(delta {abs(recomputed - call.value):g})"
            )
        if not margin_ok:
            failures.append(
                f"{project}/{family} ({call.claim_kind}): margin rule gives "
                f"{remargin!r} vs recorded {call.margin!r}"
            )

    _TABLE_OUT.parent.mkdir(parents=True, exist_ok=True)
    _TABLE_OUT.write_text(json.dumps(table, indent=2, sort_keys=True) + "\n")

    assert not failures, (
        "D226 STOP-THE-LINE: independent recomputation disagrees with the "
        "recorded evidence (report to the coordinator; never tune the "
        "tolerance):\n" + "\n".join(failures)
    )
    assert table, "the spot check sampled nothing -- the capture is broken"


def test_committed_calc_books_carry_only_discharged_sheets() -> None:
    """Every committed calc-book golden sheet's verdict is `discharged`.

    Structural since the WO117-F1 fix (only model-backed resolves get
    sheets); asserted here so a calc.py regression re-reds THIS suite.
    """
    for golden in sorted((_REPO / "tests" / "golden" / "data").glob("calc_book_*")):
        book = json.loads(golden.read_text())
        bad = [s["sheet_id"] for s in book["sheets"] if s["verdict"] != "discharged"]
        assert not bad, f"{golden.name}: non-discharged verdict on sheets {bad}"
