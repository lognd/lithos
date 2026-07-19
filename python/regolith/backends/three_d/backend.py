"""`ThreeDBackend`: the ship/preview consumer that emits the 3D artifact
family (WO-100 deliverable 3/4) -- a deterministic GLB + a self-contained
viewer per `RealizedGeometry` part and per `RealizedAssembly`.

The two realized-IR renderers register through the WO-99 renderer
registry (`RendererRegistry.register_realized`, charter 38 sec. 1
decision 6: "registered like any renderer"). The backend walks the
registry -- adding a new realized format is ONE registration, zero edits
here -- and namespaces every file under ``3d/`` (the release-package
layout, charter 38 sec. 1 decision 3). A subject whose native STEP bytes
are absent, or a host without OCP, is logged and skipped honestly (no 3D
file), never crashed on -- the same "never refuse on one missing input"
discipline the drawing/board loops already follow.
"""

from __future__ import annotations

from typani.result import Err, Ok, Result

from regolith._schema.models import RealizedAssembly, RealizedGeometry
from regolith.backends.artifacts import NativeArtifactStore
from regolith.backends.framework import BackendInputs, OutputFile
from regolith.backends.registry import (
    THREE_D_ASSEMBLY_FAMILY,
    THREE_D_PART_FAMILY,
    RealizedRendererRegistration,
    RealizedSubject,
    RendererRegistry,
    default_renderer_registry,
)
from regolith.backends.three_d.glb import GlbNode, matrix_from_transform, write_glb
from regolith.backends.three_d.tessellate import tessellate_step
from regolith.backends.three_d.viewer import viewer_html
from regolith.errors import BackendError
from regolith.logging_setup import get_logger

_log = get_logger(__name__)

# Translation on a `RealizedAssembly` part transform is metres; the
# tessellated mesh space is millimetres. One conversion home.
_M_TO_MM = 1000.0


def _glb_and_viewer(subject: str, glb: bytes) -> tuple[OutputFile, ...]:
    """The coupled `3d/<subject>.glb` + `3d/<subject>.viewer.html` pair."""
    return (
        OutputFile.of(f"3d/{subject}.glb", glb),
        OutputFile.of(f"3d/{subject}.viewer.html", viewer_html(glb, subject)),
    )


# frob:doc docs/modules/py-backends.md#three-d-backend
def render_part_3d(
    subject: str, subject_ir: RealizedSubject, native: NativeArtifactStore
) -> Result[tuple[OutputFile, ...], BackendError]:
    """Tessellate one `RealizedGeometry` part into a single-node GLB +
    viewer (WO-100 deliverable 3). `Err` when its pinned STEP is absent
    or OCP cannot mesh it (the backend skips it honestly)."""
    assert isinstance(subject_ir, RealizedGeometry)
    resolved = native.resolve(subject_ir.step_content_hash)
    if resolved.is_err:
        return Err(resolved.danger_err)
    mesh = tessellate_step(resolved.danger_ok)
    if mesh is None:
        return Err(
            BackendError(
                kind="tessellation_unavailable",
                message=f"cannot tessellate STEP for {subject!r} (OCP/import)",
            )
        )
    glb = write_glb((mesh,), (GlbNode(name=subject, mesh=0),))
    return Ok(_glb_and_viewer(subject, glb))


# frob:doc docs/modules/py-backends.md#three-d-backend
def render_assembly_3d(
    subject: str, subject_ir: RealizedSubject, native: NativeArtifactStore
) -> Result[tuple[OutputFile, ...], BackendError]:
    """Tessellate a `RealizedAssembly` into a placed-instance GLB + viewer
    (WO-100 deliverable 3): one mesh per DISTINCT part geometry (deduped
    by digest), one node per part instance carrying its SOLVED transform
    (reused, never re-solved -- regolith/07 sec. 6), named by part id for
    the viewer's hover. `Err` only when NO part could be meshed."""
    assert isinstance(subject_ir, RealizedAssembly)
    mesh_index: dict[str, int] = {}
    meshes = []
    nodes: list[GlbNode] = []
    for part in sorted(subject_ir.parts, key=lambda p: p.id):
        digest = part.geometry_digest
        if digest not in mesh_index:
            resolved = native.resolve(digest)
            if resolved.is_err:
                _log.warning(
                    "3d: assembly %s part %s STEP %s missing; skipping instance",
                    subject,
                    part.id,
                    digest[:12],
                )
                continue
            mesh = tessellate_step(resolved.danger_ok)
            if mesh is None:
                _log.warning(
                    "3d: assembly %s part %s not meshable; skipping", subject, part.id
                )
                continue
            mesh_index[digest] = len(meshes)
            meshes.append(mesh)
        tr = part.transform
        rot = (tr.rotation_deg[0], tr.rotation_deg[1], tr.rotation_deg[2])
        trans = (
            tr.translation_m[0] * _M_TO_MM,
            tr.translation_m[1] * _M_TO_MM,
            tr.translation_m[2] * _M_TO_MM,
        )
        nodes.append(
            GlbNode(
                name=part.id,
                mesh=mesh_index[digest],
                matrix=matrix_from_transform(rot, trans),
            )
        )
    if not nodes:
        return Err(
            BackendError(
                kind="assembly_3d_unavailable",
                message=f"no part of assembly {subject!r} could be tessellated",
            )
        )
    glb = write_glb(tuple(meshes), tuple(nodes))
    return Ok(_glb_and_viewer(subject, glb))


