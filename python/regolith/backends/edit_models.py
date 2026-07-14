"""Edit models for the three movable families (WO-130 deliverable 4,
D244.2, charter 42 sec. 7): boards, drawing sheets, assemblies.

An edit model is a canonical, hashed description of a family's movable
entities and their current poses, plus -- for each -- the WO-129 override
target path (charter 42 sec. 4's dotted `design.subject.slot` shape) that
would change it through the AD-40 CLI. This module NEVER imports the
WO-129 resolver (that WO runs in parallel on branch `wo129` and owns
target resolution) -- it only emits the path STRING per the charter's
documented shape, e.g. `"mainboard_mx.board.placements.J_DBG1.pose"`.

An edit model never contains a value the pipeline did not produce (D224):
where the realized surface lacks geometry an edit needs (footprint
courtyards for collision-aware dragging -- the named F136 gap), the
entity is still emitted as movable, carrying an honest `caveats` entry
saying so, never a fabricated value. Read-only entities carry
`read_only=True` and a `read_only_reason` (D244.2: "fixed by the mate
solve", "pinned by claim X", ...).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from regolith._schema.models import Placement, RealizedAssembly, RealizedLayout
from regolith.logging_setup import get_logger

_log = get_logger(__name__)

#: F-WO130-1 (escalation, see WO close-out): the realized-layout surface
#: (`RealizedLayout`) carries no footprint courtyard/keepout geometry --
#: only `Placement` (position/rotation/side). Board component drags are
#: therefore movable WITHOUT collision-checking; this is the same F136
#: gap WO-124's own module docstring already names. Never fabricated
#: here.
COURTYARD_ABSENT_CAVEAT = (
    "no footprint courtyard/keepout geometry on the realized surface -- "
    "this entity is movable WITHOUT collision-checking (F136 gap, "
    "F-WO130-1); a placer/editor may show it draggable but must say so"
)

#: F-WO130-1's companion: `RealizedLayout` carries no keepout-region
#: geometry at all (board-level exclusion zones), so a board edit model
#: cannot list them as read-only context -- it can only say, honestly,
#: that none are available yet.
KEEPOUTS_ABSENT_REASON = (
    "the realized-layout surface carries no keepout-region geometry "
    "(F136 gap, F-WO130-1) -- none listed here, never fabricated"
)


class MovableEntity(BaseModel):
    """One entity an edit model exposes: its current pose, whether it is
    editable, and the override target that would change it."""

    model_config = ConfigDict(frozen=True)

    entity_id: str
    kind: str
    pose: dict[str, float | str | None]
    override_target: str
    read_only: bool = False
    read_only_reason: str | None = None
    caveats: tuple[str, ...] = ()


class BoardEditModel(BaseModel):
    """A board's placements (component/test-point/tap-header), plus an
    honest keepouts absence note (see `KEEPOUTS_ABSENT_REASON`)."""

    model_config = ConfigDict(frozen=True)

    project: str
    subject: str
    entities: tuple[MovableEntity, ...] = ()
    keepouts_absent_reason: str = KEEPOUTS_ABSENT_REASON


class DrawingEditModel(BaseModel):
    """A drawing sheet's annotation anchors (movable) and view anchors
    (named absence -- see the module-level note in `drawing_edit_model`)."""

    model_config = ConfigDict(frozen=True)

    project: str
    subject: str
    entities: tuple[MovableEntity, ...] = ()


class AssemblyEditModel(BaseModel):
    """An assembly's part poses that the mate solve did NOT fix."""

    model_config = ConfigDict(frozen=True)

    project: str
    subject: str
    entities: tuple[MovableEntity, ...] = ()


def _placement_pose(p: Placement) -> dict[str, float | str | None]:
    return {
        "x_mm": p.position_mm[0],
        "y_mm": p.position_mm[1],
        "rot_deg": p.rotation_deg,
        "side": str(p.side),
    }


def _movable_placement(
    project: str, subject: str, kind: str, reference: str, placement: Placement
) -> MovableEntity:
    return MovableEntity(
        entity_id=reference,
        kind=kind,
        pose=_placement_pose(placement),
        override_target=f"{project}.{subject}.placements.{reference}.pose",
        read_only=False,
        caveats=(COURTYARD_ABSENT_CAVEAT,),
    )


