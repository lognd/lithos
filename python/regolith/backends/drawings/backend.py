"""`DrawingsBackend`: rides the WO-25 framework to emit the drawing set
(`DrawingModel` JSON + SVG + DXF + PDF + the audit report) for a
configured list of mech/fluid/civil subjects (WO-50 deliverable 2/3).

As of WO-99 the two hard-coded dispatch sites (the `model_for_spec`
if/elif ladder and the `files_for_model` renderer quintet) are gone: both
delegate to the :mod:`regolith.backends.registry` producer/renderer
registries. The public `model_for_spec`/`files_for_model` helpers stay
(preview and ship both call them), now thin wrappers over the default
registries, so a caller that does not care about custom registries or
format selection gets the historical byte-identical behaviour.

Mirrors `regolith.backends.mech.MechBackend`'s shape: a caller-supplied,
already-decided list of subjects to produce for (never invents which
subjects to draw -- regolith/07 sec. 6).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from regolith._schema.models import Annotation, DrawingModel
from regolith.backends.drawings.style import StyleRecord
from regolith.backends.framework import BackendInputs, OutputFile
from regolith.backends.registry import (
    ProducerRegistry,
    RendererRegistry,
    default_producer_registry,
    default_renderer_registry,
    model_for_spec_via,
    render_files_for_model,
)
from regolith.errors import BackendError
from regolith.logging_setup import get_logger

_log = get_logger(__name__)


class DrawingSpec(BaseModel):
    """One drawing to produce: a subject and which producer track reads
    it (`"mech"` reads `BackendInputs.geometry`, `"fluid"` reads
    `.flownets`, `"civil"` reads `.frames`, `"elec_blocks"` reads
    `.harnesses`, WO-58 deliverable 1; `"contract_graph"` reads the
    single `.contract_graph` (WO-61 deliverable 3); `"opt_trace"` reads
    `.opt_traces`, WO-58 deliverable 4; `"si"` reads `.si_rows`, the
    WO-78 SI table sheet). The set of valid tracks is now exactly the
    producer registry's registered kinds (WO-99).
    """

    model_config = ConfigDict(frozen=True)

    subject: str
    track: str


def model_for_spec(
    spec: DrawingSpec,
    inputs: BackendInputs,
    *,
    producers: ProducerRegistry | None = None,
) -> Result[DrawingModel, BackendError]:
    """Run the ONE per-track producer dispatch (D197: the shared
    producer set `regolith ship` and `regolith preview` both call) and
    return the raw `DrawingModel`, before any file is rendered.

    ``producers`` defaults to the built-in registry
    (:func:`regolith.backends.registry.default_producer_registry`);
    passing a custom registry lets a caller (or a plugin-composed
    registry) add producer kinds with ZERO edits here.
    """
    registry = producers if producers is not None else default_producer_registry()
    return model_for_spec_via(spec.track, spec.subject, inputs, registry)


def stamp_model(model: DrawingModel, stamp_text: str) -> DrawingModel:
    """D197's honesty stamp, applied THROUGH the model (never by
    post-editing a rendered SVG/DXF/PDF): every sheet gets one extra
    `Annotation` carrying ``stamp_text`` (``"PREVIEW -- NOT RELEASED:
    <n> unresolved"`` or ``"RELEASE-CLEAN"``, see `GateSummary
    .stamp_text`), anchored well clear of any producer's own content
    (``[-20.0, -20.0]``, ahead of every producer's `[0, 0]`-rooted
    layout) so it never trips the drafting audit's no-overlap rule.
    `Sheet`/`DrawingModel` are frozen pydantic models -- `model_copy`
    rebuilds each one with the stamp appended, everything else
    byte-identical to what the producer returned.
    """
    stamp = Annotation(
        text=stamp_text,
        anchor=[-20.0, -20.0],
        text_height_mm=5.0,
        datum_refs=[],
        per=None,
    )
    stamped_sheets = [
        sheet.model_copy(update={"annotations": [stamp, *sheet.annotations]})
        for sheet in model.sheets
    ]
    return model.model_copy(update={"sheets": stamped_sheets})


def files_for_model(
    subject: str,
    model: DrawingModel,
    *,
    renderers: RendererRegistry | None = None,
    formats: tuple[str, ...] | None = None,
    style: StyleRecord | None = None,
) -> tuple[OutputFile, ...]:
    """The `<subject>.drawing.json` + `.svg` + `.dxf` + `.pdf` +
    `.explain.txt` file set for an already-built `DrawingModel`, under
    `drawings/` -- the ONE rendering tail both `DrawingsBackend.produce`
    and the preview driver call.

    ``renderers`` defaults to the built-in registry
    (:func:`regolith.backends.registry.default_renderer_registry`);
    ``formats`` (a project's ``[artifacts] formats`` selection) narrows
    the emitted set. ``formats=None`` renders every registered drawing
    format -- goldens byte-identical to the pre-registry quintet.
    ``style`` (WO-99 D7) is the resolved project ``[style]`` pack;
    ``None`` renders with the neutral default (byte-identical).
    """
    registry = renderers if renderers is not None else default_renderer_registry()
    return render_files_for_model(
        subject, model, registry, formats=formats, style=style
    )


class DrawingsBackend:
    """Produces `drawings/<subject>.drawing.json` + `.svg` + `.dxf` +
    `.pdf` + `.explain.txt` for every configured `DrawingSpec`, dispatched
    through the WO-99 producer/renderer registries.
    """

    def __init__(
        self,
        specs: tuple[DrawingSpec, ...],
        *,
        producers: ProducerRegistry | None = None,
        renderers: RendererRegistry | None = None,
        formats: tuple[str, ...] | None = None,
        style: StyleRecord | None = None,
        project: str = "",
    ) -> None:
        """Bind the sorted (by subject) list of drawings to produce plus
        the registries/format selection (built-ins + all formats by
        default -- goldens byte-identical). ``style`` (WO-99 D7) is the
        resolved project ``[style]`` pack; ``None`` = neutral default.
        ``project`` (WO-130, D244.2) roots the emitted
        `<subject>.edit_model.json`'s override targets (the WO-129
        dotted `design.subject.slot` shape); an empty default keeps
        every pre-WO-130 call site working (the CLI passes the real
        project id)."""
        self._specs = tuple(sorted(specs, key=lambda s: s.subject))
        self._producers = (
            producers if producers is not None else default_producer_registry()
        )
        self._renderers = (
            renderers if renderers is not None else default_renderer_registry()
        )
        self._formats = formats
        self._style = style
        self._project = project

    def produce(
        self, inputs: BackendInputs
    ) -> Result[tuple[OutputFile, ...], BackendError]:
        """Emit every configured drawing's rendered file set.

        WO-123/charter 41 sec. 4 (D238.1): the drafting audit is GATING
        on this, the ship path's drawing producer -- a model that fails
        any drafting rule (style-less or geometry-measured) REFUSES the
        whole ship with a named diagnostic before any file is written
        for that subject, rather than shipping and only warning.

        WO-130 (D244.2): beside the rendered file set, each subject
        gets its `<subject>.edit_model.json` -- the annotation-anchor
        edit model (`regolith.backends.edit_models.drawing_edit_model`).
        """
        from regolith.backends.drawings.audit import assert_ship_ready
        from regolith.backends.edit_models import drawing_edit_model

        files: list[OutputFile] = []
        for spec in self._specs:
            model_result = model_for_spec(spec, inputs, producers=self._producers)
            if model_result.is_err:
                return Err(model_result.danger_err)
            model = model_result.danger_ok
            gate_error = assert_ship_ready(model, spec.subject, self._style)
            if gate_error is not None:
                return Err(gate_error)
            files.extend(
                render_files_for_model(
                    spec.subject,
                    model,
                    self._renderers,
                    formats=self._formats,
                    style=self._style,
                )
            )
            edit_model = drawing_edit_model(self._project, spec.subject, model.sheets)
            files.append(
                OutputFile.of(
                    f"{spec.subject}.edit_model.json",
                    edit_model.model_dump_json(indent=2).encode("ascii"),
                )
            )
        _log.info("drawings backend: emitted %d file(s)", len(files))
        return Ok(tuple(files))
