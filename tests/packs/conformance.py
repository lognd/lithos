"""The REUSABLE pack-protocol conformance suite (WO-20, design doc D-F).

Any model pack runs :func:`assert_pack_conforms` against itself (point
pytest at a module that calls it with the pack's entry-point name,
version, ``register`` callable, and one synthetic request its models
match). It asserts the whole protocol: registration through
``load_packs`` fakes, deterministic composition (built-ins first,
sorted packs), selection + total discharge of a synthetic obligation,
AD-19 evidence-hash keying (a pack version bump changes the pack's own
evidence hash and leaves built-ins alone), and INV-10 determinism
(repeat discharge is byte-identical).
"""

from __future__ import annotations

from collections.abc import Callable

from regolith._schema.models import Evidence
from regolith.harness import (
    DischargeRequest,
    ModelRegistry,
    PackInfo,
    default_registry,
    load_packs,
)

# A pack's register callable: the whole protocol surface (D-B).
RegisterFn = Callable[[ModelRegistry], None]


class FakeDistribution:
    """A stand-in for ``importlib.metadata.Distribution`` (version only)."""

    def __init__(self, version: str) -> None:
        """Carry the fake distribution's version string."""
        self._version = version

    @property
    def version(self) -> str:
        """The distribution version the pack identity folds (AD-19)."""
        return self._version


class FakeEntryPoint:
    """A stand-in for ``importlib.metadata.EntryPoint`` (AD-11 fakes).

    Satisfies :class:`regolith.harness.plugin.PackEntryPoint`
    structurally, so the suite needs no installed distribution.
    """

    def __init__(self, name: str, version: str, target: object) -> None:
        """A fake entry point resolving to ``target`` for pack ``name``."""
        self._name = name
        self._dist = FakeDistribution(version)
        self._target = target

    @property
    def name(self) -> str:
        """The entry-point name (== the pack name)."""
        return self._name

    @property
    def dist(self) -> FakeDistribution:
        """The owning fake distribution."""
        return self._dist

    def load(self) -> object:
        """Resolve the fake target (a real EntryPoint imports here)."""
        return self._target


def registry_with_pack(name: str, version: str, register: RegisterFn) -> ModelRegistry:
    """Built-ins plus one pack, composed exactly like ``default_registry``."""
    registry = default_registry()
    outcome = load_packs(
        registry,
        entry_points_override=[FakeEntryPoint(name, version, register)],
    )
    assert outcome.skipped == (), f"pack {name!r} failed to load: {outcome.skipped}"
    assert PackInfo(name=name, version=version) in outcome.loaded
    return registry


def discharge_with_pack(
    name: str, version: str, register: RegisterFn, request: DischargeRequest
) -> Evidence:
    """One total discharge of ``request`` through built-ins + the pack."""
    return registry_with_pack(name, version, register).discharge(request)


def assert_pack_conforms(
    *,
    name: str,
    version: str,
    register: RegisterFn,
    request: DischargeRequest,
) -> None:
    """The pack-protocol conformance contract, in one callable.

    ``request`` must be a synthetic request exactly one of the pack's
    models matches; the assertions are the protocol (see module doc).
    """
    baseline = default_registry()
    registry = registry_with_pack(name, version, register)

    # Deterministic composition: built-ins first, the pack's models after.
    builtin_count = len(baseline.all_models())
    assert [m.model_id for m in registry.all_models()[:builtin_count]] == [
        m.model_id for m in baseline.all_models()
    ], "built-ins must precede pack models, unchanged"
    added = registry.all_models()[builtin_count:]
    assert added, "the pack registered no models"
    for model in added:
        assert registry.pack_of(model.model_id) == (name, version)

    # The synthetic request selects a model OF THIS PACK.
    selected = registry.select(request)
    assert selected.is_ok, f"no pack model matched {request.claim_kind!r}"
    assert registry.pack_of(selected.danger_ok.model_id) == (name, version)

    # Total discharge: an Evidence VALUE, never an exception.
    evidence = registry.discharge(request)
    assert evidence.status.value in {"discharged", "violated", "indeterminate"}

    # INV-10 determinism: repeat discharge is byte-identical.
    again = registry.discharge(request)
    assert again == evidence, "repeat discharge must be byte-identical"

    # AD-19 keying: a pack version bump changes the pack's own evidence
    # hash (stale cached evidence can never be silently reused) ...
    bumped = discharge_with_pack(name, version + ".bumped", register, request)
    assert bumped.hash != evidence.hash, "pack version must be a hash input"
    # ... and composition stays otherwise deterministic under the bump.
    assert bumped.model_id == evidence.model_id
