"""WO-48 close-out follow-up (frame-chain completion): `FramePayload`
section/material resolution against `std.civil` -> harness model
inputs. Covers the honest deferral surface (free section, unresolved
record, untargeted demand, non-member subject) and one end-to-end
discharge over a synthetic, fully-specified frame (proving the
resolution seam works when every field IS resolvable -- the actual
five-design corpus's claims stay indeterminate for reasons this suite
also demonstrates: `section: free` members -- a genuine, schema-level
gap (no declared family field to search over) -- while
`resolve_tributary_demand` (WO-65, feldspar WO-23's seam) covers the
`FramePayload.transfers` (D176/WO-62 slice B) tributary-load path that
landed after this suite's original v1-payload-gap note.)"""

from __future__ import annotations

from pathlib import Path

from regolith._schema.models import (
    Claim,
    ClaimForm1,
    Form,
    Given,
    Obligation,
    PayloadRef,
)
from regolith.harness.models.beam_service_deflection import (
    CLAIM_KIND as MECH_DEFLECTION_KIND,
)
from regolith.harness.models.beam_utilization import CLAIM_KIND as CIVIL_UTIL_KIND
from regolith.orchestrator.frame_resolve import (
    FrameContext,
    load_frame_context,
    load_frame_records,
    member_udl_demand,
    resolve_member,
    resolve_tributary_demand,
)
from regolith.orchestrator.translate import translate

_STDLIB = ("stdlib",)


def _frame_with_member(
    *,
    member_id: str = "G1",
    role: str = "beam",
    section_name: str = "sawn_150x150",
    section_digest: str = "",
    material_name: str = "astm_a992",
    length_m: float = 6.0,
    loads: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "joints": [],
        "members": [
            {
                "id": member_id,
                "role": role,
                "a": "A",
                "b": "B",
                "length": {"lo": length_m, "hi": length_m, "unit": "m"},
                "orientation": "horizontal",
                "section": {"name": section_name, "digest": section_digest},
                "material": {"name": material_name, "digest": ""},
                "releases": {"a": [], "b": []},
            }
        ],
        "supports": [],
        "transfers": [],
        "loads": loads or [],
        "combinations": {"name": "std.civil.aisc.strength", "digest": ""},
    }


def _obligation(
    name: str, rhs: str, origin: str, digest: str = "deadbeef"
) -> Obligation:
    return Obligation(
        claim=Claim(
            forall=[],
            form=ClaimForm1(form=Form.comparison, lhs=name, op="require", rhs=rhs),
            hints=[],
            name=name,
        ),
        given=Given(backing=[], loads=[], materials=[], refs=[]),
        hints=[],
        payloads=[PayloadRef(digest=digest, kind="frame", origin=origin)],
        subject_ref=digest,
    )


def test_load_frame_records_reduces_stdlib_sections_and_materials() -> None:
    """`std.civil`'s `sections.toml`/`materials.toml` load into SI-unit
    section/material property records this resolver understands."""
    loaded = load_frame_records(_STDLIB)
    assert loaded.is_ok, loaded
    records = loaded.danger_ok
    section = records.sections["sawn_150x150"]
    assert section.area_m2 is not None
    assert section.area_m2 > 0.0
    assert section.i_m4 is not None
    material = records.materials["astm_a992"]
    assert material.e_pa == 200.0e9
    assert material.fy_pa == 345.0e6


def test_resolve_member_defers_free_section() -> None:
    """A `section: free` member (an unresolved L3 search variable) defers
    `frame_section_free`, NOT a missing-record reason (D58 does not
    apply -- there is no record to be missing)."""
    records = load_frame_records(_STDLIB).danger_ok
    ctx = FrameContext(records=records, frames={}, search_paths=_STDLIB)
    frame = _frame_with_member(section_name="free", section_digest="")
    result = resolve_member(ctx, frame, "G1")
    assert result.is_err
    assert result.danger_err.reason == "frame_section_free"


