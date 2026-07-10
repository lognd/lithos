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
    FrameClaimBounds,
    FrameContext,
    declared_embedment_m,
    load_frame_context,
    load_frame_records,
    member_demand,
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
    section_domain: str | None = None,
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
                "section_domain": section_domain,
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


def test_resolve_member_defers_free_section_with_declared_domain_and_no_demand() -> (
    None
):
    """WO-65: a `section: in registry(<family>)` member (a DECLARED
    family, `FrameMember.section_domain` populated) now runs a real
    section search (:func:`search_free_section`) instead of the old
    blanket `frame_section_domain_unsearched` placeholder -- but the
    search still needs a resolvable demand first; a member with no
    load at all defers `frame_load_untargeted`, the SAME specific
    reason a fixed-section member with no load would carry."""
    records = load_frame_records(_STDLIB).danger_ok
    ctx = FrameContext(records=records, frames={}, search_paths=_STDLIB)
    frame = _frame_with_member(
        section_name="free", section_digest="", section_domain="std.civil.w_shape"
    )
    result = resolve_member(ctx, frame, "G1")
    assert result.is_err
    assert result.danger_err.reason == "frame_load_untargeted"


def _udl(target: str = "G1", kn_per_m: float = 1.0) -> list[dict[str, object]]:
    """One literal, directly-targeted distributed load entry."""
    return [
        {
            "case": "live",
            "target": target,
            "kind": "distributed",
            "value": {"lo": kn_per_m, "hi": kn_per_m, "unit": "kN/m"},
            "direction": "gravity",
        }
    ]


def _search_ctx(
    *,
    frames: dict[str, dict] | None = None,
    claim_bounds: FrameClaimBounds | None = None,
) -> FrameContext:
    """A stdlib-backed context with optional declared claim bounds."""
    records = load_frame_records(_STDLIB).danger_ok
    return FrameContext(
        records=records,
        frames=frames or {},
        search_paths=_STDLIB,
        claim_bounds=claim_bounds,
    )


def test_resolve_member_searches_and_picks_lightest_feasible_section() -> None:
    """WO-65: given a resolvable demand and a declared utilization
    limit, the search picks the LIGHTEST (mass-per-length-ascending)
    w_shape candidate that clears the limit under the SAME value+eps
    margin rule discharge applies, and pins the canonical
    `optimize(mass_per_length, trace=<digest>)` cause + winner row."""
    frame = _frame_with_member(
        section_name="free",
        section_digest="",
        section_domain="std.civil.w_shape",
        length_m=4.0,
        loads=_udl(),
    )
    ctx = _search_ctx(
        frames={"Bridge": frame},
        claim_bounds=FrameClaimBounds(utilization_limit_all={"Bridge": 1.0}),
    )
    result = resolve_member(ctx, frame, "G1")
    assert result.is_ok, result
    member = result.danger_ok
    assert member.area_m2 > 0.0
    assert member.s_m3 is not None and member.s_m3 > 0.0
    # moment = 1000 N/m * 4.0m^2 / 8 = 2000 N*m; the lightest w_shape
    # (w8x10, s_in3=7.8 -> s_m3~1.278e-4) clears 2000/(1.278e-4*3.45e8)
    # ~= 0.045 utilization (x1.08 eps still ~0.049), so it wins
    # (declaration order IS mass-ascending for this family, WO-60's
    # own listing).
    assert member.section_key == "w8x10"
    assert member.search_cause is not None
    assert member.search_cause.startswith("optimize(mass_per_length, trace=blake3:")
    row = ctx.winner_rows["Bridge.G1.section"]
    assert row.value == "G1=w8x10"
    assert row.cause == member.search_cause
    assert ctx.consumed_pins["std.civil.section.w8x10"]


