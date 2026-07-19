"""WO-44/AD-26 conformance: the one ``regolith.plugins`` discovery seam.

Exercises the generalized seam directly (``regolith.plugins``) plus its
two newly-folded, non-model kinds (``mcu_pack``, ``backend``): a fixture
plugin per kind, loud duplicate-id/malformed-manifest refusal, and
discovery-order determinism (shuffled entry points -> identical
composition). The ``model_pack`` kind's own conformance (staging,
AD-19 evidence keying, INV-1) stays in ``tests/packs/test_pack_protocol.py``
via ``conformance.assert_pack_conforms``; this file exercises the kinds
that don't discharge evidence.
"""

from __future__ import annotations

import random

from regolith.backends.framework import Backend, BackendInputs, OutputFile
from regolith.backends.plugin import load_backend_plugins
from regolith.errors import BackendError
from regolith.plugins import (
    DuplicatePluginId,
    MalformedPluginManifest,
    PluginKind,
    PluginManifest,
    discover_plugins,
)
from regolith.realizer.elec.pinmux import PinAssignment
from regolith.realizer.firmware.contract import ClockDecl, EventDecl
from regolith.realizer.firmware.packs import FamilyPack, get_pack
from typani.result import Ok, Result

# -- fake entry point (mirrors tests.packs.conformance.FakeEntryPoint, but
# generic over kind for direct `regolith.plugins` exercise) -----------------


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


# -- fixture mcu_pack ---------------------------------------------------------


class _FixtureFamilyPack(FamilyPack):
    """A trivial fixture MCU-family pack proving the mcu_pack kind."""

    family = "fixture_family"

    def pin_init_lines(self, assignment: PinAssignment) -> tuple[str, ...]:
        return (f"/* fixture pin init: {assignment.flow} */",)

    def clock_init_lines(self, clock: ClockDecl) -> tuple[str, ...]:
        return (f"/* fixture clock init: {clock.name} */",)

    def isr_stub(self, event: EventDecl) -> tuple[str, ...]:
        del event
        return ("/* fixture isr */",)


def _register_fixture_family(packs: dict[str, FamilyPack]) -> None:
    packs[_FixtureFamilyPack.family] = _FixtureFamilyPack()


# frob:tests python/regolith/realizer/firmware/packs.py::get_pack
def test_mcu_pack_plugin_is_discovered_and_composed_after_builtins() -> None:
    """Acceptance: a `kind=mcu_pack` plugin's family resolves via `get_pack`."""
    manifest = PluginManifest(
        id="fixture-mcu",
        kind=PluginKind.MCU_PACK,
        version="1.0.0",
        register_fn=_register_fixture_family,
    )
    resolved = get_pack(
        "fixture_family",
        entry_points_override=[_FakeEntryPoint("fixture-mcu", manifest)],
    )
    assert resolved.is_ok
    assert isinstance(resolved.danger_ok, _FixtureFamilyPack)
    # Built-ins stay resolvable alongside the plugin.
    builtin = get_pack(
        "stm32g0", entry_points_override=[_FakeEntryPoint("fixture-mcu", manifest)]
    )
    assert builtin.is_ok


# -- fixture backend -----------------------------------------------------------


class _FixtureBackend:
    """A trivial fixture manufacturing backend proving the backend kind."""

    def produce(
        self, inputs: BackendInputs
    ) -> Result[tuple[OutputFile, ...], BackendError]:
        del inputs
        return Ok((OutputFile.of("fixture.txt", b"fixture backend output"),))


def _register_fixture_backend(backends: dict[str, Backend]) -> None:
    backends["fixture"] = _FixtureBackend()


class _BuiltinMarkerBackend:
    """A distinct, identity-checkable stand-in for "the builtin backend
    already registered under this key" -- a real `Backend` so the plugin
    seam's `dict[str, Backend]` typing holds, never a bare `object()`."""

    def produce(
        self, inputs: BackendInputs
    ) -> Result[tuple[OutputFile, ...], BackendError]:
        del inputs
        return Ok((OutputFile.of("builtin.txt", b"builtin backend output"),))