def test_resolve_member_defers_unknown_section_record() -> None:
    """A section name matching no std.civil record defers
    `frame_section_unresolved` (a real content gap, unlike `free`)."""
    records = load_frame_records(_STDLIB).danger_ok
    ctx = FrameContext(records=records, frames={}, search_paths=_STDLIB)
    frame = _frame_with_member(section_name="nonexistent_section")
    result = resolve_member(ctx, frame, "G1")
    assert result.is_err
    assert result.danger_err.reason == "frame_section_unresolved"


def test_resolve_member_not_found_names_the_gap() -> None:
    """A subject naming no frame member (e.g. a derived quantity like
    `heel_sg`) defers `frame_member_not_found`, not silently matched."""
    records = load_frame_records(_STDLIB).danger_ok
    ctx = FrameContext(records=records, frames={}, search_paths=_STDLIB)
    frame = _frame_with_member()
    result = resolve_member(ctx, frame, "heel_sg")
    assert result.is_err
    assert result.danger_err.reason == "frame_member_not_found"


def test_resolve_member_succeeds_for_fixed_section_and_material() -> None:
    """A member with a real registry section/material resolves to
    positive, finite numeric properties and pins both records."""
    records = load_frame_records(_STDLIB).danger_ok
    ctx = FrameContext(records=records, frames={}, search_paths=_STDLIB)
    frame = _frame_with_member()
    result = resolve_member(ctx, frame, "G1")
    assert result.is_ok, result
    member = result.danger_ok
    assert member.area_m2 > 0.0
    assert member.i_m4 > 0.0
    assert member.e_pa > 0.0
    assert member.fy_pa > 0.0
    assert "std.civil.section.sawn_150x150" in ctx.consumed_pins
    assert "std.civil.material.astm_a992" in ctx.consumed_pins


def test_member_udl_demand_defers_when_untargeted() -> None:
    """A member with no directly-targeted literal distributed load
    defers `frame_load_untargeted` (the tributary-transfer gap the v1
    frame payload does not carry -- WO-54's own declared exclusion for
    this same payload surface)."""
    records = load_frame_records(_STDLIB).danger_ok
    ctx = FrameContext(records=records, frames={}, search_paths=_STDLIB)
    frame = _frame_with_member(loads=[])
    member = resolve_member(ctx, frame, "G1").danger_ok
    result = member_udl_demand(frame, member)
    assert result.is_err
    assert result.danger_err.reason == "frame_load_untargeted"


def _frame_with_tributary(
    *,
    trib_kind: str = "width",
    trib_unit: str = "m",
    trib_magnitude: float = 3.0,
    source_pressure_kpa: float | None = 4.0,
    length_m: float = 6.0,
) -> dict[str, object]:
    """A two-member frame: `Deck` (the tributary source, directly
    loaded) transferring to `G1` (the receiving beam) via a `Bearing`
    transfer with a declared `tributary` value -- the exact shape
    `resolve_tributary_demand` consumes."""
    source_loads: list[dict[str, object]] = []
    if source_pressure_kpa is not None:
        source_loads = [
            {
                "case": "live",
                "target": "Deck",
                "kind": "distributed",
                "value": {
                    "lo": source_pressure_kpa,
                    "hi": source_pressure_kpa,
                    "unit": "kPa",
                },
                "direction": "gravity",
            }
        ]
    return {
        "joints": [],
        "members": [
            {
                "id": "G1",
                "role": "beam",
                "a": "A",
                "b": "B",
                "length": {"lo": length_m, "hi": length_m, "unit": "m"},
                "orientation": "horizontal",
                "section": {"name": "sawn_150x150", "digest": ""},
                "material": {"name": "astm_a992", "digest": ""},
                "releases": {"a": [], "b": []},
            },
            {
                "id": "Deck",
                "role": "slab",
                "a": "A",
                "b": "B",
                "length": {"lo": length_m, "hi": length_m, "unit": "m"},
                "orientation": "horizontal",
                "section": {"name": "sawn_150x150", "digest": ""},
                "material": {"name": "astm_a992", "digest": ""},
                "releases": {"a": [], "b": []},
            },
        ],
        "supports": [],
        "transfers": [
            {
                "id": "deck_g1",
                "kind": "Bearing",
                "from": "Deck",
                "to": "G1",
                "tributary": {
                    "kind": trib_kind,
                    "value": {
                        "lo": trib_magnitude,
                        "hi": trib_magnitude,
                        "unit": trib_unit,
                    },
                },
            }
        ],
        "loads": source_loads,
        "combinations": {"name": "std.civil.aisc.strength", "digest": ""},
    }