def test_search_gates_on_declared_deflection_claim() -> None:
    """WO-65 (the dispatch's own live repro): a member whose deflection
    claim (`span/360`) the lightest strength-feasible shape FAILS must
    NOT win with that shape -- feasibility is ALL declared demands
    (AD-30), evaluated discharge-coherently (value + eps <= limit).
    Footbridge's real numbers: 12m span, 3.69kN/m tributary demand --
    w8x31 clears strength but deflects 0.109m >> 0.033m; the lightest
    candidate clearing BOTH is w16x40 (I=519in4, area 11.8in2)."""
    frame = _frame_with_member(
        section_name="free",
        section_digest="",
        section_domain="std.civil.w_shape",
        length_m=12.0,
        loads=_udl(kn_per_m=3.69),
    )
    ctx = _search_ctx(
        frames={"Bridge": frame},
        claim_bounds=FrameClaimBounds(
            utilization_limit_all={"Bridge": 1.0},
            deflection_divisors={("Bridge", "G1"): 360.0},
        ),
    )
    result = resolve_member(ctx, frame, "G1")
    assert result.is_ok, result
    assert result.danger_ok.section_key == "w16x40"


def test_search_feasibility_is_discharge_coherent_on_eps_margin() -> None:
    """A candidate whose RAW utilization fits the limit but whose
    value+eps (the beam model's 8 percent conservatism, the exact
    margin rule `harness/evidence.py` discharges with) does NOT is
    infeasible -- the search can never pin a winner discharge would
    then reject. Load tuned so w8x10 lands between 1/1.08 and 1.0:
    moment = 41kN*m -> util ~0.930, x1.08 ~1.004 > 1.0 -> w8x31 wins."""
    frame = _frame_with_member(
        section_name="free",
        section_digest="",
        section_domain="std.civil.w_shape",
        length_m=4.0,
        loads=_udl(kn_per_m=20.5),
    )
    ctx = _search_ctx(
        frames={"Bridge": frame},
        claim_bounds=FrameClaimBounds(utilization_limit_all={"Bridge": 1.0}),
    )
    result = resolve_member(ctx, frame, "G1")
    assert result.is_ok, result
    assert result.danger_ok.section_key == "w8x31"


def test_search_defers_infeasible_when_no_candidate_clears_the_bounds() -> None:
    """No candidate in the family clearing the declared bound(s) defers
    `frame_section_search_infeasible`, naming the gates."""
    frame = _frame_with_member(
        section_name="free",
        section_digest="",
        section_domain="std.civil.timber_sawn",
        material_name="spf_no1",
        length_m=12.0,
        loads=_udl(kn_per_m=50.0),
    )
    ctx = _search_ctx(
        frames={"Barn": frame},
        claim_bounds=FrameClaimBounds(utilization_limit_all={"Barn": 1.0}),
    )
    result = resolve_member(ctx, frame, "G1")
    assert result.is_err
    assert result.danger_err.reason == "frame_section_search_infeasible"
    assert "utilization<=1.0" in result.danger_err.detail


def test_search_with_no_declared_bounds_picks_by_objective_alone() -> None:
    """A member no checkable claim covers gates on nothing: the
    disclosed mass-per-length objective alone picks (feasibility means
    the design's DECLARED demands, never an invented house rule)."""
    frame = _frame_with_member(
        section_name="free",
        section_digest="",
        section_domain="std.civil.w_shape",
        length_m=4.0,
        loads=_udl(),
    )
    ctx = _search_ctx(frames={"Bridge": frame})
    result = resolve_member(ctx, frame, "G1")
    assert result.is_ok, result
    assert result.danger_ok.section_key == "w8x10"


def test_resolve_member_defers_capacity_unresolved_for_unlanded_family() -> None:
    """A declared family with no std.civil section rows at all defers
    `frame_section_family_not_landed`, not a blanket catch-all."""
    records = load_frame_records(_STDLIB).danger_ok
    ctx = FrameContext(records=records, frames={}, search_paths=_STDLIB)
    frame = _frame_with_member(
        section_name="free",
        section_digest="",
        section_domain="std.civil.no_such_family",
        loads=[
            {
                "case": "live",
                "target": "G1",
                "kind": "distributed",
                "value": {"lo": 1.0, "hi": 1.0, "unit": "kN/m"},
                "direction": "gravity",
            }
        ],
    )
    result = resolve_member(ctx, frame, "G1")
    assert result.is_err
    assert result.danger_err.reason == "frame_section_family_not_landed"


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
    trib_unit: str = "m",
    trib_magnitude: float = 3.0,
    source_pressure_kpa: float | None = 4.0,
    length_m: float = 6.0,
) -> dict[str, object]:
    """A two-member frame: `Deck` (the tributary source, directly
    loaded) transferring to `G1` (the receiving beam) via a `Bearing`
    transfer with a declared `tributary` value -- the exact shape
    `resolve_tributary_demand` consumes: `FrameTransfer.tributary`
    (`crates/regolith-oblig/src/frame.rs`) is a FLAT `ScalarInterval`
    (`{lo, hi, unit}`), no `kind`/`value` wrapper (WO-65 bugfix; `kind`
    -- "width" vs "area" -- is inferred from `unit` itself, `m` vs
    `m2`)."""
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
                    "lo": trib_magnitude,
                    "hi": trib_magnitude,
                    "unit": trib_unit,
                },
            }
        ],
        "loads": source_loads,
        "combinations": {"name": "std.civil.aisc.strength", "digest": ""},
    }


