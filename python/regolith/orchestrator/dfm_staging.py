"""`manufacturable(<process>)` staging: the build's own FeatureProgram +
realized-geometry facts reaching the `mfg.manufacturable` model
(WO-110 headline; F130 census item 4, D232.2).

Mirrors `plan_staging`'s posture exactly: this module owns DERIVING the
staged `dfm_part`/`dfm_tools` payload records from data the build
already produced -- the payload's `feature_programs` (WO-51),
`snapshots` (subject-hash -> scope name), and the staged-build loop's
realized inputs (`geometry.realized`, AD-25) -- and staging them into
the build's ONE `PayloadStore` (D96/D154). The obligation-to-request
lowering stays in :mod:`regolith.orchestrator.translate`
(`_translate_manufacturable`), which maps this module's honest gaps
onto its own `Deferral` surface, same split as costing/plan staging.

ONE HOME for the process vocabulary (the tripwire rule applied to
process words): the claim-token map (`manufacturable(milled)` ->
family) and the stage-process map (`process=cnc_mill` -> family) live
here and nowhere else.

v1 grounding scope (named cuts, all reported in the WO close-out):

- Only the MILL family grounds (the existing `[[machine]]`/`[[tool]]`
  record vocabulary is mill-class); every other family defers with the
  reason naming what would ground it.
- Only `hole`-kind feature ops feed the tool-fit check (pocket ops
  carry no width scalar today); a mill-stage hole whose diameter or
  depth is not a spelled literal defers NAMING the parameter (the
  D224/WO-113 enrichment surface, never a guess).
- A part with more than one realized geometry subject (weldments)
  defers stock fit: per-piece boxes live in per-piece frames, so no
  assembly-level bounding box is derivable without RealizedAssembly
  consumption (a named cut).
"""

from __future__ import annotations

import json
import re

from regolith._schema.models import FeatureProgram, RealizedGeometry
from regolith.harness.models.cam.records import Aabb
from regolith.harness.models.dfm.records import (
    MILL_FAMILY,
    DfmFeature,
    DfmPart,
    DfmToolSet,
)
from regolith.logging_setup import get_logger
from regolith.orchestrator.payload_store import PayloadStore

_log = get_logger(__name__)

# Claim-token -> process family (`manufacturable(<token>)`; the corpus
# vocabulary as surveyed at dispatch: cut/milled/mill/formed/machined/
# molded/turned/routed/tapped/plated/all).
CLAIM_TOKEN_FAMILIES: dict[str, str] = {
    "mill": MILL_FAMILY,
    "milled": MILL_FAMILY,
    "machined": MILL_FAMILY,
    "routed": MILL_FAMILY,
    "turned": "turn",
    "cut": "cut",
    "formed": "form",
    "molded": "mold",
    "tapped": "tap",
    "plated": "plate",
    "printed": "print",
    "all": "all",
}

# Stage `process=<head>` -> process family (the fleet's spelled heads).
STAGE_PROCESS_FAMILIES: dict[str, str] = {
    "cnc_mill": MILL_FAMILY,
    "cnc_drill": MILL_FAMILY,
    "cnc_router_3axis": MILL_FAMILY,
    "gear_hob": "hob",
    "cnc_lathe": "turn",
    "laser_cut": "cut",
    "tube_laser": "cut",
    "press_brake": "form",
    "press_shop": "form",
    "sheet_metal": "form",
    "metal_spinning": "form",
    "mandrel_bend": "form",
    "tube_bend": "form",
    "cnc_coiler": "form",
    "injection_mold": "mold",
    "investment_cast": "cast",
    "drop_forge": "forge",
    "electroplate": "plate",
    "electrodeposit": "plate",
    "tap_rigid": "tap",
    "saw_stock": "saw",
    "gtaw": "weld",
    "mig_weld": "weld",
    "tig_weld": "weld",
}

# The families the v1 model family can actually ground (see module doc).
GROUNDED_FAMILIES: frozenset[str] = frozenset({MILL_FAMILY})

# Spelled length -> mm. Deliberately tiny: the corpus spells feature
# scalars in these units; an unrecognized unit is an HONEST non-parse
# (the caller defers naming the parameter), never a silent unit guess.
_LENGTH_MM = {"mm": 1.0, "cm": 10.0, "m": 1000.0, "um": 1e-3, "in": 25.4}
_LENGTH_RE = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*(mm|cm|um|in|m)\s*$")


