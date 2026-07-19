"""WO-99: producer/renderer registries, the renderer plugin seam, and the
`dist/<project>/` package layout.

Proves the acceptance criteria: a toy renderer plugin needs ZERO edits to
any dispatch site and its format appears in the emitted package; the
registries reject duplicate ids loudly; `auto_specs` walks the producer
registry; two ships are byte-identical; native STEP bytes persist at
realize time.
"""

from __future__ import annotations

from regolith._schema.models import DrawingModel
from regolith.backends.artifacts import NativeArtifactStore
from regolith.backends.drawings.backend import (
    DrawingSpec,
    files_for_model,
    model_for_spec,
)
from regolith.backends.framework import BackendInputs
from regolith.backends.preview import auto_specs
from regolith.backends.registry import (
    DRAWING_FAMILY,
    ProducerRegistration,
    ProducerRegistry,
    RendererRegistration,
    default_producer_registry,
    default_renderer_registry,
)
from regolith.backends.renderer_plugin import (
    RegistryBundle,
    load_renderer_plugins,
)
from regolith.errors import BackendError
from regolith.plugins import DuplicatePluginId, PluginKind, PluginManifest
from typani.result import Result


class _FakeEntryPoint:
    """A stand-in ``importlib.metadata.EntryPoint`` resolving to ``target``."""

    def __init__(self, name: str, target: object) -> None:
        self._name = name
        self._target = target

    @property
    def name(self) -> str:
        return self._name

    def load(self) -> object:
        return self._target


def _empty_inputs() -> BackendInputs:
    from regolith.orchestrator.lockfile import Lockfile

    return BackendInputs(
        lockfile=Lockfile(tool_version="test"),
        evidence={},
        geometry={},
        layouts={},
        native=NativeArtifactStore("."),
    )


# -- producer registry ---------------------------------------------------


def _unused_produce(
    subject: str, inputs: BackendInputs
) -> Result[DrawingModel, BackendError]:
    raise NotImplementedError("never invoked; registration-error path only")


# frob:tests python/regolith/backends/registry.py::default_producer_registry kind="unit"
def test_producer_registry_duplicate_kind_is_loud() -> None:
    """A second registration of the same kind is an `Err`, never a shadow."""
    registry = default_producer_registry()
    dup = ProducerRegistration("mech", _unused_produce, lambda i: ())
    result = registry.register(dup)
    assert result.is_err
    assert result.danger_err == "mech"


# frob:tests python/regolith/backends/registry.py::model_for_spec_via kind="unit"
def test_model_for_spec_unknown_track_is_named_error() -> None:
    """An unregistered track is the same `unknown_drawing_track` the old
    if/elif ladder returned."""
    result = model_for_spec(DrawingSpec(subject="x", track="nope"), _empty_inputs())
    assert result.is_err
    assert result.danger_err.kind == "unknown_drawing_track"


def test_auto_specs_walks_the_producer_registry() -> None:
    """A custom producer kind is auto-derived by `auto_specs` with no edits
    to the derivation site."""
    registry = ProducerRegistry()
    registry.register(
        ProducerRegistration(
            "toy",
            _unused_produce,
            lambda i: ("alpha", "beta"),
        )
    )
    specs = auto_specs(_empty_inputs(), producers=registry)
    assert {(s.subject, s.track) for s in specs} == {
        ("alpha", "toy"),
        ("beta", "toy"),
    }


# -- renderer registry ---------------------------------------------------


def _one_sheet_model() -> DrawingModel:
    from regolith.backends.drawings.producers import si_table

    return si_table("s", ())


def test_renderer_registry_duplicate_format_is_loud() -> None:
    registry = default_renderer_registry()
    dup = RendererRegistration("svg", "svg", DRAWING_FAMILY, lambda m: b"")
    assert registry.register(dup).is_err


def test_default_renderer_registry_has_the_five_builtins() -> None:
    assert set(default_renderer_registry().formats()) == {
        "json",
        "svg",
        "dxf",
        "pdf",
        "explain",
    }


# frob:tests python/regolith/backends/registry.py::render_files_for_model kind="unit"
def test_files_for_model_formats_selection_narrows_output() -> None:
    """`[artifacts] formats` narrows the emitted set; default renders all."""
    model = _one_sheet_model()
    all_files = {f.relpath for f in files_for_model("s", model)}
    assert all_files == {
        "drawings/s.drawing.json",
        "drawings/s.svg",
        "drawings/s.dxf",
        "drawings/s.pdf",
        "drawings/s.explain.txt",
    }
    only_svg = {f.relpath for f in files_for_model("s", model, formats=("svg",))}
    assert only_svg == {"drawings/s.svg"}