def test_resolve_tributary_demand_width_kind_is_pressure_times_width() -> None:
    """A `tributary: <m>` (unit `m`, inferred "width") transfer reduces
    to `pressure (Pa) * width (m)`, a line load (N/m) -- no length
    involvement (the width IS the loaded strip's own dimension)."""
    records = load_frame_records(_STDLIB).danger_ok
    ctx = FrameContext(records=records, frames={}, search_paths=_STDLIB)
    frame = _frame_with_tributary(trib_unit="m", trib_magnitude=3.0)
    member = resolve_member(ctx, frame, "G1").danger_ok
    result = resolve_tributary_demand(frame, member)
    assert result.is_ok, result
    # 4.0 kPa * 3.0 m = 12000 N/m
    assert result.danger_ok == 12000.0


def test_resolve_tributary_demand_area_kind_spreads_over_member_length() -> None:
    """A `tributary: <m2>` (unit `m2`, inferred "area") transfer
    reduces to a resultant force (`pressure * area`) spread over the
    RECEIVING member's own length (N/m)."""
    records = load_frame_records(_STDLIB).danger_ok
    ctx = FrameContext(records=records, frames={}, search_paths=_STDLIB)
    frame = _frame_with_tributary(trib_unit="m2", trib_magnitude=10.8, length_m=6.0)
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


def test_member_demand_includes_stationed_point_loads() -> None:
    """WO-85/D194: a stationed point load (`on [G1@0.5]`, SCHEMA 27's
    `station` field) enters the demand surface; the midspan moment is
    `P*L*f*(1-f)` and the deflection-equivalent UDL reproduces the
    exact simple-span point-load maximum through the landed
    `5wL^4/384EI` model."""
    records = load_frame_records(_STDLIB).danger_ok
    ctx = FrameContext(records=records, frames={}, search_paths=_STDLIB)
    frame = _frame_with_member(
        loads=[
            {
                "case": "hoist",
                "target": "G1",
                "kind": "point",
                "station": 0.5,
                "value": {"lo": 2.0, "hi": 2.0, "unit": "kN"},
                "direction": "gravity",
            }
        ]
    )
    member = resolve_member(ctx, frame, "G1").danger_ok
    result = member_demand(frame, member)
    assert result.is_ok, result
    demand = result.danger_ok
    assert demand.point_loads == ((2000.0, 0.5),)
    length = member.length_m
    # M = P*L*f*(1-f) = P*L/4 at midspan.
    assert abs(demand.moment_nm(length) - 2000.0 * length / 4.0) < 1e-9
    # Equivalent UDL for a midspan point load: matching PL^3/48EI to
    # 5wL^4/384EI gives w = 8P/(5L).
    expected_w = 8.0 * 2000.0 / (5.0 * length)
    assert abs(demand.deflection_w_equiv(length) - expected_w) < 1e-6


def test_member_demand_endpoint_point_load_bends_nothing() -> None:
    """A point load at station 0 or 1 sits on the support: zero moment
    and zero deflection contribution (its share rides the axial path)."""
    records = load_frame_records(_STDLIB).danger_ok
    ctx = FrameContext(records=records, frames={}, search_paths=_STDLIB)
    frame = _frame_with_member(
        loads=[
            {
                "case": "post",
                "target": "G1",
                "kind": "point",
                "station": 0.0,
                "value": {"lo": 5.0, "hi": 5.0, "unit": "kN"},
                "direction": "gravity",
            }
        ]
    )
    member = resolve_member(ctx, frame, "G1").danger_ok
    demand = member_demand(frame, member).danger_ok
    assert demand.moment_nm(member.length_m) == 0.0
    assert demand.deflection_w_equiv(member.length_m) == 0.0
    # ... but it still counts toward the member's total gravity load.
    assert demand.total_gravity_n(member.length_m) == 5000.0


