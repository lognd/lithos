"""WO-78 deliverable 2: SI claim translation units (charter 35 sec.
1.2-1.3).

Pure `translate()` behavior over synthetic obligations -- the feldspar
pack is NOT required here (translation routes by claim-kind string;
discharge itself is the e2e suite `tests/test_wo78_signal_integrity.py`,
which carries the WO-27 skip-if-absent posture). What this suite pins:

- the impedance window halves route to the microstrip/stripline
  `.lo`/`.hi` claim kinds with the stackup record resolving h/er/t
  (record-first, charter sec. 1.2);
- every termination scheme routes to its exposed sizing model's kind
  with the call kwargs as the model ports;
- every named honest deferral (unknown stackup, non-outer layer,
  stackup-derived stripline, differential pairs, scheme=parallel,
  missing inputs) defers with its recorded reason, never a guess.
"""

from __future__ import annotations

from pathlib import Path

from regolith._schema.models import ClaimForm1, Obligation
from regolith.orchestrator.si_stackups import SiContext, load_si_context
from regolith.orchestrator.translate import translate

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _si_context() -> SiContext:
    result = load_si_context(
        str(REPO_ROOT), record_search_paths=(str(REPO_ROOT / "stdlib"),)
    )
    assert result.is_ok, result
    return result.danger_ok


def _obligation(name: str, lhs: str, op: str, rhs: str) -> Obligation:
    return Obligation.model_validate(
        {
            "claim": {
                "name": name,
                "form": {"form": "comparison", "lhs": lhs, "op": op, "rhs": rhs},
                "forall": [],
                "hints": [],
            },
            "subject_ref": "test-subject",
            "given": {"materials": [], "loads": [], "backing": [], "refs": []},
            "hints": [],
        }
    )


_MICROSTRIP_CALL = (
    "elec.impedance(clk, role=microstrip, stackup=jlc04161h_7628, "
    "layer=outer, w=0.00036)"
)


def test_stackup_records_load_and_cite() -> None:
    """Deliverable 1's loader: >= 6 records across the 2/4/6-layer
    classes, every one carrying its fab citation."""
    ctx = _si_context()
    assert len(ctx.stackups) >= 6
    layer_counts = {r.layer_count for r in ctx.stackups.values()}
    assert {2, 4, 6} <= layer_counts
    for record in ctx.stackups.values():
        assert "jlcpcb.com/impedance" in record.reference, record


def test_microstrip_window_halves_route_with_record_geometry() -> None:
    """The `.lo`/`.hi` halves route to the feldspar microstrip pair;
    h/er/t come from the named record (7628: 0.2104mm / 4.4 / 0.035mm),
    w from the claim."""
    ctx = _si_context()
    for suffix, op, rhs, kind in (
        ("lo", ">=", "45", "elec.si.microstrip_z0.lo"),
        ("hi", "<=", "55", "elec.si.microstrip_z0.hi"),
    ):
        ob = _obligation(f"clk_z0.{suffix}", _MICROSTRIP_CALL, op, rhs)
        result = translate(ob, si_context=ctx)
        assert result.is_ok, result
        request = result.danger_ok
        assert request.claim_kind == kind
        assert request.inputs["elec.si.microstrip.w"].lo == 0.00036
        assert request.inputs["elec.si.microstrip.h"].lo == 0.0002104
        assert request.inputs["elec.si.microstrip.er"].lo == 4.4
        # 0.035mm / 1000 in floats: compare with a relative tolerance.
        assert abs(request.inputs["elec.si.microstrip.t"].lo - 3.5e-05) < 1e-18
        assert request.limit == float(rhs)


def test_stripline_routes_from_explicit_kwargs() -> None:
    ob = _obligation(
        "dram_z0.lo",
        "elec.impedance(dram_dq, role=stripline, w=0.000382, b=0.001, er=3.66)",
        ">=",
        "55",
    )
    result = translate(ob, si_context=_si_context())
    assert result.is_ok, result
    request = result.danger_ok
    assert request.claim_kind == "elec.si.stripline_z0.lo"
    assert request.inputs["elec.si.stripline.b"].lo == 0.001


