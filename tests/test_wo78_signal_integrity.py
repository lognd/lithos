"""WO-78 end to end: the SI exemplar board's claims discharge against
the feldspar WO-25 models with the sized values in evidence, and the
ac_shunt bypass rule fires on the violating fixture while the fixed
board stays clean (charter 35 sec. 3(a)-(b)).

feldspar is the optional pack (WO-27 posture): the discharge half
skips when it is absent; the RULE half runs regardless (the rule
engine is Rust, no pack involved).
"""

from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest
from regolith import compiler
from regolith.magnetite.records_payload import registry_records_payload
from regolith.magnetite.stdlib_resolve import resolve_record_search_paths

REPO_ROOT = Path(__file__).resolve().parent.parent
_SI_BOARD = str(REPO_ROOT / "examples" / "tracks" / "cuprite" / "si_board.cupr")
_VIOLATING = str(
    REPO_ROOT / "examples" / "negative" / "72_si_ac_shunt_bypass_missing.cupr"
)
_PACKS = str(REPO_ROOT / "stdlib" / "std.board_correctness")
_STDLIB = (str(REPO_ROOT / "stdlib"),)


def _value_of(evidence) -> float:
    """Decode `Evidence.value_bits` (the AD-6 bit-exact float channel)."""
    bits = evidence.value_bits
    if isinstance(bits, float):
        return bits
    return struct.unpack("<d", struct.pack("<q", int(bits)))[0]


def _records_input() -> compiler.RealizedInput:
    payload = registry_records_payload(_STDLIB)
    assert payload is not None, "stdlib component records must serialize"
    digest, kind, subject, payload_bytes = payload
    return compiler.RealizedInput(
        digest=digest, kind=kind, subject=subject, payload_bytes=payload_bytes
    )


# ---------------------------------------------------------------------------
# The rule half (charter 35 sec. 3(b)) -- no feldspar needed.
# ---------------------------------------------------------------------------


def test_ac_shunt_bypass_rule_fires_on_the_violating_fixture() -> None:
    """The supply-pin shunt-presence rule (landed cycle 33 as
    pdn_decoupling.shunt_cap_presence -- WO-78 adds no duplicate pack,
    per 21-rule-packs D-C) fires E0601 on the bypass-less board,
    attributed to the offending pin."""
    result = compiler.check((_PACKS, _VIOLATING), realized_inputs=(_records_input(),))
    assert result.is_ok, result
    payload = json.loads(result.danger_ok.payload_json)
    firings = [
        d["message"]
        for d in payload["diagnostics"]
        if "shunt_cap_presence" in d["message"] and "violated" in d["message"]
    ]
    assert firings, payload["diagnostics"]
    assert any("u1.dvdd" in m for m in firings), firings


def test_si_board_passes_the_attached_packs_clean() -> None:
    """The fixed side: the SI exemplar attaches pdn_decoupling +
    clock_discipline and renders zero diagnostics (its residue is the
    honest realized-tier placement deferral)."""
    result = compiler.check((_PACKS, _SI_BOARD), realized_inputs=(_records_input(),))
    assert result.is_ok, result
    payload = json.loads(result.danger_ok.payload_json)
    assert payload["diagnostics"] == [], payload["diagnostics"]


# ---------------------------------------------------------------------------
# The discharge half (charter 35 sec. 3(a)-(b): sized values in
# evidence) -- feldspar-gated per the WO-27 posture.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def si_build():
    pytest.importorskip(
        "feldspar",
        reason="WO-78's SI discharge exercises feldspar's optional pack "
        "(the WO-27 skip-if-absent posture)",
    )
    from regolith.orchestrator.orchestrate import BuildTier, build

    record_paths = (
        resolve_record_search_paths(str(REPO_ROOT / "examples" / "tracks" / "cuprite"))
        or _STDLIB
    )
    result = build(
        (_SI_BOARD,),
        BuildTier.BUILD,
        si_record_paths=record_paths,
        cost_record_paths=record_paths,
    )
    assert result.is_ok, result
    report = result.danger_ok
    payload = json.loads(report.payload_json)
    names = [ob["claim"].get("name") for ob in payload["obligations"]]
    return dict(zip(names, report.results, strict=True))