def _column_frame(*, n_posts: int = 2) -> dict[str, object]:
    """A beam-onto-columns frame (the pavilion shape): G1 carries a
    direct line load and delivers its end reactions into `n_posts`
    column members via `Pinned` transfers."""
    posts = [f"P{i}" for i in range(1, n_posts + 1)]
    member_dicts = [
        {
            "id": name,
            "role": "column",
            "a": "A",
            "b": "B",
            "length": {"lo": 3.0, "hi": 3.0, "unit": "m"},
            "orientation": "vertical",
            "section": {"name": "sawn_150x150", "digest": ""},
            "material": {"name": "astm_a992", "digest": ""},
            "releases": {"a": [], "b": []},
        }
        for name in posts
    ]
    member_dicts.append(
        {
            "id": "G1",
            "role": "beam",
            "a": "A",
            "b": "B",
            "length": {"lo": 6.0, "hi": 6.0, "unit": "m"},
            "orientation": "horizontal",
            "section": {"name": "sawn_150x150", "digest": ""},
            "material": {"name": "astm_a992", "digest": ""},
            "releases": {"a": [], "b": []},
        }
    )
    return {
        "joints": [],
        "members": member_dicts,
        "supports": [],
        "transfers": [
            {"id": f"g1_{p.lower()}", "kind": "Pinned", "from": "G1", "to": p}
            for p in posts
        ],
        "loads": [
            {
                "case": "live",
                "target": "G1",
                "kind": "line",
                "value": {"lo": 4.0, "hi": 4.0, "unit": "kN/m"},
                "direction": "gravity",
            }
        ],
        "combinations": {"name": "std.civil.aisc.strength", "digest": ""},
    }


def test_member_demand_resolves_column_axial_from_gravity_path() -> None:
    """WO-85 deliverable 3 (the "axial pinned at 0" wall dies): a
    column receiving a `Pinned` transfer from a line-loaded beam with
    two end reactions resolves `W/2` axial demand -- and no longer
    defers `frame_load_untargeted` despite carrying no load of its
    own."""
    records = load_frame_records(_STDLIB).danger_ok
    ctx = FrameContext(records=records, frames={}, search_paths=_STDLIB)
    frame = _column_frame(n_posts=2)
    member = resolve_member(ctx, frame, "P1").danger_ok
    result = member_demand(frame, member)
    assert result.is_ok, result
    demand = result.danger_ok
    # W = 4 kN/m * 6 m = 24 kN, split across two end reactions.
    assert demand.axial_n == 12000.0
    assert demand.w_n_per_m == 0.0
    # The UDL-only surface still (honestly) has nothing for a column.
    udl = member_udl_demand(frame, member)
    assert udl.is_err
    assert udl.danger_err.reason == "frame_load_untargeted"


def test_member_demand_axial_skips_indeterminate_multi_support_source() -> None:
    """A source beam with 3+ reaction transfers is statically
    indeterminate for the closed-form equal split -- the path is
    skipped (logged), and a column with no other demand source defers
    honestly rather than receiving a guessed share."""
    records = load_frame_records(_STDLIB).danger_ok
    ctx = FrameContext(records=records, frames={}, search_paths=_STDLIB)
    frame = _column_frame(n_posts=3)
    member = resolve_member(ctx, frame, "P1").danger_ok
    result = member_demand(frame, member)
    assert result.is_err
    assert result.danger_err.reason == "frame_load_untargeted"


def test_declared_embedment_reads_the_transfer_depth() -> None:
    """WO-85/D194: `EmbeddedPost(depth=1.4m)` -> 1.4 (metres); a frame
    with no depth-carrying transfer resolves `None`."""
    frame = _column_frame(n_posts=2)
    transfers = frame["transfers"]
    assert isinstance(transfers, list)
    transfers.append(
        {
            "id": "p1_e1",
            "kind": "EmbeddedPost",
            "from": "P1",
            "to": "E1",
            "depth": {"lo": 1.4, "hi": 1.4, "unit": "m"},
        }
    )
    assert declared_embedment_m(frame, "P1") == 1.4
    assert declared_embedment_m(frame, "P2") is None


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