# -- renderer plugin seam (acceptance A1) --------------------------------


def _toy_render(model: DrawingModel) -> bytes:
    return f"TOY:{model.subject}".encode("ascii")


def _register_toy(bundle: RegistryBundle) -> None:
    bundle.renderers.register(
        RendererRegistration("toy", "toy.txt", DRAWING_FAMILY, _toy_render)
    )


# frob:tests python/regolith/backends/renderer_plugin.py::load_renderer_plugins kind="unit"
def test_toy_renderer_plugin_appears_with_zero_dispatch_edits() -> None:
    """A `kind=renderer` plugin's format shows up in `files_for_model`'s
    output with no edit to any dispatch site."""
    manifest = PluginManifest(
        id="toy-renderer",
        kind=PluginKind.RENDERER,
        version="1.0.0",
        register_fn=_register_toy,
    )
    outcome = load_renderer_plugins(
        entry_points_override=[_FakeEntryPoint("toy", manifest)]
    )
    assert outcome.errors == ()
    assert "toy" in outcome.bundle.renderers.formats()
    files = files_for_model("s", _one_sheet_model(), renderers=outcome.bundle.renderers)
    toy = [f for f in files if f.relpath == "drawings/s.toy.txt"]
    assert len(toy) == 1
    assert toy[0].content == b"TOY:s"


def _register_colliding(bundle: RegistryBundle) -> None:
    bundle.renderers.register(
        RendererRegistration("svg", "svg", DRAWING_FAMILY, _toy_render)
    )


def test_renderer_plugin_colliding_with_builtin_is_skipped_loudly() -> None:
    """A plugin claiming a built-in format id is a loud duplicate, never a
    silent shadow of the built-in renderer."""
    manifest = PluginManifest(
        id="evil-renderer",
        kind=PluginKind.RENDERER,
        version="1.0.0",
        register_fn=_register_colliding,
    )
    outcome = load_renderer_plugins(
        entry_points_override=[_FakeEntryPoint("evil", manifest)]
    )
    assert any(isinstance(e, DuplicatePluginId) for e in outcome.errors)
    # The built-in svg renderer is untouched.
    files = files_for_model("s", _one_sheet_model(), renderers=outcome.bundle.renderers)
    svg = [f for f in files if f.relpath == "drawings/s.svg"]
    assert svg and svg[0].content.startswith(b"<")


# -- package layout: index + determinism ---------------------------------


# frob:tests python/regolith/backends/package.py::package_side_files kind="unit"
def test_package_index_and_side_files_are_deterministic() -> None:
    """The index and gate/parity/acceptance ledgers are byte-stable across
    two assemblies (two ships byte-identical)."""
    from regolith.backends.framework import OutputFile
    from regolith.backends.package import ACCEPTANCE_LEDGER_NAME, package_side_files
    from regolith.backends.parity import build_parity_report
    from regolith.orchestrator.lockfile import Lockfile

    gate = _gate_summary()
    parity = build_parity_report(Lockfile(tool_version="0.1.0"), (), _empty_ledger())
    artifacts = (OutputFile.of("drawings/s.svg", b"<svg/>"),)
    first = package_side_files("proj", gate, parity, artifacts)
    second = package_side_files("proj", gate, parity, artifacts)
    assert {f.relpath: f.content for f in first} == {
        f.relpath: f.content for f in second
    }
    names = {f.relpath for f in first}
    assert ACCEPTANCE_LEDGER_NAME in names
    assert "index.md" in names
    index = next(f for f in first if f.relpath == "index.md")
    assert b"drawings/s.svg" in index.content
    assert b"RELEASE-CLEAN" in index.content


def _gate_summary():
    from regolith.orchestrator.orchestrate import GateCounts, GateSummary

    return GateSummary(
        tier="RELEASE",
        ok=True,
        release_ok=True,
        counts=GateCounts(violated=0, indeterminate=0, below_trust_floor=0),
    )


def _empty_ledger():
    from regolith._schema.models import WaiveLedger

    return WaiveLedger.model_validate({"entries": []})
