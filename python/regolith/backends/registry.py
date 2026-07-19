"""Producer + renderer registries -- the ONE dispatch seam (WO-99, charter 38 sec. 1.2).

Kills the two hard-coded dispatch sites of the first-generation emission
pipeline: the `model_for_spec` if/elif ladder (now a
:class:`ProducerRegistry` lookup) and the `files_for_model` renderer
quintet (now a :class:`RendererRegistry` walk). Built-in producers and
renderers register through the SAME API a third-party ``renderer``-kind
plugin uses (:mod:`regolith.backends.renderer_plugin`, AD-26); adding an
artifact kind or an output format is ONE registration, ZERO edits to a
dispatch site. Duplicate ids are a loud typed error, never silent
last-wins shadowing.

The realized-IR renderer family (GLB, HTML viewer, real KiCad -- WO-100/
WO-101) registers its renderers into this same :class:`RendererRegistry`
keyed by a distinct ``over`` family, so those WOs are pure registrations
too; this WO ships only the ``DrawingModel`` family (the existing
svg/dxf/pdf/json/explain set) plus the seam.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from typani.result import Err, Ok, Result

from regolith._schema.models import DrawingModel, RealizedAssembly, RealizedGeometry
from regolith.backends.artifacts import NativeArtifactStore
from regolith.backends.framework import BackendInputs, OutputFile
from regolith.errors import BackendError
from regolith.logging_setup import get_logger

if TYPE_CHECKING:
    from regolith.backends.drawings.style import StyleRecord

# NOTE: the concrete producer/renderer callables live in
# `regolith.backends.drawings.*`, whose package `__init__` imports
# `DrawingsBackend`, which imports THIS module -- so importing those
# submodules at module load would be a cycle. They are imported lazily
# (function-body imports; the module cache makes the repeat cost nil)
# inside the built-in wrappers and the `default_*_registry` factories.

_log = get_logger(__name__)

# A producer turns (subject, inputs) into a `DrawingModel` (or a named
# `BackendError` when the subject's input IR is absent). It is the unit
# the `ProducerRegistry` dispatches on -- one per subject kind.
Producer = Callable[[str, BackendInputs], Result[DrawingModel, BackendError]]

# The auto-derivation half of a producer registration: which subjects
# `auto_specs` should draw with NO `--spec` (every one straight from the
# build's own realized inputs, never invented -- regolith/07 sec. 6).
SubjectSource = Callable[[BackendInputs], Iterable[str]]

# A renderer turns ONE model (plus a resolved `StyleRecord`, WO-99 D7) into
# one artifact file's bytes. The parameters are `...` because the registry
# is heterogeneous by design: each `over` family's renderers consume that
# family's own IR (`DrawingModel` for `DRAWING_FAMILY`, `BomModel` for the
# WO-101 `bom` family, ...) and the style arg is optional per renderer. A
# single family-agnostic dispatch site (`for_family`) walks them all, so
# the callable type cannot name one concrete signature.
DrawingRenderer = Callable[..., bytes]

# The family id the `DrawingModel` renderers register under; the realized-
# IR renderer families (WO-100/101) use their own family strings.
# frob:doc docs/modules/py-backends.md#backends-registry
DRAWING_FAMILY = "drawing"

# WO-100: the realized-IR renderer families. Their renderers do NOT
# consume a `DrawingModel` (they project/tessellate a `RealizedGeometry`
# or `RealizedAssembly` straight from the pinned native bytes), so they
# carry their own callable shape and their own family keys -- registered
# into the SAME `RendererRegistry` (this module docstring's promise) via
# :meth:`RendererRegistry.register_realized`, never mixed into the
# `DrawingModel` walk `files_for_model` drives.
# frob:doc docs/modules/py-backends.md#backends-registry
THREE_D_PART_FAMILY = "3d.part"
# frob:doc docs/modules/py-backends.md#backends-registry
THREE_D_ASSEMBLY_FAMILY = "3d.assembly"

# One realized-IR renderer: (subject, IR, native store) -> a coupled set
# of artifact files (the 3D family emits a GLB + its self-contained
# viewer as one unit), or a named `BackendError` when the native bytes
# are absent / OCP is unavailable on the host.
RealizedSubject = RealizedGeometry | RealizedAssembly
RealizedRenderer = Callable[
    [str, RealizedSubject, NativeArtifactStore],
    Result[tuple[OutputFile, ...], BackendError],
]


# frob:doc docs/modules/py-backends.md#backends-registry
@dataclass(frozen=True)
class ProducerRegistration:
    """One subject kind's producer plus its auto-derivable subject source.

    ``kind`` is the drawing track string (``"mech"``/``"fluid"``/...);
    ``produce`` is the ONE dispatch target `model_for_spec` looks up;
    ``subjects`` enumerates the auto-derivable subjects for `auto_specs`
    (empty for caller-only kinds like ``opt_trace``).
    """

    kind: str
    produce: Producer
    subjects: SubjectSource


# frob:doc docs/modules/py-backends.md#backends-registry
@dataclass(frozen=True)
class RendererRegistration:
    """One output format over one model family.

    ``format_id`` is the config-selectable id (``"svg"``, ``"json"``,
    ...); ``suffix`` is the artifact filename tail
    (``<subject>.<suffix>``); ``over`` is the model family the renderer
    consumes (:data:`DRAWING_FAMILY` for this WO's set); ``render`` turns
    the model into the file's bytes.
    """

    format_id: str
    suffix: str
    over: str
    render: DrawingRenderer


# frob:doc docs/modules/py-backends.md#backends-registry
@dataclass(frozen=True)
class RealizedRendererRegistration:
    """One realized-IR renderer (WO-100): ``format_id`` is the config-
    selectable id (``"glb"``); ``over`` is the realized family it consumes
    (:data:`THREE_D_PART_FAMILY` / :data:`THREE_D_ASSEMBLY_FAMILY`);
    ``render`` turns the subject + native store into its coupled file set.
    """

    format_id: str
    over: str
    render: RealizedRenderer


# frob:doc docs/modules/py-backends.md#backends-registry
class ProducerRegistry:
    """Subject kind -> producer, with loud-on-duplicate registration.

    The registration API `model_for_spec` reads and the ``renderer``-kind
    plugin seam writes are the same one: :meth:`register`. A duplicate
    kind is an `Err` value (never a silent shadow of a built-in).
    """

    def __init__(self) -> None:
        """Start empty; built-ins are added via :func:`default_producer_registry`."""
        self._by_kind: dict[str, ProducerRegistration] = {}

    # frob:doc docs/modules/py-backends.md#backends-registry
    def register(self, registration: ProducerRegistration) -> Result[None, str]:
        """Add ``registration``; `Err` (never overwrite) on a duplicate kind."""
        if registration.kind in self._by_kind:
            _log.warning(
                "producer registry: duplicate kind %r rejected LOUDLY",
                registration.kind,
            )
            return Err(registration.kind)
        self._by_kind[registration.kind] = registration
        _log.debug("producer registry: registered kind %r", registration.kind)
        return Ok(None)

    # frob:doc docs/modules/py-backends.md#backends-registry
    def get(self, kind: str) -> ProducerRegistration | None:
        """The registration for ``kind``, or ``None`` if unregistered."""
        return self._by_kind.get(kind)

    # frob:doc docs/modules/py-backends.md#backends-registry
    def kinds(self) -> tuple[str, ...]:
        """Every registered kind, in registration order (deterministic)."""
        return tuple(self._by_kind)

    # frob:doc docs/modules/py-backends.md#backends-registry
    def registrations(self) -> tuple[ProducerRegistration, ...]:
        """Every registration, in registration order (drives `auto_specs`)."""
        return tuple(self._by_kind.values())


# frob:doc docs/modules/py-backends.md#backends-registry
class RendererRegistry:
    """Format id -> renderer, keyed per model family, loud on duplicate.

    `files_for_model` walks the :data:`DRAWING_FAMILY` renderers whose
    ``format_id`` the project selected (all built-ins by default). The
    realized-IR families (WO-100/101) coexist here under their own family
    keys without touching the drawing walk.
    """

    def __init__(self) -> None:
        """Start empty; built-ins are added via :func:`default_renderer_registry`."""
        self._by_family: dict[str, dict[str, RendererRegistration]] = {}
        # WO-100: the realized-IR renderer families live beside the
        # `DrawingModel` families in the SAME registry object, keyed by
        # their own family strings, so `files_for_model`'s drawing walk
        # never sees them and a 3D renderer is still a plain registration.
        self._by_realized: dict[str, dict[str, RealizedRendererRegistration]] = {}

    # frob:doc docs/modules/py-backends.md#backends-registry
    def register(self, registration: RendererRegistration) -> Result[None, str]:
        """Add ``registration``; `Err` (never overwrite) on a duplicate id."""
        family = self._by_family.setdefault(registration.over, {})
        if registration.format_id in family:
            _log.warning(
                "renderer registry: duplicate format %r (family %r) rejected LOUDLY",
                registration.format_id,
                registration.over,
            )
            return Err(f"{registration.over}:{registration.format_id}")
        family[registration.format_id] = registration
        _log.debug(
            "renderer registry: registered format %r (family %r)",
            registration.format_id,
            registration.over,
        )
        return Ok(None)

    # frob:doc docs/modules/py-backends.md#backends-registry
    def for_family(self, family: str) -> tuple[RendererRegistration, ...]:
        """Every renderer of ``family``, in registration order."""
        return tuple(self._by_family.get(family, {}).values())

    # frob:doc docs/modules/py-backends.md#backends-registry
    def formats(self, family: str = DRAWING_FAMILY) -> tuple[str, ...]:
        """Every registered format id of ``family`` (default: drawing)."""
        return tuple(self._by_family.get(family, {}))

    # frob:doc docs/modules/py-backends.md#backends-registry
    def register_realized(
        self, registration: RealizedRendererRegistration
    ) -> Result[None, str]:
        """Add a realized-IR renderer (WO-100); `Err` on a duplicate id
        within its family (never a silent shadow, same discipline as the
        drawing renderers)."""
        family = self._by_realized.setdefault(registration.over, {})
        if registration.format_id in family:
            _log.warning(
                "renderer registry: duplicate realized format %r (family %r) "
                "rejected LOUDLY",
                registration.format_id,
                registration.over,
            )
            return Err(f"{registration.over}:{registration.format_id}")
        family[registration.format_id] = registration
        _log.debug(
            "renderer registry: registered realized format %r (family %r)",
            registration.format_id,
            registration.over,
        )
        return Ok(None)

    # frob:doc docs/modules/py-backends.md#backends-registry
    def for_realized_family(
        self, family: str
    ) -> tuple[RealizedRendererRegistration, ...]:
        """Every realized-IR renderer of ``family``, in registration order."""
        return tuple(self._by_realized.get(family, {}).values())


# --- WO-130: the universal artifact surface (D244/AD-41, charter 42 secs.
# 6-7) -- the viewer vocabulary + the family->viewer registry, kept
# BESIDE the producer/renderer registrations above (one home, AD-41
# ruling 2). A family landing without a viewer hint is a loud
# registration error (the `ArtifactFamilyRegistry.register` duplicate/
# missing discipline mirrors the two registries above), never a silent
# gap a consumer discovers by falling through a hardcoded family list
# (F145).

#: The CLOSED viewer vocabulary (charter 42 sec. 6). A consumer that
#: understands none of these still has the honest fallback ladder
#: (`table`/`json`/`text`/`binary`) -- there is always something
#: truthful to render.
Viewer = Literal[
    "svg", "raster", "gerber", "glb", "table", "markdown", "json", "text", "binary"
]


# frob:doc docs/modules/py-backends.md#backends-registry
@dataclass(frozen=True)
class PathPattern:
    """One relpath-narrowing rule (WO-161, AD-46): the per-file
    classification data that used to live in
    :func:`regolith.backends.artifact_index.classify`'s hand-written
    if/elif ladder, now carried as DATA on the family's own
    registration.

    A file matches this pattern iff ``contains`` (empty string matches
    any relpath) is a substring of ``f"/{relpath}"`` AND (when ``exts``
    is non-empty) the file's lowercase extension is a member of
    ``exts``. ``kind`` may reference ``{stem}`` (the filename with
    ``strip_prefix`` removed from its front and its extension stripped)
    for a per-file kind label (e.g. ``"gerber_layer.{stem}"``).
    ``viewer`` of ``None`` means "the family's own default viewer hint
    already describes this file honestly" (the caller applies the
    family default in that case), matching `classify`'s old
    ``viewer_override`` contract exactly.
    """

    contains: str
    exts: frozenset[str]
    kind: str
    viewer: Viewer | None
    media_type: str
    strip_prefix: str = ""


# frob:doc docs/modules/py-backends.md#backends-registry
@dataclass(frozen=True)
class ArtifactFamilyRegistration:
    """One artifact family's DEFAULT viewer hint plus its per-file
    classification rules (``path_patterns``, WO-161): every family MUST
    carry a default viewer so an unclassified file in it still resolves
    honestly, and ``path_patterns`` narrows individual files whose kind
    does not match the family default (e.g. a board family defaults to
    ``gerber`` but its ``board_status.json`` is a ``json`` file).
    ``path_patterns`` is matched in order; the built-in registrations
    always end with a catch-all pattern so a known family never fails
    to classify a file (charter 42 sec. 6's honest fallback ladder)."""

    family: str
    viewer: Viewer
    path_patterns: tuple[PathPattern, ...] = ()


# frob:doc docs/modules/py-backends.md#backends-registry
class ArtifactFamilyRegistry:
    """Family -> default viewer hint, with the SAME loud-on-duplicate
    discipline as :class:`ProducerRegistry`/:class:`RendererRegistry`."""

    def __init__(self) -> None:
        """Start empty; built-ins are added via
        :func:`default_artifact_family_registry`."""
        self._by_family: dict[str, ArtifactFamilyRegistration] = {}

    # frob:doc docs/modules/py-backends.md#backends-registry
    def register(self, registration: ArtifactFamilyRegistration) -> Result[None, str]:
        """Add ``registration``; `Err` (never overwrite) on a duplicate family."""
        if registration.family in self._by_family:
            _log.warning(
                "artifact family registry: duplicate family %r rejected LOUDLY",
                registration.family,
            )
            return Err(registration.family)
        self._by_family[registration.family] = registration
        _log.debug(
            "artifact family registry: registered family %r -> viewer %r",
            registration.family,
            registration.viewer,
        )
        return Ok(None)

    # frob:doc docs/modules/py-backends.md#backends-registry
    def get(self, family: str) -> ArtifactFamilyRegistration | None:
        """The registration for ``family``, or ``None`` if unregistered
        (a REGISTRATION ERROR at the artifact-index build site -- see
        :func:`regolith.backends.artifact_index.build_index`, which
        turns a ``None`` here into a loud `BackendError`, never a
        silent gap)."""
        return self._by_family.get(family)

    # frob:doc docs/modules/py-backends.md#backends-registry
    def families(self) -> tuple[str, ...]:
        """Every registered family, in registration order (deterministic)."""
        return tuple(self._by_family)


# --- WO-161: path_patterns data, replacing `classify()`'s if/elif ladder --

#: Extension -> (kind, viewer override or None [use the family default],
#: media type) -- the EXACT table `artifact_index.classify` used to hold
#: (deliberately conservative: an extension not in the CLOSED viewer
#: vocabulary resolves to the honest fallback ladder member closest to
#: true rather than a fabricated richer viewer). Shared by every family
#: as its common baseline (`_COMMON_PATH_PATTERNS`).
_EXT_CLASSIFY: dict[str, tuple[str, Viewer | None, str]] = {
    ".svg": ("svg", "svg", "image/svg+xml"),
    ".dxf": ("dxf", "text", "image/vnd.dxf"),
    ".pdf": ("pdf", "binary", "application/pdf"),
    ".json": ("json", "json", "application/json"),
    ".md": ("markdown", "markdown", "text/markdown"),
    ".csv": ("csv", "table", "text/csv"),
    ".glb": ("glb", "glb", "model/gltf-binary"),
    ".html": ("html", "text", "text/html"),
    ".step": ("step", "binary", "model/step"),
    ".kicad_pcb": ("kicad_pcb", "text", "text/plain"),
    ".v": ("hdl_source", "text", "text/plain"),
    ".sv": ("hdl_source", "text", "text/plain"),
    ".vh": ("hdl_source", "text", "text/plain"),
    ".elf": ("elf", "binary", "application/x-elf"),
    ".bin": ("firmware_image", "binary", "application/octet-stream"),
    ".h": ("source", "text", "text/plain"),
    ".c": ("source", "text", "text/plain"),
    ".txt": ("text", "text", "text/plain"),
    ".sigrok-cli": ("capture_config", "text", "text/plain"),
}

#: Gerber X2 layer suffixes (WO-124's `GERBER_LAYER_FILES`) -- stable
#: Gerber X2/RS-274X convention, the ``boards`` family's own pattern set
#: (below) narrows these before the common extension table ever runs.
_GERBER_LAYER_EXT = frozenset(
    {".gtl", ".gbl", ".gts", ".gbs", ".gtp", ".gbp", ".gto", ".gbo", ".gm1", ".gbr"}
)

#: Every family's baseline pattern set (WO-161 deliverable 3): the old
#: `classify()` extension table, plus a catch-all last entry so a known
#: family's file always classifies (the honest `file`/`binary` fallback
#: `classify()` returned when no extension mapped).
_COMMON_PATH_PATTERNS: tuple[PathPattern, ...] = tuple(
    PathPattern(
        contains="", exts=frozenset({ext}), kind=kind, viewer=viewer, media_type=media
    )
    for ext, (kind, viewer, media) in _EXT_CLASSIFY.items()
) + (
    PathPattern(
        contains="",
        exts=frozenset(),
        kind="file",
        viewer="binary",
        media_type="application/octet-stream",
    ),
)

#: The ``boards`` family's own patterns (WO-161 deliverable 1
#: enumeration: the two relpath-specific rules `classify()` hand-dispatched
#: for boards, run BEFORE the common baseline so a `.gbrjob`/gerber-layer/
#: drill file never falls through to the generic extension table).
_BOARDS_PATH_PATTERNS: tuple[PathPattern, ...] = (
    PathPattern(
        contains="/gerbers/",
        exts=frozenset({".gbrjob"}),
        kind="job_file",
        viewer="json",
        media_type="application/json",
    ),
    PathPattern(
        contains="/gerbers/",
        exts=_GERBER_LAYER_EXT,
        kind="gerber_layer.{stem}",
        viewer=None,
        media_type="application/vnd.gerber",
        strip_prefix="board-",
    ),
    PathPattern(
        contains="/drill/",
        exts=frozenset(),
        kind="drill.{stem}",
        viewer=None,
        media_type="application/vnd.excellon-drill",
        strip_prefix="board-",
    ),
)


# frob:doc docs/modules/py-backends.md#backends-registry
def match_path_pattern(
    relpath: str, registration: ArtifactFamilyRegistration
) -> tuple[str, Viewer | None, str] | None:
    """``(kind, viewer_override, media_type)`` for ``relpath`` under
    ``registration``'s ``path_patterns``, walked in order; ``None`` if
    NOTHING matched (a registration missing its common baseline, e.g. a
    hand-built test registry -- a REGISTRATION ERROR at the artifact-
    index build site, mirroring the old unregistered-family error, see
    :func:`regolith.backends.artifact_index.build_index`)."""
    name = relpath.rsplit("/", 1)[-1]
    _, ext = os.path.splitext(name)
    ext = ext.lower()
    haystack = f"/{relpath}"
    for pattern in registration.path_patterns:
        if pattern.contains and pattern.contains not in haystack:
            continue
        if pattern.exts and ext not in pattern.exts:
            continue
        kind = pattern.kind
        if "{stem}" in kind:
            stem = name.removeprefix(pattern.strip_prefix)
            stem = stem[: -len(ext)] if ext else stem
            kind = kind.format(stem=stem)
        return kind, pattern.viewer, pattern.media_type
    return None


# frob:doc docs/modules/py-backends.md#backends-registry
def default_artifact_family_registry() -> ArtifactFamilyRegistry:
    """The thirteen landed families' default viewer hints (WO-130
    deliverable 2): every family `package.FAMILY_DIRS` names, plus
    ``ledgers`` for the top-level package side files (`manifest.json`,
    `index.md`, the gate/parity/acceptance ledgers, and this WO's own
    `artifact_index.json`) which carry no family directory of their own.

    Defaults are the family's TYPICAL content; the per-file classifier
    (:mod:`regolith.backends.artifact_index`) narrows individual files
    whose kind does not match (e.g. `boards/board_status.json` is
    `json`, not `gerber`) -- narrowing is never a silent gap because the
    family default always resolves first.
    """
    registry = ArtifactFamilyRegistry()
    builtins: tuple[tuple[str, Viewer], ...] = (
        ("drawings", "svg"),
        ("calc", "table"),
        ("boards", "gerber"),
        ("3d", "glb"),
        ("bom", "table"),
        ("cost", "table"),
        # F-WO130-5: `MechBackend`'s own package (STEP models + its own
        # bom.csv/json + fab_notes.json), landed under the CLI's
        # `builtin_backends["mech"]` key without ever joining
        # `package.FAMILY_DIRS` -- closed in this same change (binary
        # default for the STEP models; the classifier narrows the CSV/
        # JSON siblings to `table`/`json`).
        ("mech", "binary"),
        ("firmware", "binary"),
        ("hdl", "text"),
        ("instructions", "markdown"),
        ("harness", "markdown"),
        ("evidence", "json"),
        ("ledgers", "json"),
        # WO-165 (AD-47 sec. 5, D268 item 3): the perf-board program's
        # two families -- the human-followable wiring map (an svg
        # default, the same `DrawingModel` -> svg path every drawing
        # family uses) and the wire cut list (a table default: a CSV
        # bill of wire lengths by gauge plus a board-dimensions JSON
        # sibling, both narrowed by the common extension baseline).
        ("wiring_map", "svg"),
        ("cutlist", "table"),
        # WO-166 (AD-47 sec. 5, D268 item 1): the wire-EDM die-set
        # program's two families -- the profile-cut DXF-plus-metadata
        # output (an svg-renderer-family default since it rides the
        # same `DrawingModel` projection every drawing family uses,
        # narrowed to the .dxf extension by the common baseline) and
        # the die-set assembly's own check-result/summary package (a
        # table default: JSON/CSV check reports, narrowed by the
        # common extension baseline).
        ("edm_profile", "svg"),
        ("die_set", "table"),
        # WO-167 (AD-47 sec. 5, D268 item 4): the dwelling/house-wiring
        # program's two families -- the cable schedule (one row per
        # branch circuit, a table default narrowed by the common
        # extension baseline) and the panel schedule (breaker-slot/
        # load rows plus the panel siting verdict, same table default).
        ("cable_schedule", "table"),
        ("panel_schedule", "table"),
    )
    for family, viewer in builtins:
        patterns = (
            _BOARDS_PATH_PATTERNS + _COMMON_PATH_PATTERNS
            if family == "boards"
            else _COMMON_PATH_PATTERNS
        )
        result = registry.register(
            ArtifactFamilyRegistration(family, viewer, path_patterns=patterns)
        )
        assert result.is_ok, f"built-in artifact family collision: {family}"
    return registry


# --- built-in producers -------------------------------------------------


def _mech(subject: str, inputs: BackendInputs) -> Result[DrawingModel, BackendError]:
    # WO-100: the mech producer now PROJECTS the pinned STEP bytes (real
    # HLR multi-view drawing) instead of drawing a bbox rectangle; it
    # degrades to the LOUDLY-annotated bbox stand-in when the bytes or
    # OCP are unavailable (`project.mech_part_projected_drawing`'s own
    # fallback), so this dispatch site never crashes on a bytes-less
    # subject and never needs a second branch here.
    from regolith.backends.drawings.project import mech_part_projected_drawing

    geometry = inputs.geometry.get(subject)
    if geometry is None:
        _log.warning("drawings: no realized geometry for %s", subject)
        return Err(
            BackendError(
                kind="geometry_ir_unavailable",
                message=f"no RealizedGeometry supplied for subject {subject!r}",
            )
        )
    return Ok(mech_part_projected_drawing(subject, geometry, inputs.native))


def _fluid(subject: str, inputs: BackendInputs) -> Result[DrawingModel, BackendError]:
    from regolith.backends.drawings.producers import fluid_pid

    flownet = inputs.flownets.get(subject)
    if flownet is None:
        _log.warning("drawings: no flownet payload for %s", subject)
        return Err(
            BackendError(
                kind="flownet_ir_unavailable",
                message=f"no FlownetPayload supplied for subject {subject!r}",
            )
        )
    return Ok(fluid_pid(subject, flownet))


def _civil(subject: str, inputs: BackendInputs) -> Result[DrawingModel, BackendError]:
    from regolith.backends.drawings.producers import civil_plan_section

    frame = inputs.frames.get(subject)
    if frame is None:
        _log.warning("drawings: no frame payload for %s", subject)
        return Err(
            BackendError(
                kind="frame_ir_unavailable",
                message=f"no FramePayload supplied for subject {subject!r}",
            )
        )
    return Ok(civil_plan_section(subject, frame))


def _elec_blocks(
    subject: str, inputs: BackendInputs
) -> Result[DrawingModel, BackendError]:
    from regolith.backends.drawings.producers import elec_blocks

    harness = inputs.harnesses.get(subject)
    if harness is None:
        _log.warning("drawings: no harness payload for %s", subject)
        return Err(
            BackendError(
                kind="harness_ir_unavailable",
                message=f"no HarnessPayload supplied for subject {subject!r}",
            )
        )
    return Ok(elec_blocks(subject, harness))


def _contract_graph(
    subject: str, inputs: BackendInputs
) -> Result[DrawingModel, BackendError]:
    from regolith.backends.drawings.producers import (
        contract_graph as contract_graph_producer,
    )

    graph = inputs.contract_graph
    if graph is None:
        _log.warning("drawings: no contract graph payload for %s", subject)
        return Err(
            BackendError(
                kind="contract_graph_ir_unavailable",
                message=f"no ContractGraphPayload supplied for subject {subject!r}",
            )
        )
    return Ok(contract_graph_producer(subject, graph))


def _si(subject: str, inputs: BackendInputs) -> Result[DrawingModel, BackendError]:
    from regolith.backends.drawings.producers import si_table

    rows = inputs.si_rows.get(subject)
    if rows is None:
        _log.warning("drawings: no SI rows for %s", subject)
        return Err(
            BackendError(
                kind="si_rows_unavailable",
                message=f"no SI table rows derived for subject {subject!r}",
            )
        )
    return Ok(si_table(subject, rows))


def _opt_trace(
    subject: str, inputs: BackendInputs
) -> Result[DrawingModel, BackendError]:
    from regolith.backends.drawings.producers import (
        opt_trace as opt_trace_producer,
    )

    trace = inputs.opt_traces.get(subject)
    if trace is None:
        _log.warning("drawings: no optimization trace for %s", subject)
        return Err(
            BackendError(
                kind="opt_trace_ir_unavailable",
                message=f"no OptimizationTrace supplied for subject {subject!r}",
            )
        )
    return Ok(opt_trace_producer(subject, trace))


# frob:doc docs/modules/py-backends.md#backends-registry
def default_producer_registry() -> ProducerRegistry:
    """The eight built-in producers (mech/fluid/civil/elec_blocks/
    contract_graph/si/opt_trace), registered in the historical
    `model_for_spec` order so `auto_specs` derivation is deterministic.
    """
    registry = ProducerRegistry()
    builtins = (
        ProducerRegistration("mech", _mech, lambda i: sorted(i.geometry)),
        ProducerRegistration("fluid", _fluid, lambda i: sorted(i.flownets)),
        ProducerRegistration("civil", _civil, lambda i: sorted(i.frames)),
        ProducerRegistration(
            "elec_blocks", _elec_blocks, lambda i: sorted(i.harnesses)
        ),
        ProducerRegistration("si", _si, lambda i: sorted(i.si_rows)),
        ProducerRegistration(
            "contract_graph",
            _contract_graph,
            lambda i: ("contract_graph",) if i.contract_graph is not None else (),
        ),
        ProducerRegistration("opt_trace", _opt_trace, lambda _i: ()),
    )
    for registration in builtins:
        result = registry.register(registration)
        assert result.is_ok, f"built-in producer collision: {registration.kind}"
    return registry


# --- built-in renderers -------------------------------------------------


def _render_json(model: DrawingModel, style: StyleRecord | None = None) -> bytes:
    # `style` accepted for a uniform renderer signature (WO-99 D7); JSON is
    # the model's own bytes and carries no drafting aesthetics to restyle.
    del style
    return model.model_dump_json(by_alias=True).encode("utf-8")


def _render_explain(model: DrawingModel, style: StyleRecord | None = None) -> bytes:
    from regolith.backends.drawings.audit import explain_report

    del style  # explain text is structural, not styled (WO-99 D7).
    return explain_report(model).encode("ascii")


# frob:doc docs/modules/py-backends.md#backends-registry
def default_renderer_registry() -> RendererRegistry:
    """The five built-in `DrawingModel` formats (json/svg/dxf/pdf/explain),
    registered in the historical `files_for_model` order so the emitted
    file set is byte-identical to the pre-registry pipeline.
    """
    from regolith.backends.drawings.renderer import render_svg
    from regolith.backends.drawings.renderer_dxf import render_dxf
    from regolith.backends.drawings.renderer_pdf import render_pdf

    registry = RendererRegistry()
    builtins = (
        RendererRegistration("json", "drawing.json", DRAWING_FAMILY, _render_json),
        RendererRegistration("svg", "svg", DRAWING_FAMILY, render_svg),
        RendererRegistration("dxf", "dxf", DRAWING_FAMILY, render_dxf),
        RendererRegistration("pdf", "pdf", DRAWING_FAMILY, render_pdf),
        RendererRegistration("explain", "explain.txt", DRAWING_FAMILY, _render_explain),
    )
    for registration in builtins:
        result = registry.register(registration)
        assert result.is_ok, f"built-in renderer collision: {registration.format_id}"
    return registry


# frob:doc docs/modules/py-backends.md#backends-registry
def model_for_spec_via(
    kind: str,
    subject: str,
    inputs: BackendInputs,
    producers: ProducerRegistry,
) -> Result[DrawingModel, BackendError]:
    """Look ``kind`` up in ``producers`` and run it (the registry
    replacement for the `model_for_spec` if/elif ladder). An unregistered
    kind is the same ``unknown_drawing_track`` error the ladder returned.
    """
    registration = producers.get(kind)
    if registration is None:
        return Err(
            BackendError(
                kind="unknown_drawing_track",
                message=f"unknown drawing track {kind!r} for {subject!r}",
            )
        )
    return registration.produce(subject, inputs)


def _invoke_renderer(
    render: DrawingRenderer, model: DrawingModel, style: StyleRecord
) -> bytes:
    """Call a drawing renderer, threading ``style`` only when the callable
    accepts it (WO-99 D7). A pre-D7 or third-party renderer with the
    single-argument ``render(model)`` contract keeps working unchanged --
    the acceptance criterion that a toy renderer needs ZERO edits stands.
    """
    import inspect

    try:
        params = inspect.signature(render).parameters
    except (TypeError, ValueError):
        return render(model)
    accepts_style = len(params) >= 2 or any(
        p.kind is p.VAR_POSITIONAL or p.name == "style" for p in params.values()
    )
    return render(model, style) if accepts_style else render(model)


# frob:doc docs/modules/py-backends.md#backends-registry
def render_files_for_model(
    subject: str,
    model: DrawingModel,
    renderers: RendererRegistry,
    *,
    formats: tuple[str, ...] | None = None,
    style: StyleRecord | None = None,
) -> tuple[OutputFile, ...]:
    """Walk the drawing-family renderers (optionally filtered to
    ``formats``) and emit one ``drawings/<subject>.<suffix>`` file each --
    the registry replacement for the hard-coded `files_for_model` quintet.

    ``formats=None`` renders every registered drawing format (the default,
    goldens byte-identical); a project's ``[artifacts] formats`` list
    narrows it. ``style`` (WO-99 D7) is the resolved project ``[style]``
    pack threaded into every renderer; ``None`` resolves to the neutral
    default (byte-identical to the pre-style output). The drafting-audit
    warning is emitted once here, exactly as the pre-registry tail did.
    """
    from regolith.backends.drawings.audit import run_drafting_rules
    from regolith.backends.drawings.style import resolve_style

    resolved_style = resolve_style(style)
    selected = None if formats is None else set(formats)
    files: list[OutputFile] = []
    for registration in renderers.for_family(DRAWING_FAMILY):
        if selected is not None and registration.format_id not in selected:
            continue
        content = _invoke_renderer(registration.render, model, resolved_style)
        files.append(
            OutputFile.of(f"drawings/{subject}.{registration.suffix}", content)
        )
    failed = [r for r in run_drafting_rules(model) if not r.passed]
    if failed:
        _log.warning("drawings: %s failed %d drafting rule(s)", subject, len(failed))
    return tuple(files)