def test_footbridge_deflect_flips_to_a_real_discharged_verdict() -> None:
    """WO-65 end to end over the REAL corpus design (the WO-56 flagship
    acceptance's calcite half): `orchestrate.build` at T1 over
    footbridge.calx searches G1's declared `std.civil.w_shape` family,
    the winner (w16x40 -- the lightest candidate clearing BOTH the
    strength limit AND the L/360 deflection bound; the deflect claim
    gates the search, so lighter strength-only shapes lose) discharges
    the `deflect` obligation with a REAL harness verdict, its trace is
    persisted, and the winner row + std.civil pins ride the report
    (INV-21/INV-22)."""
    from regolith.orchestrator.orchestrate import build
    from regolith.orchestrator.tiers import BuildTier

    report = build(
        ("examples/tracks/calcite/footbridge.calx",),
        BuildTier.BUILD,
        frame_record_paths=_STDLIB,
    ).danger_ok
    assert report.ok
    discharged = [
        r for r in report.results if r.evidence is not None and r.deferral is None
    ]
    assert any(
        r.evidence.model_id.startswith("beam_simple_span_deflection_udl")
        and r.evidence.status.value == "discharged"
        for r in discharged
    ), report.results
    # WO-85/D194: the `.members.all` strength aggregate expands per
    # member at lowering, so G2's strength[G2] obligation now runs ITS
    # OWN search too (strength-only -- no deflect bound names G2 -- so
    # a lighter shape than G1's deflection-governed w16x40 wins). Two
    # winner rows, one per searched member; before the expansion the
    # aggregate deferred wholesale on the first unresolved member and
    # only G1's own deflect claim triggered a search.
    rows = {row.slot: row for row in report.frame_lock_rows}
    assert set(rows) == {"Bridge.G1.section", "Bridge.G2.section"}, rows
    g1_row = rows["Bridge.G1.section"]
    assert g1_row.value == "G1=w16x40"
    assert g1_row.cause.startswith("optimize(mass_per_length, trace=blake3:")
    pin_keys = {key for key, _ in report.frame_record_pins}
    assert "std.civil.section.w16x40@1" in pin_keys
    assert "std.civil.material.astm_a992@1" in pin_keys


def test_small_office_frame_members_have_nonzero_length_at_build_tier() -> None:
    """CI-shaped tripwire for the split-file grid/level aggregation fix
    (frame_lower.rs `GridIndex`/`LevelIndex::build_all`): small_office's
    `frame.calx` anchors its members against `grid`/`level` datums
    declared in the SEPARATE `site.calx` file (calcite/02 sec. 1). Before
    the fix, `frame_lower` built its grid/level position table per file,
    so `frame.calx` (which declares no grid/level of its own) resolved
    every anchor component to `None` and every member's `length`
    silently collapsed to `[0, 0] m` -- a check-tier golden with
    `evidence_count=0` never caught it (`deflect2` deferred as
    `frame_load_untargeted` instead of a real numeric verdict). This
    test runs the REAL `orchestrate.build` pipeline (not just
    `frame_lower` in isolation) so a future regression anywhere in the
    chain trips it, not only a `regolith-lower` unit test."""
    import json

    from regolith.orchestrator.orchestrate import build
    from regolith.orchestrator.tiers import BuildTier

    report = build(
        ("examples/flagships/small_office",),
        BuildTier.BUILD,
        frame_record_paths=_STDLIB,
    ).danger_ok
    assert report.ok
    payload = json.loads(report.payload_json)
    frames = payload.get("frames", {})
    assert frames, "small_office build produced no frames payload"
    members = [m for frame in frames.values() for m in frame["members"]]
    assert members, "small_office frame has no members"
    zero_length = [m["id"] for m in members if m["length"]["lo"] == 0.0]
    assert not zero_length, (
        "members with zero length (cross-file grid/level datums not "
        f"reaching the position table): {zero_length}"
    )
