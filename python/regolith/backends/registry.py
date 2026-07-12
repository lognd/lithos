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

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from typani.result import Err, Ok, Result

from regolith._schema.models import DrawingModel
from regolith.backends.framework import BackendInputs, OutputFile
from regolith.errors import BackendError
from regolith.logging_setup import get_logger

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

# A renderer over a `DrawingModel` turns it into one artifact file's bytes.
DrawingRenderer = Callable[[DrawingModel], bytes]

# The family id the `DrawingModel` renderers register under; the realized-
# IR renderer families (WO-100/101) use their own family strings.
DRAWING_FAMILY = "drawing"


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


class ProducerRegistry:
    """Subject kind -> producer, with loud-on-duplicate registration.

    The registration API `model_for_spec` reads and the ``renderer``-kind
    plugin seam writes are the same one: :meth:`register`. A duplicate
    kind is an `Err` value (never a silent shadow of a built-in).
    """

    def __init__(self) -> None:
        """Start empty; built-ins are added via :func:`default_producer_registry`."""
        self._by_kind: dict[str, ProducerRegistration] = {}

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

    def get(self, kind: str) -> ProducerRegistration | None:
        """The registration for ``kind``, or ``None`` if unregistered."""
        return self._by_kind.get(kind)

    def kinds(self) -> tuple[str, ...]:
        """Every registered kind, in registration order (deterministic)."""
        return tuple(self._by_kind)

    def registrations(self) -> tuple[ProducerRegistration, ...]:
        """Every registration, in registration order (drives `auto_specs`)."""
        return tuple(self._by_kind.values())


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

    def for_family(self, family: str) -> tuple[RendererRegistration, ...]:
        """Every renderer of ``family``, in registration order."""
        return tuple(self._by_family.get(family, {}).values())

    def formats(self, family: str = DRAWING_FAMILY) -> tuple[str, ...]:
        """Every registered format id of ``family`` (default: drawing)."""
        return tuple(self._by_family.get(family, {}))


# --- built-in producers -------------------------------------------------


def _mech(subject: str, inputs: BackendInputs) -> Result[DrawingModel, BackendError]:
    from regolith.backends.drawings.producers import mech_part_drawing

    geometry = inputs.geometry.get(subject)
    if geometry is None:
        _log.warning("drawings: no realized geometry for %s", subject)
        return Err(
            BackendError(
                kind="geometry_ir_unavailable",
                message=f"no RealizedGeometry supplied for subject {subject!r}",
            )
        )
    return Ok(mech_part_drawing(subject, geometry))


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


def _render_json(model: DrawingModel) -> bytes:
    return model.model_dump_json(by_alias=True).encode("utf-8")


def _render_explain(model: DrawingModel) -> bytes:
    from regolith.backends.drawings.audit import explain_report

    return explain_report(model).encode("ascii")


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


def render_files_for_model(
    subject: str,
    model: DrawingModel,
    renderers: RendererRegistry,
    *,
    formats: tuple[str, ...] | None = None,
) -> tuple[OutputFile, ...]:
    """Walk the drawing-family renderers (optionally filtered to
    ``formats``) and emit one ``drawings/<subject>.<suffix>`` file each --
    the registry replacement for the hard-coded `files_for_model` quintet.

    ``formats=None`` renders every registered drawing format (the default,
    goldens byte-identical); a project's ``[artifacts] formats`` list
    narrows it. The drafting-audit warning is emitted once here, exactly
    as the pre-registry tail did.
    """
    from regolith.backends.drawings.audit import run_drafting_rules

    selected = None if formats is None else set(formats)
    files: list[OutputFile] = []
    for registration in renderers.for_family(DRAWING_FAMILY):
        if selected is not None and registration.format_id not in selected:
            continue
        content = registration.render(model)
        files.append(
            OutputFile.of(f"drawings/{subject}.{registration.suffix}", content)
        )
    failed = [r for r in run_drafting_rules(model) if not r.passed]
    if failed:
        _log.warning("drawings: %s failed %d drafting rule(s)", subject, len(failed))
    return tuple(files)
