"""WO-164: the realizer capability registry (AD-47).

Proves the acceptance criteria: `RealizerCapability` carries all seven
fields required (no silent-default holes); a registration missing a
required field is refused with a named `IncompleteCapabilityError`
(at least two distinct fields separately proven empty); mech and elec
are both registered and their lookups carry the REAL scattered pieces
they retrofit (not just "the field exists").
"""

from __future__ import annotations

import pytest
from regolith._schema.models import FeatureProgram
from regolith.backends.capabilities import (
    CapabilityRegistry,
    IncompleteCapabilityError,
    RealizerCapability,
    ToolAdapterDescriptor,
    default_capability_registry,
    get_capability,
    register_capability,
)
from regolith.realizer.elec.kicad import LayoutRequest


def _complete_kwargs() -> dict[str, object]:
    """A fully-populated field set a test can selectively empty out."""
    return {
        "domain": "toy",
        "program_kind": FeatureProgram,
        "realized_kind": "toy.realized",
        "artifact_families": ("mech",),
        "tool_adapters": (ToolAdapterDescriptor(name="toy", tier="deterministic"),),
        "process_records": ("std.mech/records/**",),
        "dfm_checks": ("toy:check",),
        "claim_kinds": ("toy_claim",),
    }


def test_registers_a_complete_capability() -> None:
    registry = CapabilityRegistry()
    registry.register(RealizerCapability(**_complete_kwargs()))
    assert registry.domains() == ("toy",)
    assert get_capability(registry, "toy") is not None
    assert get_capability(registry, "nonexistent") is None


# frob:ticket T-0047
@pytest.mark.parametrize(
    "field",
    [
        "artifact_families",
        "tool_adapters",
        "process_records",
        "dfm_checks",
        "claim_kinds",
    ],
)
def test_refuses_capability_missing_a_tuple_field(field: str) -> None:
    kwargs = _complete_kwargs()
    kwargs[field] = ()
    registry = CapabilityRegistry()
    with pytest.raises(IncompleteCapabilityError) as exc_info:
        registry.register(RealizerCapability(**kwargs))
    assert field in exc_info.value.empty_fields
    assert exc_info.value.domain == "toy"


def test_refuses_capability_with_empty_domain() -> None:
    kwargs = _complete_kwargs()
    kwargs["domain"] = ""
    registry = CapabilityRegistry()
    with pytest.raises(IncompleteCapabilityError) as exc_info:
        registry.register(RealizerCapability(**kwargs))
    assert "domain" in exc_info.value.empty_fields


def test_refuses_capability_with_empty_realized_kind() -> None:
    kwargs = _complete_kwargs()
    kwargs["realized_kind"] = ""
    registry = CapabilityRegistry()
    with pytest.raises(IncompleteCapabilityError) as exc_info:
        registry.register(RealizerCapability(**kwargs))
    assert "realized_kind" in exc_info.value.empty_fields


def test_refuses_duplicate_domain_registration() -> None:
    registry = CapabilityRegistry()
    registry.register(RealizerCapability(**_complete_kwargs()))
    with pytest.raises(IncompleteCapabilityError) as exc_info:
        registry.register(RealizerCapability(**_complete_kwargs()))
    assert "domain: duplicate registration" in exc_info.value.empty_fields


def test_register_capability_result_wrapper_reports_err() -> None:
    registry = CapabilityRegistry()
    kwargs = _complete_kwargs()
    kwargs["dfm_checks"] = ()
    result = register_capability(registry, RealizerCapability(**kwargs))
    assert result.is_err
    assert "dfm_checks" in result.danger_err


def test_register_capability_result_wrapper_reports_ok() -> None:
    registry = CapabilityRegistry()
    result = register_capability(registry, RealizerCapability(**_complete_kwargs()))
    assert result.is_ok