# frob:doc docs/modules/py-backends.md#three-d-backend
def register_three_d(registry: RendererRegistry) -> None:
    """Register the two built-in 3D renderers (part + assembly) into
    ``registry`` (WO-100). Idempotency is the registry's concern: a
    duplicate id is a loud `Err` it already rejects."""
    registry.register_realized(
        RealizedRendererRegistration("glb", THREE_D_PART_FAMILY, render_part_3d)
    )
    registry.register_realized(
        RealizedRendererRegistration("glb", THREE_D_ASSEMBLY_FAMILY, render_assembly_3d)
    )


# frob:doc docs/modules/py-backends.md#three-d-backend
def default_three_d_registry() -> RendererRegistry:
    """A `RendererRegistry` carrying the drawing built-ins PLUS the 3D
    realized renderers -- the registry `ThreeDBackend` walks by default."""
    registry = default_renderer_registry()
    register_three_d(registry)
    return registry


# frob:doc docs/modules/py-backends.md#three-d-backend
class ThreeDBackend:
    """Emits `3d/<subject>.glb` + `.viewer.html` for every geometry part
    and every assembly the caller names (never invents which subjects to
    render -- regolith/07 sec. 6). A subject with absent bytes / no OCP is
    skipped honestly, never crashed on.
    """

    def __init__(
        self,
        *,
        parts: tuple[str, ...] | None = None,
        assemblies: tuple[str, ...] | None = None,
        renderers: RendererRegistry | None = None,
    ) -> None:
        """Bind the caller-decided part/assembly subject lists (``None``
        renders every subject the inputs carry) and the registry (default:
        drawing built-ins + the 3D renderers)."""
        self._parts = tuple(sorted(parts)) if parts is not None else None
        self._assemblies = tuple(sorted(assemblies)) if assemblies is not None else None
        self._renderers = (
            renderers if renderers is not None else default_three_d_registry()
        )

    def _part_renderers(self) -> tuple[RealizedRendererRegistration, ...]:
        return self._renderers.for_realized_family(THREE_D_PART_FAMILY)

    def _assembly_renderers(self) -> tuple[RealizedRendererRegistration, ...]:
        return self._renderers.for_realized_family(THREE_D_ASSEMBLY_FAMILY)

    # frob:doc docs/modules/py-backends.md#three-d-backend
    # frob:waive PERF004 reason="one-shot sort of a small set, never re-sorted"
    def produce(
        self, inputs: BackendInputs
    ) -> Result[tuple[OutputFile, ...], BackendError]:
        """Render the 3D family for every configured subject, skipping any
        subject whose native bytes are unavailable (Result-total)."""
        files: list[OutputFile] = []
        part_subjects = (
            self._parts if self._parts is not None else tuple(sorted(inputs.geometry))
        )
        for subject in part_subjects:
            geometry = inputs.geometry.get(subject)
            if geometry is None:
                _log.warning("3d backend: no geometry for part %s", subject)
                continue
            for reg in self._part_renderers():
                result = reg.render(subject, geometry, inputs.native)
                if result.is_err:
                    _log.warning(
                        "3d backend: part %s (%s) skipped: %s",
                        subject,
                        reg.format_id,
                        result.danger_err.message,
                    )
                    continue
                files.extend(result.danger_ok)

        asm_subjects = (
            self._assemblies
            if self._assemblies is not None
            else tuple(sorted(inputs.assemblies))
        )
        for subject in asm_subjects:
            assembly = inputs.assemblies.get(subject)
            if assembly is None:
                _log.warning("3d backend: no assembly for %s", subject)
                continue
            for reg in self._assembly_renderers():
                result = reg.render(subject, assembly, inputs.native)
                if result.is_err:
                    _log.warning(
                        "3d backend: assembly %s (%s) skipped: %s",
                        subject,
                        reg.format_id,
                        result.danger_err.message,
                    )
                    continue
                files.extend(result.danger_ok)

        _log.info("3d backend: emitted %d file(s)", len(files))
        return Ok(tuple(files))