def test_resolve_tributary_demand_width_kind_is_pressure_times_width() -> None:
    """A `tributary: {kind: width, value: <m>}` transfer reduces to
    `pressure (Pa) * width (m)`, a line load (N/m) -- no length
    involvement (the width IS the loaded strip's own dimension)."""
    records = load_frame_records(_STDLIB).danger_ok
    ctx = FrameContext(records=records, frames={}, search_paths=_STDLIB)
    frame = _frame_with_tributary(trib_kind="width", trib_magnitude=3.0)
    member = resolve_member(ctx, frame, "G1").danger_ok
    result = resolve_tributary_demand(frame, member)
    assert result.is_ok, result
    # 4.0 kPa * 3.0 m = 12000 N/m
    assert result.danger_ok == 12000.0


def test_resolve_tributary_demand_area_kind_spreads_over_member_length() -> None:
    """A `tributary: {kind: area, value: <m2>}` transfer reduces to a
    resultant force (`pressure * area`) spread over the RECEIVING
    member's own length (N/m)."""
    records = load_frame_records(_STDLIB).danger_ok
    ctx = FrameContext(records=records, frames={}, search_paths=_STDLIB)
    frame = _frame_with_tributary(
        trib_kind="area", trib_unit="m2", trib_magnitude=10.8, length_m=6.0
    )
    member = resolve_member(ctx, frame, "G1").danger_ok
    result = resolve_tributary_demand(frame, member)
    assert result.is_ok, result
    # 4.0 kPa * 10.8 m2 = 43200 N total / 6.0 m span = 7200 N/m
    assert result.danger_ok == 7200.0


def test_resolve_tributary_demand_skips_source_with_no_resolvable_load() -> None:
    """A `Bearing(tributary=...)` transfer whose SOURCE member carries
    no recognized pressure-unit load is skipped (not zero-filled,
    since "no source load" and "zero source load" are different
    facts) -- `resolve_tributary_demand` returns `Ok(0.0)`."""
    records = load_frame_records(_STDLIB).danger_ok
    ctx = FrameContext(records=records, frames={}, search_paths=_STDLIB)
    frame = _frame_with_tributary(source_pressure_kpa=None)
    member = resolve_member(ctx, frame, "G1").danger_ok
    result = resolve_tributary_demand(frame, member)
    assert result.is_ok, result
    assert result.danger_ok == 0.0


def test_member_udl_demand_resolves_via_tributary_transfer_alone() -> None:
    """A member with NO directly-targeted literal load, but a
    resolvable `Bearing(tributary=...)` transfer, now discharges
    (WO-65) instead of deferring `frame_load_untargeted`."""
    records = load_frame_records(_STDLIB).danger_ok
    ctx = FrameContext(records=records, frames={}, search_paths=_STDLIB)
    frame = _frame_with_tributary()
    member = resolve_member(ctx, frame, "G1").danger_ok
    result = member_udl_demand(frame, member)
    assert result.is_ok, result
    assert result.danger_ok == 12000.0


def test_member_udl_demand_sums_direct_line_loads() -> None:
    """A member directly targeted by literal `kN/m` load entries sums
    to a positive UDL demand."""
    records = load_frame_records(_STDLIB).danger_ok
    ctx = FrameContext(records=records, frames={}, search_paths=_STDLIB)
    frame = _frame_with_member(
        loads=[
            {
                "case": "live",
                "target": "G1",
                "kind": "distributed",
                "value": {"lo": 4.0, "hi": 4.0, "unit": "kN/m"},
                "direction": "gravity",
            }
        ]
    )
    member = resolve_member(ctx, frame, "G1").danger_ok
    result = member_udl_demand(frame, member)
    assert result.is_ok, result
    assert result.danger_ok == 4000.0