def parse_len_mm(text: str) -> float | None:
    """Parse a spelled length literal (`17mm`, `1.5in`) to mm, or None."""
    match = _LENGTH_RE.match(text)
    if match is None:
        return None
    return float(match.group(1)) * _LENGTH_MM[match.group(2)]


class DfmPartFacts:
    """One part's derived DFM facts, plus the gaps found deriving them."""

    def __init__(
        self,
        part: DfmPart | None,
        *,
        missing_params: tuple[str, ...] = (),
        geometry_gap: str = "",
    ) -> None:
        self.part = part
        # `<feature>.<param>` names a spelled-but-unresolvable (or
        # unspelled) scalar -- the WO-113/D224 enrichment surface.
        self.missing_params = missing_params
        # Non-empty names why no realized bounding box exists.
        self.geometry_gap = geometry_gap


class DfmContext:
    """The build's DFM-staging state (the PlanContext posture).

    Built once per `build()` from the payload JSON + the realized-input
    channel; consumed by `translate._translate_manufacturable`.
    """

    def __init__(
        self,
        *,
        scope_by_subject: dict[str, str],
        programs: dict[str, FeatureProgram],
        realized: dict[str, tuple[str, RealizedGeometry]],
        payload_store: PayloadStore | None,
    ) -> None:
        self._scope_by_subject = scope_by_subject
        self._programs = programs
        # part-scoped realized subjects: subject text -> (digest, geometry)
        self._realized = realized
        self._store = payload_store

    def scope_of(self, subject_ref: str) -> str | None:
        """The snapshot scope name (part/decl) a subject hash belongs to."""
        return self._scope_by_subject.get(subject_ref)

    def program_of(self, part_name: str) -> FeatureProgram | None:
        """The emitted FeatureProgram for ``part_name``, if any."""
        return self._programs.get(part_name)

    def realized_of(self, part_name: str) -> list[tuple[str, RealizedGeometry]]:
        """Every realized (digest, geometry) whose subject is this part's."""
        prefix = part_name + "."
        return [
            (digest, geom)
            for subject, (digest, geom) in sorted(self._realized.items())
            if subject == part_name or subject.startswith(prefix)
        ]

    def stage(self, name: str, record: DfmPart | DfmToolSet) -> str | None:
        """Stage one derived record into the build's payload store,
        returning its content digest (`None` = no store configured)."""
        if self._store is None:
            return None
        digest = self._store.put(record.model_dump_json().encode("utf-8"))
        _log.debug("dfm staging: put %s digest=%s", name, digest)
        return digest


def load_dfm_context(
    build_payload: dict[str, object],
    realized_inputs: tuple[object, ...],
    *,
    payload_store: PayloadStore | None,
) -> DfmContext:
    """Build the DfmContext from the build's own payload + realized set.

    Total and lenient by construction: a malformed row is logged and
    skipped (its dependent claims then defer naming the gap), never a
    build failure -- manufacturability staging must not be able to
    break a build that never claims it.
    """
    scope_by_subject: dict[str, str] = {}
    snapshots = build_payload.get("snapshots")
    if isinstance(snapshots, list):
        for snap in snapshots:
            if not isinstance(snap, dict):
                continue
            snap_hash = snap.get("hash")
            snap_scope = snap.get("scope")
            if snap_hash is not None and snap_scope is not None:
                scope_by_subject[str(snap_hash)] = str(snap_scope)
    programs: dict[str, FeatureProgram] = {}
    raw_programs = build_payload.get("feature_programs")
    if isinstance(raw_programs, list):
        for raw in raw_programs:
            try:
                program = FeatureProgram.model_validate(raw)
            except Exception:  # pydantic ValidationError; skip, named later
                _log.warning("dfm staging: unparseable feature program row skipped")
                continue
            programs[program.part_name] = program
    realized: dict[str, tuple[str, RealizedGeometry]] = {}
    for ri in realized_inputs:
        kind = getattr(ri, "kind", "")
        if kind != "geometry.realized":
            continue
        subject = getattr(ri, "subject", "")
        digest = getattr(ri, "digest", "")
        try:
            geometry = RealizedGeometry.model_validate(
                json.loads(bytes(getattr(ri, "payload_bytes", b"")).decode("utf-8"))
            )
        except Exception:
            _log.warning(
                "dfm staging: realized input for subject %s unparseable; skipped",
                subject,
            )
            continue
        realized[subject] = (digest, geometry)
    _log.debug(
        "dfm context: %d scope(s), %d program(s), %d realized subject(s)",
        len(scope_by_subject),
        len(programs),
        len(realized),
    )
    return DfmContext(
        scope_by_subject=scope_by_subject,
        programs=programs,
        realized=realized,
        payload_store=payload_store,
    )


