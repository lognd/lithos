"""Unit tests for `regolith.backends.instructions` (WO-96, D199.1): the
`AssemblySteps` producer's deterministic fixed-then-placed ordering,
the honest `unordered_parts` callout for an underconstrained part, the
fastener callout appearing ONLY with discharged bolted-joint evidence,
the D197 stamp applied through the model, and the rendered document's
"no invented literal" honesty.
"""

from __future__ import annotations

from regolith._schema.models import AssemblyPart, MateEdge, RealizedAssembly
from regolith.backends.instructions import (
    files_for_steps,
    render_document,
    stamp_steps,
    steps_for_assembly,
)
from regolith.harness import DischargeRequest, Interval, default_registry
from regolith.harness.models.bolted_joint import CLAIM_KIND as _BOLT_CLAIM_KIND


def _part(part_id: str) -> AssemblyPart:
    return AssemblyPart(
        id=part_id,
        geometry_digest=f"blake3:{part_id}",
        transform={"translation_m": [0.0, 0.0, 0.0], "rotation_deg": [0.0, 0.0, 0.0]},
    )


def _assembly(
    dof_states: dict[str, str], mates: list[MateEdge] | None = None
) -> RealizedAssembly:
    return RealizedAssembly(
        com_m=[0.0, 0.0, 0.0],
        dof_states=dof_states,
        interferences=[],
        mass_kg=1.0,
        mating_graph_hash="blake3:test_assembly",
        mates=mates or [],
        parts=[_part(pid) for pid in sorted(dof_states)],
    )


def test_placed_part_step_cites_the_placing_mate_edge() -> None:
    # WO-104 exemplar: RealizedAssembly now exposes typed mate edges, so
    # the placed part's step reads a real `mate_ref` (the full rigid mate
    # that placed it). Full step<->mate consumption is WO-100 D5.
    assembly = _assembly(
        {"Base": "fixed", "Arm": "placed"},
        mates=[
            MateEdge(
                id="m_arm",
                part_a="Base",
                part_b="Arm",
                kind="coincident",
                dof_consumed=6,
            )
        ],
    )
    steps = steps_for_assembly("gantry", assembly, {})
    place_steps = {s.part_ref: s for s in steps.steps if s.action == "place"}
    assert place_steps["Arm"].mate_ref == "m_arm"
    # The root part is placed by no mate -- honestly None, never invented.
    assert place_steps["Base"].mate_ref is None


def _discharged_bolt_evidence():
    request = DischargeRequest(
        claim_kind=_BOLT_CLAIM_KIND,
        limit=2_000.0,
        inputs={
            "f_preload": Interval(lo=9_000.0, hi=15_000.0),
            "f_external": Interval(lo=0.0, hi=800.0),
            "k_bolt": Interval.point(1.0e8),
            "k_clamp": Interval.point(4.0e8),
        },
    )
    evidence = default_registry().discharge(request)
    assert evidence.status.value == "discharged", evidence
    return evidence


def _violated_bolt_evidence():
    request = DischargeRequest(
        claim_kind=_BOLT_CLAIM_KIND,
        limit=2_000.0,
        inputs={
            "f_preload": Interval.point(1_500.0),
            "f_external": Interval(lo=0.0, hi=800.0),
            "k_bolt": Interval.point(1.0e8),
            "k_clamp": Interval.point(4.0e8),
        },
    )
    evidence = default_registry().discharge(request)
    assert evidence.status.value == "violated", evidence
    return evidence


def test_root_part_orders_before_a_placed_part() -> None:
    assembly = _assembly({"Base": "fixed", "Arm": "placed"})
    steps = steps_for_assembly("gantry", assembly, {})
    part_order = [s.part_ref for s in steps.steps]
    assert part_order == ["Base", "Arm"]
    assert steps.unordered_parts == ()


def test_underconstrained_part_is_named_in_unordered_callout_not_a_step() -> None:
    assembly = _assembly({"Base": "fixed", "Loose": "underconstrained"})
    steps = steps_for_assembly("gantry", assembly, {})
    part_refs = {s.part_ref for s in steps.steps}
    assert "Loose" not in part_refs
    assert steps.unordered_parts == ("Loose",)