def board_edit_model(
    project: str,
    subject: str,
    layout: RealizedLayout,
    *,
    tap_plan=None,  # noqa: ANN001 -- regolith.realizer.elec.debug_placement.TapPlacementPlan
) -> BoardEditModel:
    """The board's edit model (WO-130 deliverable 4): every component
    placement on `layout.placements`, PLUS -- when ``tap_plan`` is
    supplied (the WO-125 debug-profile augmentation; absent on a
    release ship, charter 40 sec. 1) -- its tap header and every test
    point, neither of which lives on `layout.placements` (they are the
    debug augmentation's OWN placements, WO-125's
    `TapPlacementPlan.header_placement`/`.test_points`)."""
    entities: list[MovableEntity] = [
        _movable_placement(project, subject, "component", p.reference, p)
        for p in layout.placements
    ]
    if tap_plan is not None:
        entities.append(
            _movable_placement(
                project,
                subject,
                "tap_header",
                tap_plan.header_placement.reference,
                tap_plan.header_placement,
            )
        )
        entities.extend(
            _movable_placement(
                project,
                subject,
                "test_point",
                tp.placement.reference,
                tp.placement,
            )
            for tp in tap_plan.test_points
        )
    _log.info(
        "board_edit_model: %d entity(ies) for %s.%s", len(entities), project, subject
    )
    return BoardEditModel(project=project, subject=subject, entities=tuple(entities))


def drawing_edit_model(project: str, subject: str, sheets) -> DrawingEditModel:  # noqa: ANN001
    """The drawing sheet's edit model (WO-130 deliverable 4): every
    `Annotation.anchor` across `sheets` (a `DrawingModel.sheets` list) is
    movable. `View` (charter 42 sec. 7's "view anchors") carries NO
    stored anchor on the current realized-drawing schema -- sheet layout
    is renderer-computed, not a persisted position -- so view entries are
    a named absence here (F-WO130-2), never a fabricated anchor.
    """
    entities: list[MovableEntity] = []
    for sheet_index, sheet in enumerate(sheets):
        for ann_index, annotation in enumerate(sheet.annotations):
            entities.append(
                MovableEntity(
                    entity_id=f"sheet{sheet_index}.annotation{ann_index}",
                    kind="annotation",
                    pose={
                        "x_mm": annotation.anchor[0],
                        "y_mm": annotation.anchor[1],
                    },
                    override_target=(
                        f"{project}.{subject}.annotations.{ann_index}.anchor"
                    ),
                    read_only=False,
                )
            )
        for view_index, _view in enumerate(sheet.views):
            entities.append(
                MovableEntity(
                    entity_id=f"sheet{sheet_index}.view{view_index}",
                    kind="view",
                    pose={},
                    override_target=(f"{project}.{subject}.views.{view_index}.anchor"),
                    read_only=True,
                    read_only_reason=(
                        "no stored view anchor on the realized-drawing "
                        "schema -- sheet layout is renderer-computed "
                        "(F136-adjacent gap, F-WO130-2); moving it is not "
                        "possible until a `View` anchor field lands"
                    ),
                )
            )
    _log.info(
        "drawing_edit_model: %d entity(ies) for %s.%s", len(entities), project, subject
    )
    return DrawingEditModel(project=project, subject=subject, entities=tuple(entities))


#: `RealizedAssembly.dof_states` values the mate solve DID fix (D244.2:
#: "a solved DOF is read-only WITH its reason") -- `"underconstrained"`
#: is the one state the solve did NOT determine, so it is the only
#: movable one.
_SOLVED_DOF_REASON = {
    "fixed": "fixed by the mate solve (the solve's own root)",
    "placed": "solved by a spanning mate (the mate solve fixed this DOF)",
}


def assembly_edit_model(
    project: str, subject: str, assembly: RealizedAssembly
) -> AssemblyEditModel:
    """The assembly's edit model (WO-130 deliverable 4): every part whose
    `dof_states` entry is `"underconstrained"` (the mate solve did NOT
    fix it) is movable; `"fixed"`/`"placed"` parts are read-only WITH
    their reason (D244.2)."""
    entities: list[MovableEntity] = []
    for part in assembly.parts:
        state = assembly.dof_states.get(part.id, "underconstrained")
        reason = _SOLVED_DOF_REASON.get(state)
        entities.append(
            MovableEntity(
                entity_id=part.id,
                kind="part",
                pose={
                    "x_m": part.transform.translation_m[0],
                    "y_m": part.transform.translation_m[1],
                    "z_m": part.transform.translation_m[2],
                    "rx_deg": part.transform.rotation_deg[0],
                    "ry_deg": part.transform.rotation_deg[1],
                    "rz_deg": part.transform.rotation_deg[2],
                },
                override_target=f"{project}.{subject}.parts.{part.id}.pose",
                read_only=reason is not None,
                read_only_reason=reason,
            )
        )
    _log.info(
        "assembly_edit_model: %d entity(ies) for %s.%s",
        len(entities),
        project,
        subject,
    )
    return AssemblyEditModel(project=project, subject=subject, entities=tuple(entities))