def test_named_deferrals_are_honest() -> None:
    """Every recorded residual defers with its named reason."""
    ctx = _si_context()
    cases = (
        # feldspar's diff_pair_z named cut.
        (
            "z.lo",
            "elec.impedance(pair, role=diff, w=0.0002)",
            ">=",
            "80",
            "si_differential_unexposed",
        ),
        # Unknown stackup key: nothing resolved, never guessed.
        (
            "z.lo",
            "elec.impedance(clk, role=microstrip, stackup=nope, w=0.0003)",
            ">=",
            "45",
            "si_stackup_unknown",
        ),
        # Non-outer microstrip layer: no published role table.
        (
            "z.lo",
            "elec.impedance(clk, role=microstrip, stackup=jlc04161h_7628, "
            "layer=in1, w=0.0003)",
            ">=",
            "45",
            "si_layer_unsupported",
        ),
        # Stackup-derived stripline: the recorded residual.
        (
            "z.lo",
            "elec.impedance(dq, role=stripline, stackup=jlc04161h_7628, w=0.0003)",
            ">=",
            "55",
            "si_stripline_stackup_underivable",
        ),
        # Missing geometry entirely.
        (
            "z.lo",
            "elec.impedance(clk, role=microstrip)",
            ">=",
            "45",
            "si_inputs_missing",
        ),
        # scheme=parallel: no exposed sizing model.
        (
            "t",
            "elec.termination(clk, scheme=parallel, z0=50)",
            ">=",
            "50",
            "si_scheme_unexposed",
        ),
        # Termination with no scheme.
        ("t", "elec.termination(clk, z0=50)", ">=", "50", "si_scheme_missing"),
        # Termination missing its scheme's inputs.
        (
            "t",
            "elec.termination(clk, scheme=series, z0=50)",
            ">=",
            "34",
            "si_inputs_missing",
        ),
    )
    for name, lhs, op, rhs, reason in cases:
        result = translate(_obligation(name, lhs, op, rhs), si_context=ctx)
        assert result.is_err, (lhs, result)
        assert result.danger_err.reason == reason, (lhs, result.danger_err)


def test_termination_schemes_route_to_their_models() -> None:
    ctx = _si_context()
    cases = (
        (
            "elec.termination(clk, scheme=series, z0=50, ro=15)",
            "elec.si.series_termination.rs",
            {"elec.si.series_termination.z0": 50.0},
        ),
        (
            "elec.termination(bus, scheme=thevenin, leg=r1, z0=50, vcc=5, vbias=1.5)",
            "elec.si.thevenin_termination.r1",
            {"elec.si.thevenin_termination.vbias": 1.5},
        ),
        (
            "elec.termination(bus, scheme=thevenin, leg=r2, z0=50, vcc=5, vbias=1.5)",
            "elec.si.thevenin_termination.r2",
            {"elec.si.thevenin_termination.vcc": 5.0},
        ),
        (
            "elec.termination(clk, scheme=ac_shunt, part=r, z0=50)",
            "elec.si.ac_shunt.r",
            {"elec.si.ac_shunt.z0": 50.0},
        ),
        (
            "elec.termination(clk, scheme=ac_shunt, part=c, "
            "rise_time=0.000000001, r=50)",
            "elec.si.ac_shunt.c",
            {"elec.si.ac_shunt.rise_time": 1e-9},
        ),
    )
    for lhs, kind, spot in cases:
        result = translate(_obligation("t", lhs, ">=", "1"), si_context=ctx)
        assert result.is_ok, (lhs, result)
        request = result.danger_ok
        assert request.claim_kind == kind
        for port, value in spot.items():
            assert request.inputs[port].lo == value


def test_form_is_claimform1() -> None:
    """Guard: the synthetic obligations above really are the ClaimForm1
    shape the real lowering emits (a schema drift here would silently
    hollow out this whole suite)."""
    ob = _obligation(
        "t", "elec.termination(clk, scheme=series, z0=50, ro=15)", ">=", "34"
    )
    assert isinstance(ob.claim.form, ClaimForm1)