def test_steps_for_assembly_is_deterministic_across_two_calls() -> None:
    assembly = _assembly({"Base": "fixed", "Arm": "placed", "Cap": "placed"})
    a = steps_for_assembly("gantry", assembly, {})
    b = steps_for_assembly("gantry", assembly, {})
    assert a.model_dump_json() == b.model_dump_json()


def test_placed_parts_tie_break_alphabetically_by_part_id() -> None:
    assembly = _assembly({"Base": "fixed", "Zeta": "placed", "Alpha": "placed"})
    steps = steps_for_assembly("gantry", assembly, {})
    part_order = [s.part_ref for s in steps.steps]
    assert part_order == ["Base", "Alpha", "Zeta"]


def test_fastener_callout_appears_only_with_discharged_evidence() -> None:
    assembly = _assembly({"Base": "fixed", "Arm": "placed"})
    evidence = _discharged_bolt_evidence()
    steps = steps_for_assembly("gantry", assembly, {"Arm": evidence})
    fasten_steps = [s for s in steps.steps if s.action == "fasten"]
    assert len(fasten_steps) == 1
    assert fasten_steps[0].part_ref == "Arm"
    assert fasten_steps[0].fastener is not None
    assert fasten_steps[0].fastener.evidence_hash == evidence.hash
    assert fasten_steps[0].fastener.model_id == evidence.model_id


def test_fastener_callout_absent_when_evidence_violated() -> None:
    assembly = _assembly({"Base": "fixed", "Arm": "placed"})
    evidence = _violated_bolt_evidence()
    steps = steps_for_assembly("gantry", assembly, {"Arm": evidence})
    fasten_steps = [s for s in steps.steps if s.action == "fasten"]
    assert fasten_steps == []


def test_fastener_callout_absent_when_no_evidence_supplied() -> None:
    assembly = _assembly({"Base": "fixed", "Arm": "placed"})
    steps = steps_for_assembly("gantry", assembly, {})
    assert all(s.action != "fasten" for s in steps.steps)


def test_stamp_steps_sets_the_stamp_through_the_model() -> None:
    assembly = _assembly({"Base": "fixed"})
    steps = steps_for_assembly("gantry", assembly, {})
    stamped = stamp_steps(steps, "PREVIEW -- NOT RELEASED: 3 unresolved")
    assert stamped.stamp == "PREVIEW -- NOT RELEASED: 3 unresolved"
    assert steps.stamp is None  # original untouched (frozen pydantic)


def test_render_document_every_number_traces_to_the_steps_payload() -> None:
    assembly = _assembly({"Base": "fixed", "Arm": "placed"})
    evidence = _discharged_bolt_evidence()
    steps = steps_for_assembly("gantry", assembly, {"Arm": evidence})
    doc = render_document(steps)
    assert "Base" in doc
    assert "Arm" in doc
    fastener = next(s.fastener for s in steps.steps if s.action == "fasten")
    assert fastener is not None
    # The rendered value is EXACTLY the payload's own float, formatted --
    # never a second, independently-computed number.
    assert f"{fastener.value.as_float():.6g}" in doc
    assert fastener.evidence_hash in doc
    assert fastener.model_id in doc


def test_render_document_unordered_callout_names_every_stranded_part() -> None:
    assembly = _assembly({"Base": "fixed", "Loose": "underconstrained"})
    steps = steps_for_assembly("gantry", assembly, {})
    doc = render_document(steps)
    assert "Loose" in doc
    assert "Unordered parts" in doc


def test_files_for_steps_writes_json_and_markdown_under_instructions() -> None:
    assembly = _assembly({"Base": "fixed"})
    steps = steps_for_assembly("gantry", assembly, {})
    files = files_for_steps("gantry", steps)
    relpaths = {f.relpath for f in files}
    assert relpaths == {
        "instructions/gantry.steps.json",
        "instructions/gantry.instructions.md",
    }
