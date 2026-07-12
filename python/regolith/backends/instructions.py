"""`AssemblySteps`: an ordered, viewable build document derived ENTIRELY
from proven pipeline data (WO-96, executing D199.1).

Rides the same one-producer-two-consumers shape D197 established for
`regolith.backends.drawings`: :func:`steps_for_assembly` builds the raw
`AssemblySteps` model from a `RealizedAssembly` (WO-62: parts + solved
transforms + `dof_states`) and this build's evidence index;
:func:`render_document` is the ONE renderer to the human-readable
document (markdown, the same idiom `regolith.docgen.render` already
uses -- no new dependency); :func:`files_for_steps` is the rendering
tail both the preview driver and `InstructionsBackend` (the ship
consumer) call.

HONEST-DATA SEAM (regolith/07 sec. 6, "backends never decide"; mirrors
`regolith.realizer.mech.assembly`'s own "INTEGRATION SEAM" docstring
precedent): `RealizedAssembly`'s wire schema (WO-62 deliverable 4)
carries `dof_states` (fixed | placed | underconstrained, keyed by part
id) and `mating_graph_hash` (an opaque provenance hash) -- it does NOT
carry the mate graph's own edges (which mate connects which two parts,
with what kind). No `regolith-lower` pass yet emits a numeric mate
graph either (`assembly.py`'s own note: mate solving is exercised over
a hand-declared `AssemblyDef`, never a compiled/stored artifact). So a
TRUE topological sort over individual mate dependencies is not
reconstructable from what actually reaches a backend today; this
producer builds the best HONEST proxy the schema supports:

  - the DOF-state itself already records solve reachability (`"fixed"`
    is the mate-solve root; `"placed"` is everything the solve
    successfully reached; `"underconstrained"` is everything it could
    not) -- steps are ordered fixed-first, then placed, tie-broken by
    part id (AD-6, deterministic, INV-10); underconstrained parts are
    NEVER given a step (that would invent an order the data does not
    support) -- they are named in the honest `unordered_parts` callout
    instead, exactly like a real mate-graph cycle or floating part
    would leave them.
  - `mate_ref` cites the placing mate's id (WO-104): `RealizedAssembly`
    now carries typed `mates` (part_a, part_b, kind, dof_consumed), so a
    placed part's step names the full rigid mate that placed it. Read
    straight from the exposed edges, never re-derived; a part with no
    such mate keeps `None`. Full step<->mate consumption (kind-aware
    ordering, fastener joins) is WO-100 D5.
  - fastener/torque callouts: no torque-producing model exists in this
    harness yet (grepped -- `bolted_joint.py` discharges a residual
    CLAMP FORCE per VDI 2230, `bearing_life.py` discharges an L10 LIFE;
    neither is literally a torque). Rather than invent a torque number
    the toolchain never computed, this producer reports the model's
    OWN discharged quantity, labeled honestly, keyed by convention:
    `BackendInputs.evidence[part.id]` (the same "keyed by subject"
    convention every other evidence-consuming backend already uses,
    `regolith.backends.framework.BackendInputs`'s own docstring) is the
    fastener claim for the mate that PLACES that part, when one is
    supplied. A discharged bolted-joint/bearing claim there emits a
    `FastenerCallout`; anything else (violated/indeterminate/absent)
    emits none -- never decoration.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict
from typani.result import Ok, Result

from regolith._schema.models import Evidence, RealizedAssembly
from regolith.backends.artifacts import NativeArtifactStore
from regolith.backends.framework import BackendInputs, OutputFile
from regolith.errors import BackendError
from regolith.harness.quantity import bits_to_f64
from regolith.logging_setup import get_logger

_log = get_logger(__name__)

# model_id prefix (before "@version") -> (claim label, unit label) for
# the fastener claim kinds this producer recognizes. One home for the
# vocabulary (mirrors `regolith.harness.models.*`'s own `CLAIM_KIND`
# constants -- never re-spelled elsewhere).
_FASTENER_MODEL_LABELS: Mapping[str, tuple[str, str]] = {
    "bolted_joint_separation_vdi2230": ("residual clamp force (VDI 2230)", "N"),
    "bearing_basic_rating_life_l10h": ("basic rating life L10", "h"),
}

_DOF_TIER = {"fixed": 0, "placed": 1}


class FastenerCallout(BaseModel):
    """A discharged fastener/bearing claim attached to a step (never
    decoration -- present only when `BackendInputs.evidence` actually
    carries a `discharged` `Evidence` for the part, regolith/07 sec. 6).
    """

    model_config = ConfigDict(frozen=True)

    claim_label: str
    value: float
    unit: str
    model_id: str
    evidence_hash: str


class AssemblyStep(BaseModel):
    """One ordered build step: place a part, or fasten it (with a
    `FastenerCallout` when the fastening claim discharged)."""

    model_config = ConfigDict(frozen=True)

    step: int
    action: str  # "place" | "fasten"
    part_ref: str
    mate_ref: str | None = None
    fastener: FastenerCallout | None = None


class AssemblySteps(BaseModel):
    """The machine-readable assembly-instructions payload for one
    subject: the ordered step list plus the honest unordered-parts
    callout (parts the mate graph could not place -- WO-96 deliverable
    1). `stamp` carries D197's preview honesty banner (`None` for a
    `ship` consumer, set through the model -- never by post-editing the
    rendered document -- for a `preview` consumer)."""

    model_config = ConfigDict(frozen=True)

    subject: str
    steps: tuple[AssemblyStep, ...]
    unordered_parts: tuple[str, ...]
    mating_graph_hash: str
    stamp: str | None = None


def _fastener_for_part(
    part_id: str, evidence: Mapping[str, Evidence]
) -> FastenerCallout | None:
    """The `FastenerCallout` for `part_id`, keyed by the module
    docstring's `evidence[part.id]` convention -- `None` unless the
    evidence is present, its `model_id` matches a recognized fastener
    model, AND its status is `discharged` (never violated/indeterminate)."""
    found = evidence.get(part_id)
    if found is None:
        return None
    if found.status.value != "discharged":
        _log.debug(
            "instructions: %s has evidence but status=%s (no fastener callout)",
            part_id,
            found.status.value,
        )
        return None
    prefix = found.model_id.split("@", 1)[0]
    labels = _FASTENER_MODEL_LABELS.get(prefix)
    if labels is None:
        return None
    label, unit = labels
    value = bits_to_f64(found.value_bits)
    _log.info(
        "instructions: fastener callout part=%s model=%s value=%s%s evidence=%s",
        part_id,
        found.model_id,
        value,
        unit,
        found.hash,
    )
    return FastenerCallout(
        claim_label=label,
        value=value,
        unit=unit,
        model_id=found.model_id,
        evidence_hash=found.hash,
    )


def steps_for_assembly(
    subject: str,
    assembly: RealizedAssembly,
    evidence: Mapping[str, Evidence],
) -> AssemblySteps:
    """Build the ordered `AssemblySteps` for `assembly` (module docstring's
    honest-data seam): fixed-then-placed, tie-broken by part id;
    underconstrained parts never get a step, they are named in
    `unordered_parts` (WO-96 deliverable 1's honest-gap callout).
    """
    tiered = [
        (p.id, _DOF_TIER[assembly.dof_states.get(p.id, "underconstrained")])
        for p in assembly.parts
        if assembly.dof_states.get(p.id) in _DOF_TIER
    ]
    ordered_ids = [pid for pid, _tier in sorted(tiered, key=lambda t: (t[1], t[0]))]
    unordered = sorted(
        p.id for p in assembly.parts if assembly.dof_states.get(p.id) not in _DOF_TIER
    )

    # WO-104: the mate that PLACES each part (`part_b`, a full rigid
    # spanning-tree mate `dof_consumed == 6`), keyed by placed part id --
    # read straight from the exposed `assembly.mates`, never re-derived.
    # First placing mate wins on the (source-order) list (AD-6). Full
    # step<->mate consumption is WO-100 D5; this only cites the id.
    placing_mate: dict[str, str] = {}
    for edge in assembly.mates:
        if edge.dof_consumed == 6 and edge.part_b not in placing_mate:
            placing_mate[edge.part_b] = edge.id

    steps: list[AssemblyStep] = []
    n = 0
    for part_id in ordered_ids:
        n += 1
        steps.append(
            AssemblyStep(
                step=n,
                action="place",
                part_ref=part_id,
                mate_ref=placing_mate.get(part_id),
            )
        )
        fastener = _fastener_for_part(part_id, evidence)
        if fastener is not None:
            n += 1
            steps.append(
                AssemblyStep(
                    step=n, action="fasten", part_ref=part_id, fastener=fastener
                )
            )

    _log.info(
        "instructions: subject=%s steps=%d unordered=%d",
        subject,
        len(steps),
        len(unordered),
    )
    return AssemblySteps(
        subject=subject,
        steps=tuple(steps),
        unordered_parts=tuple(unordered),
        mating_graph_hash=assembly.mating_graph_hash,
    )


def stamp_steps(steps: AssemblySteps, stamp_text: str) -> AssemblySteps:
    """D197's honesty stamp, applied THROUGH the model (never by
    post-editing a rendered document) -- mirrors
    `regolith.backends.drawings.backend.stamp_model` exactly."""
    return steps.model_copy(update={"stamp": stamp_text})


def _svg_of(
    placed_lines: list[tuple[tuple[float, float], ...]],
    current_lines: list[tuple[tuple[float, float], ...]],
) -> str:
    """A small standalone inline SVG of a step's front-view silhouette:
    already-placed edges in gray, the current part's edges highlighted.
    Deterministic (fixed viewport, fixed float format); ASCII."""
    all_lines = placed_lines + current_lines
    xs = [x for line in all_lines for x, _y in line]
    ys = [y for line in all_lines for _x, y in line]
    if not xs or not ys:
        return ""
    min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
    span = max(max_x - min_x, max_y - min_y, 1.0)
    scale = 180.0 / span

    def _poly(line: tuple[tuple[float, float], ...], color: str, width: str) -> str:
        pts = " ".join(
            f"{(x - min_x) * scale:.2f},{(max_y - y) * scale:.2f}" for x, y in line
        )
        return (
            f'<polyline points="{pts}" fill="none" '
            f'stroke="{color}" stroke-width="{width}"/>'
        )

    body = "".join(_poly(line, "#888", "0.6") for line in placed_lines)
    body += "".join(_poly(line, "#c0392b", "1.2") for line in current_lines)
    dim = f"{200.0:.0f}"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{dim}" height="{dim}" '
        f'viewBox="-10 -10 {dim} {dim}">{body}</svg>'
    )


def step_view_svgs(
    assembly: RealizedAssembly,
    steps: AssemblySteps,
    native: NativeArtifactStore,
) -> dict[int, str]:
    """One inline front-view SVG per PLACE step (WO-100 deliverable 5):
    the parts placed so far in gray, the step's own part highlighted,
    projected from the pinned STEP bytes. A part whose bytes are absent
    (or a host without OCP) contributes no view -- honestly omitted,
    never fabricated. Keyed by step number."""
    from regolith.backends.drawings.project import project_assembly_front

    parts_by_id = {p.id: p for p in assembly.parts}

    def _placed(
        part_id: str,
    ) -> tuple[bytes, tuple[float, float, float], tuple[float, float, float]] | None:
        part = parts_by_id.get(part_id)
        if part is None:
            return None
        resolved = native.resolve(part.geometry_digest)
        if resolved.is_err:
            return None
        tr = part.transform
        return (
            resolved.danger_ok,
            (tr.rotation_deg[0], tr.rotation_deg[1], tr.rotation_deg[2]),
            (
                tr.translation_m[0] * 1000.0,
                tr.translation_m[1] * 1000.0,
                tr.translation_m[2] * 1000.0,
            ),
        )

    views: dict[int, str] = {}
    prior_ids: list[str] = []
    for step in steps.steps:
        if step.action != "place":
            continue
        current = _placed(step.part_ref)
        if current is None:
            prior_ids.append(step.part_ref)
            continue
        prior = [pl for pid in prior_ids if (pl := _placed(pid)) is not None]
        placed_lines = project_assembly_front(prior) or []
        current_lines = project_assembly_front([current]) or []
        svg = _svg_of(placed_lines, current_lines)
        if svg:
            views[step.step] = svg
        prior_ids.append(step.part_ref)
    _log.info("instructions: %d step view(s) for %s", len(views), steps.subject)
    return views


def render_document(
    steps: AssemblySteps,
    views: Mapping[int, str] = {},  # noqa: B006 (frozen input)
) -> str:
    """The ONE human-readable renderer: deterministic markdown (the
    `regolith.docgen.render` idiom -- no new rendering dependency).
    Every number here traces straight to `steps` (regolith/07 sec. 6):
    this function only formats, it invents nothing.
    """
    lines: list[str] = [f"# Assembly instructions: {steps.subject}", ""]
    if steps.stamp is not None:
        lines.append(f"**{steps.stamp}**")
        lines.append("")
    lines.append(f"Mating graph: `{steps.mating_graph_hash}`")
    lines.append("")
    lines.append("## Steps")
    lines.append("")
    if not steps.steps:
        lines.append("(no orderable steps)")
    for step in steps.steps:
        if step.action == "place":
            lines.append(f"{step.step}. Place part `{step.part_ref}`.")
            view = views.get(step.step)
            if view:
                lines.append("")
                lines.append(view)
        else:
            assert step.fastener is not None
            fastener = step.fastener
            lines.append(
                f"{step.step}. Fasten part `{step.part_ref}` -- "
                f"{fastener.claim_label}: {fastener.value:.6g} {fastener.unit} "
                f"(discharged, model `{fastener.model_id}`, "
                f"evidence `{fastener.evidence_hash}`)."
            )
    lines.append("")
    lines.append("## Unordered parts")
    lines.append("")
    if steps.unordered_parts:
        lines.append(
            "The mate graph could not place the following part(s) -- no "
            "honest step order is available for them (a cycle or a "
            "floating/underconstrained part):"
        )
        lines.append("")
        for part_id in steps.unordered_parts:
            lines.append(f"- `{part_id}`")
    else:
        lines.append("(none -- every part in this assembly placed)")
    lines.append("")
    return "\n".join(lines)


def files_for_steps(
    subject: str,
    steps: AssemblySteps,
    views: Mapping[int, str] = {},  # noqa: B006 (frozen input)
) -> tuple[OutputFile, ...]:
    """The `<subject>.steps.json` + `.instructions.md` pair for an
    already-built `AssemblySteps` -- the ONE rendering tail both
    `InstructionsBackend.produce` and the preview driver call. ``views``
    (WO-100 deliverable 5) embeds a per-step projected front view in the
    markdown; empty when native bytes / OCP are unavailable."""
    steps_json = steps.model_dump_json(by_alias=True).encode("utf-8")
    doc_bytes = render_document(steps, views).encode("ascii")
    return (
        OutputFile.of(f"instructions/{subject}.steps.json", steps_json),
        OutputFile.of(f"instructions/{subject}.instructions.md", doc_bytes),
    )


class InstructionsBackend:
    """`ship`-side consumer: produces `instructions/<subject>.steps.json`
    + `.instructions.md` for every subject `BackendInputs.assemblies`
    carries. Runs only inside the release gate like every other ship
    backend (INV-24) -- never stamped (the gate is already clean by
    construction at this point)."""

    def __init__(self, subjects: tuple[str, ...] | None = None) -> None:
        """Bind the caller-decided subject list (never invents which
        assemblies to document -- regolith/07 sec. 6); `None` documents
        every subject `BackendInputs.assemblies` carries."""
        self._subjects = tuple(sorted(subjects)) if subjects is not None else None

    def produce(
        self, inputs: BackendInputs
    ) -> Result[tuple[OutputFile, ...], BackendError]:
        """Emit the steps JSON + rendered document for every configured
        (or, if unconfigured, every available) assembly subject."""
        subjects = (
            self._subjects
            if self._subjects is not None
            else tuple(sorted(inputs.assemblies))
        )
        files: list[OutputFile] = []
        for subject in subjects:
            assembly = inputs.assemblies.get(subject)
            if assembly is None:
                _log.warning(
                    "instructions backend: no RealizedAssembly for %s", subject
                )
                continue
            steps = steps_for_assembly(subject, assembly, inputs.evidence)
            views = step_view_svgs(assembly, steps, inputs.native)
            files.extend(files_for_steps(subject, steps, views))
        _log.info("instructions backend: emitted %d file(s)", len(files))
        return Ok(tuple(files))