def test_translate_mech_deflection_discharges_for_a_fully_resolved_member() -> None:
    """End-to-end proof the resolution seam discharges a real numeric
    verdict when EVERY field is resolvable: a fixed section/material,
    a direct literal load, and a `<member>.span / N` bound -- the
    exact shape none of the five ratified corpus designs happen to
    exercise (every one leaves its deflection-governing member
    `section: free`)."""
    frame = _frame_with_member(
        length_m=6.0,
        loads=[
            {
                "case": "live",
                "target": "G1",
                "kind": "distributed",
                "value": {"lo": 4.0, "hi": 4.0, "unit": "kN/m"},
                "direction": "gravity",
            }
        ],
    )
    ctx_result = load_frame_context(
        ".", build_payload={"frames": {"Bridge": frame}}, record_search_paths=_STDLIB
    )
    assert ctx_result.is_ok, ctx_result
    ctx = ctx_result.danger_ok
    obligation = _obligation(
        "deflect",
        "mech.deflection(G1, under=std.civil.aisc.service) <= G1.span / 360",
        "Bridge",
    )
    lowered = translate(obligation, frame_context=ctx)
    assert lowered.is_ok, lowered
    request = lowered.danger_ok
    assert request.claim_kind == MECH_DEFLECTION_KIND
    assert request.limit > 0.0
    assert set(request.inputs) == {"w_load", "length", "e_modulus", "i_area"}


def test_translate_civil_utilization_discharges_for_a_fully_resolved_group() -> None:
    """The `<Structure>.members.all` group form discharges when its one
    member resolves in full (section+material+direct demand)."""
    frame = _frame_with_member(
        length_m=6.0,
        loads=[
            {
                "case": "live",
                "target": "G1",
                "kind": "distributed",
                "value": {"lo": 4.0, "hi": 4.0, "unit": "kN/m"},
                "direction": "gravity",
            }
        ],
    )
    # `sawn_150x150` carries an `s_mm3` field (needed for utilization,
    # unlike the `comp_deck`/`rc_wall` per-metre families).
    ctx_result = load_frame_context(
        ".", build_payload={"frames": {"Bridge": frame}}, record_search_paths=_STDLIB
    )
    ctx = ctx_result.danger_ok
    obligation = _obligation(
        "strength",
        "civil.utilization(Bridge.members.all, under=std.civil.aisc.strength) <= 1.0",
        "Bridge",
    )
    lowered = translate(obligation, frame_context=ctx)
    assert lowered.is_ok, lowered
    assert lowered.danger_ok.claim_kind == CIVIL_UTIL_KIND
    assert lowered.danger_ok.limit == 1.0


def test_translate_defers_for_no_frame_context() -> None:
    """A frame-referencing claim with no frame context configured
    defers `frame_context_unconfigured`, never silently discharges."""
    obligation = _obligation(
        "deflect",
        "mech.deflection(G1, under=std.civil.aisc.service) <= G1.span / 360",
        "Bridge",
    )
    lowered = translate(obligation, frame_context=None)
    assert lowered.is_err
    assert lowered.danger_err.reason == "frame_context_unconfigured"


def test_translate_defers_for_undischargeable_form() -> None:
    """`civil.story_drift`/`civil.bearing_pressure`/`mech.first_mode`
    each defer `no_frame_model` -- deliverable 5 covers only
    civil.utilization/mech.deflection."""
    frame = _frame_with_member()
    ctx = load_frame_context(
        ".", build_payload={"frames": {"Bridge": frame}}, record_search_paths=_STDLIB
    ).danger_ok
    obligation = _obligation("vibe", "mech.first_mode(Bridge) > 3Hz", "Bridge")
    lowered = translate(obligation, frame_context=ctx)
    assert lowered.is_err
    assert lowered.danger_err.reason == "no_frame_model"


def test_load_frame_context_is_none_without_frames(tmp_path: Path) -> None:
    """A build payload with no `frames` key skips context load entirely
    (no honest reason to load std.civil records for a frame-less build)."""
    result = load_frame_context(str(tmp_path), build_payload={}, record_search_paths=())
    assert result.is_ok
    assert result.danger_ok is None