# frob:tests python/regolith/backends/plugin.py::load_backend_plugins kind="unit"
def test_backend_plugin_composes_alongside_builtins() -> None:
    """Acceptance: a `kind=backend` plugin adds a named backend, builtins kept."""
    manifest = PluginManifest(
        id="fixture-backend",
        kind=PluginKind.BACKEND,
        version="1.0.0",
        register_fn=_register_fixture_backend,
    )
    builtin_marker = _BuiltinMarkerBackend()
    outcome = load_backend_plugins(
        {"mech": builtin_marker},
        entry_points_override=[_FakeEntryPoint("fixture-backend", manifest)],
    )
    assert outcome.errors == ()
    assert outcome.backends["mech"] is builtin_marker
    assert isinstance(outcome.backends["fixture"], _FixtureBackend)


def test_backend_plugin_never_shadows_a_builtin_key() -> None:
    """A plugin naming an already-claimed key is a loud duplicate, not last-wins."""

    def _register_hostile(backends: dict[str, Backend]) -> None:
        backends["mech"] = _FixtureBackend()

    manifest = PluginManifest(
        id="hostile-backend",
        kind=PluginKind.BACKEND,
        version="1.0.0",
        register_fn=_register_hostile,
    )
    builtin_marker = _BuiltinMarkerBackend()
    outcome = load_backend_plugins(
        {"mech": builtin_marker},
        entry_points_override=[_FakeEntryPoint("hostile-backend", manifest)],
    )
    assert outcome.backends["mech"] is builtin_marker
    assert len(outcome.errors) == 1
    assert isinstance(outcome.errors[0], DuplicatePluginId)


# -- generic seam: duplicate id / malformed manifest / determinism -----------


# frob:tests python/regolith/plugins.py::discover_plugins
def test_duplicate_plugin_id_within_a_kind_is_a_loud_error() -> None:
    """Two manifests sharing an id under the SAME kind: the second is skipped."""
    first = PluginManifest(
        id="dup", kind=PluginKind.BACKEND, version="1.0.0", register_fn=lambda b: None
    )
    second = PluginManifest(
        id="dup", kind=PluginKind.BACKEND, version="2.0.0", register_fn=lambda b: None
    )
    outcome = discover_plugins(
        PluginKind.BACKEND,
        entry_points_override=[
            _FakeEntryPoint("a_first", first),
            _FakeEntryPoint("b_second", second),
        ],
    )
    assert [m.id for m in outcome.manifests] == ["dup"]
    assert len(outcome.errors) == 1
    assert isinstance(outcome.errors[0], DuplicatePluginId)
    assert outcome.errors[0].plugin_id == "dup"


def test_malformed_manifest_is_a_loud_error_never_a_crash() -> None:
    """An entry point resolving to a non-PluginManifest is a named error value."""
    outcome = discover_plugins(
        PluginKind.BACKEND,
        entry_points_override=[_FakeEntryPoint("junk", object())],
    )
    assert outcome.manifests == ()
    assert len(outcome.errors) == 1
    assert isinstance(outcome.errors[0], MalformedPluginManifest)
    assert outcome.errors[0].source == "junk"


def test_discovery_composition_is_deterministic_under_shuffle() -> None:
    """Discovery order is sorted-by-entry-point-name regardless of input order."""
    manifests = [
        PluginManifest(
            id=f"plugin-{i}",
            kind=PluginKind.BACKEND,
            version="1.0.0",
            register_fn=lambda b: None,
        )
        for i in range(5)
    ]
    entries = [
        _FakeEntryPoint(f"ep-{i}", manifest) for i, manifest in enumerate(manifests)
    ]
    shuffled = list(entries)
    random.Random(42).shuffle(shuffled)
    baseline = discover_plugins(PluginKind.BACKEND, entry_points_override=entries)
    reordered = discover_plugins(PluginKind.BACKEND, entry_points_override=shuffled)
    assert [m.id for m in baseline.manifests] == [m.id for m in reordered.manifests]
    assert [m.id for m in baseline.manifests] == [f"plugin-{i}" for i in range(5)]


def test_rule_pack_kind_is_reserved_and_composes_empty() -> None:
    """WO-28's remainder: the rule_pack kind is wired but always empty for now."""
    outcome = discover_plugins(PluginKind.RULE_PACK, entry_points_override=[])
    assert outcome.manifests == ()
    assert outcome.errors == ()