def derive_part_facts(
    context: DfmContext, part_name: str, claim_token: str
) -> DfmPartFacts:
    """Derive the staged `DfmPart` for one claim, or the named gaps.

    The mill-family fact set: every mill-stage `hole` op's spelled
    diameter/depth (a hole missing either is a named missing param --
    depth falls back to the part's ONE spelled blank thickness when
    present, recorded in the feature's provenance), plus the part's
    single realized bounding box.
    """
    program = context.program_of(part_name)
    if program is None:
        return DfmPartFacts(
            None, geometry_gap=f"no emitted FeatureProgram for part {part_name!r}"
        )
    families: list[str] = []
    thickness_mm: float | None = None
    thickness_src = ""
    for op in program.features:
        family = STAGE_PROCESS_FAMILIES.get(op.process or "")
        if family is not None and family not in families:
            families.append(family)
        if op.kind == "blank" and thickness_mm is None:
            spelled = (op.params or {}).get("thickness")
            if spelled is not None:
                thickness_mm = parse_len_mm(spelled.text)
                thickness_src = f"blank {op.name!r} thickness {spelled.text}"
    features: list[DfmFeature] = []
    missing: list[str] = []
    for op in program.features:
        if op.kind != "hole":
            continue
        family = STAGE_PROCESS_FAMILIES.get(op.process or "")
        if family != MILL_FAMILY:
            continue
        params = op.params or {}
        dia_text = params.get("diameter")
        dia_mm = parse_len_mm(dia_text.text) if dia_text is not None else None
        if dia_mm is None:
            missing.append(f"{op.name}.diameter")
            continue
        depth_text = params.get("depth")
        depth_mm = parse_len_mm(depth_text.text) if depth_text is not None else None
        provenance = "spelled"
        if depth_mm is None and thickness_mm is not None:
            depth_mm = thickness_mm
            provenance = f"through-hole depth from {thickness_src}"
        if depth_mm is None:
            missing.append(f"{op.name}.depth")
            continue
        features.append(
            DfmFeature(
                name=op.name,
                count=op.count,
                stage=op.stage or "",
                process=op.process or "",
                dia_mm=dia_mm,
                depth_mm=depth_mm,
                provenance=provenance,
            )
        )
    realized = context.realized_of(part_name)
    if not realized:
        return DfmPartFacts(
            None,
            missing_params=tuple(missing),
            geometry_gap=(
                f"part {part_name!r} has no realized geometry in this build "
                "(the staged loop realized nothing for it)"
            ),
        )
    if len(realized) > 1:
        return DfmPartFacts(
            None,
            missing_params=tuple(missing),
            geometry_gap=(
                f"part {part_name!r} realized {len(realized)} pieces; "
                "assembly-level bounding box is not derivable without "
                "RealizedAssembly consumption (WO-110 named cut)"
            ),
        )
    digest, geometry = realized[0]
    top = geometry.topology
    bbox = Aabb(
        x_min=top.bbox_min_mm[0],
        x_max=top.bbox_max_mm[0],
        y_min=top.bbox_min_mm[1],
        y_max=top.bbox_max_mm[1],
        z_min=top.bbox_min_mm[2],
        z_max=top.bbox_max_mm[2],
    )
    part = DfmPart(
        part_name=part_name,
        claim_process=claim_token,
        families=tuple(families),
        features=tuple(features),
        bbox_mm=bbox,
        geometry_digest=digest,
    )
    return DfmPartFacts(part, missing_params=tuple(missing))


__all__ = [
    "CLAIM_TOKEN_FAMILIES",
    "GROUNDED_FAMILIES",
    "STAGE_PROCESS_FAMILIES",
    "DfmContext",
    "DfmPartFacts",
    "derive_part_facts",
    "load_dfm_context",
    "parse_len_mm",
]