def test_impedance_window_discharges_against_the_stackup_record(si_build) -> None:
    """Both window halves discharge via the Hammerstad-Jensen model;
    the computed Zo (50.17 ohm at w=0.36mm on JLC04161H-7628) is the
    evidence value -- the calculation's output IS in evidence."""
    for half, kind in (
        ("clk_z0.lo", "elec_si_microstrip_z0_lo@1"),
        ("clk_z0.hi", "elec_si_microstrip_z0_hi@1"),
    ):
        res = si_build[half]
        assert res.evidence is not None, res
        assert res.evidence.model_id == kind
        assert res.evidence.status.value == "discharged"
        assert _value_of(res.evidence) == pytest.approx(50.17, abs=0.05)


def test_stripline_window_discharges_from_explicit_kwargs(si_build) -> None:
    """The Cohn exact stripline value (60.34 ohm -- feldspar's own
    calibrated fixture geometry) discharges both halves."""
    for half in ("dram_z0.lo", "dram_z0.hi"):
        res = si_build[half]
        assert res.evidence is not None and res.evidence.status.value == "discharged"
        assert _value_of(res.evidence) == pytest.approx(60.34290501664108, rel=1e-6)


def test_termination_sizing_carries_the_sized_values(si_build) -> None:
    """Every termination scheme discharges with the cited formula's
    sized value in evidence: Rs = Z0 - Ro = 35; R1 = Z0*Vcc/Vbias =
    166.67; R2 = Z0*Vcc/(Vcc-Vbias) = 71.43; ac shunt R = Z0 = 50 and
    C = tr/(4R) = 5 pF against the only floor its +100% declared band
    can certify (charter sec. 3(b) 'with sized values')."""
    expected = {
        "clk_rs": ("elec_si_series_termination_rs@1", 35.0),
        "bus_r1": ("elec_si_thevenin_termination_r1@1", 50.0 * 5.0 / 1.5),
        "bus_r2": ("elec_si_thevenin_termination_r2@1", 50.0 * 5.0 / 3.5),
        "clk_shunt_r": ("elec_si_ac_shunt_sizing_r@1", 50.0),
        "clk_shunt_c": ("elec_si_ac_shunt_sizing_c@1", 1.0e-9 / (4.0 * 50.0)),
    }
    for name, (model_id, sized) in expected.items():
        res = si_build[name]
        assert res.evidence is not None, (name, res)
        assert res.evidence.model_id == model_id
        assert res.evidence.status.value == "discharged", (name, res.evidence)
        assert _value_of(res.evidence) == pytest.approx(sized, rel=1e-9), name


# frob:tests python/regolith/config.py::registered_keys
# frob:tests python/regolith/harness/registry.py::ModelRegistry.registered_keys
def test_claim_kinds_pin_to_the_installed_pack() -> None:
    """The claim-kind strings translate.py spells are exactly the
    installed pack's registered keys (the one-home drift check the
    translate unit suite's docstring promises)."""
    pytest.importorskip("feldspar", reason="registry pinning needs the pack")
    import importlib

    from regolith.harness.registry import default_registry

    t = importlib.import_module("regolith.orchestrator.translate")
    registered = {k[0] for k in default_registry().registered_keys()}
    spelled = (
        set(t._SI_MICROSTRIP_KINDS.values())
        | set(t._SI_STRIPLINE_KINDS.values())
        | {kind for kind, _ in t._SI_TERMINATION_ROUTES.values()}
    )
    assert spelled <= registered, spelled - registered


def test_margin_math_is_real_a_narrow_trace_violates() -> None:
    """At w=0.28mm the same stackup's Z0 is 56.1 ohm: the window's .hi
    half must come back VIOLATED, never rubber-stamped (the acceptance
    note in si_board.cupr's own header)."""
    pytest.importorskip("feldspar", reason="needs the impedance model")
    from regolith.harness import DischargeRequest, Interval
    from regolith.harness.registry import default_registry

    request = DischargeRequest(
        claim_kind="elec.si.microstrip_z0.hi",
        limit=55.0,
        inputs={
            "elec.si.microstrip.w": Interval(lo=0.00028, hi=0.00028),
            "elec.si.microstrip.h": Interval(lo=0.0002104, hi=0.0002104),
            "elec.si.microstrip.t": Interval(lo=3.5e-05, hi=3.5e-05),
            "elec.si.microstrip.er": Interval(lo=4.4, hi=4.4),
        },
    )
    evidence = default_registry().discharge(request)
    assert evidence.status.value == "violated"