def test_mech_capability_is_honestly_populated() -> None:
    registry = default_capability_registry()
    mech = get_capability(registry, "mech")
    assert mech is not None
    assert mech.program_kind is FeatureProgram
    assert mech.realized_kind == "geometry.realized"
    assert "mech" in mech.artifact_families
    assert "3d" in mech.artifact_families
    tiers = {adapter.tier for adapter in mech.tool_adapters}
    assert tiers == {"deterministic"}
    assert any("build123d" in adapter.name for adapter in mech.tool_adapters)
    assert "geometry_realizable" in mech.claim_kinds
    assert "mfg.manufacturable" in mech.claim_kinds
    assert any("check_stock_fit" in check for check in mech.dfm_checks)
    assert any("check_tool_fit" in check for check in mech.dfm_checks)
    assert any("std.mech" in rec for rec in mech.process_records)


# frob:tests python/regolith/backends/capabilities.py::get_capability kind="unit"
def test_elec_capability_is_honestly_populated() -> None:
    registry = default_capability_registry()
    elec = get_capability(registry, "elec")
    assert elec is not None
    assert elec.program_kind is LayoutRequest
    assert elec.realized_kind == "layout.realized"
    assert "boards" in elec.artifact_families
    tiers = [adapter.tier for adapter in elec.tool_adapters]
    # Real tool tried first, deterministic fallback after (AD-45 ordering).
    assert tiers == ["real_tool", "deterministic"]
    assert elec.tool_adapters[0].name == "kicad-cli"
    assert elec.claim_kinds == ("elec.layout.drc_clean",)
    assert any("std.elec" in rec for rec in elec.process_records)


# frob:tests python/regolith/backends/capabilities.py::default_capability_registry kind="unit"
# frob:ticket T-0047
def test_default_registry_has_exactly_mech_elec_perfboard_wire_edm() -> None:
    # WO-165: perfboard joins mech/elec as the first NEW capability
    # program registered through this registry (mech/elec were a
    # descriptive retrofit of pre-existing code). WO-166 adds wire_edm
    # as the second, WO-167 adds dwelling_wiring as the fourth (the
    # final owner capability target).
    registry = default_capability_registry()
    assert set(registry.domains()) == {
        "mech",
        "elec",
        "perfboard",
        "wire_edm",
        "dwelling_wiring",
    }


# frob:ticket T-0047
def test_dwelling_wiring_capability_is_honestly_populated() -> None:
    from regolith.realizer.elec.dwelling_wiring import DwellingCircuitPlan

    registry = default_capability_registry()
    cap = registry.get("dwelling_wiring")
    assert cap is not None
    assert cap.program_kind is DwellingCircuitPlan
    assert cap.realized_kind == "dwelling_wiring.realized"
    assert set(cap.artifact_families) == {"cable_schedule", "panel_schedule"}
    assert len(cap.tool_adapters) == 1
    assert cap.tool_adapters[0].tier == "deterministic"
    assert all(rec.startswith("std.process/") for rec in cap.process_records)
    assert len(cap.dfm_checks) == 3
    assert set(cap.claim_kinds) == {
        "elec.power.ampacity",
        "elec.power.voltage_drop",
        "elec.power.working_clearance",
    }


def test_wire_edm_capability_is_honestly_populated() -> None:
    from regolith.realizer.mech.wire_edm import WireEdmProfile

    registry = default_capability_registry()
    wire_edm = get_capability(registry, "wire_edm")
    assert wire_edm is not None
    assert wire_edm.program_kind is WireEdmProfile
    assert wire_edm.realized_kind == "edm_profile.realized"
    assert "edm_profile" in wire_edm.artifact_families
    assert "die_set" in wire_edm.artifact_families
    tiers = {adapter.tier for adapter in wire_edm.tool_adapters}
    assert tiers == {"deterministic"}
    assert any("check_wire_edm_corner_radius" in c for c in wire_edm.dfm_checks)
    assert "mfg.die_set_producible" in wire_edm.claim_kinds


def test_capability_model_is_frozen() -> None:
    capability = RealizerCapability(**_complete_kwargs())
    with pytest.raises(Exception):  # noqa: B017, PT011 -- pydantic ValidationError on frozen mutation
        capability.domain = "mutated"  # type: ignore[misc]
