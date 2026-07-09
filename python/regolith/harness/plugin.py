"""Model-pack composition over the ONE plugin seam (WO-20/AD-19, WO-44/AD-26).

Design: `docs/spec/toolchain/20-solver-abstraction.md` sec. D-B. A pack is
a normal Python distribution exposing one entry point in the group
``regolith.plugins`` whose target is a ``regolith.plugins.PluginManifest``
with ``kind=model_pack`` and a ``register_fn(registry) -> None`` callable
(WO-44 migrated this seam off its own ``regolith.model_packs`` group onto
the shared one). regolith discovers packs by id only and NEVER imports one
by module path (no dependency cycle is representable). Composition is
deterministic: built-ins first (``default_registry``), then packs in
sorted-by-id order. A bad pack is skipped LOUDLY -- its error is a value
recorded on the registry and named in the build report, and its models
are staged so a mid-registration failure never leaves a partial load --
but it never aborts the other packs and never raises.
"""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict

from regolith.harness.registry import ModelRegistry, method_named_kind_violation
from regolith.logging_setup import get_logger
from regolith.plugins import (
    PluginDiscoveryError,
    PluginEntryPoint,
    PluginKind,
    PluginManifest,
    discover_plugins,
)

_log = get_logger(__name__)


class PackInfo(BaseModel):
    """One successfully loaded model pack's identity (id + version).

    The pair every evidence hash produced by the pack's models folds
    (AD-19), so upgrading the pack invalidates exactly its own cached
    evidence.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    version: str


class DuplicateModelId(BaseModel):
    """A pack declared a model id something already registered (D-B).

    D94: the registry key is ``(claim_kind, model_id)`` -- one model MAY
    register under two DIFFERENT kinds legally, so this is a duplicate
    only when the SAME kind already has that id. Two models sharing one
    id under ONE kind would make selection ambiguous; the whole pack is
    skipped (no partial load) and named.
    """

    model_config = ConfigDict(frozen=True)

    pack: str
    model_id: str


class MethodNamedKind(BaseModel):
    """A pack declared a claim kind naming a method/tool, not WHAT is
    claimed (D94, sec. 8.1: `mech.fea.static_stress` was a bootstrap
    error). The whole pack is skipped, naming the offending word.
    """

    model_config = ConfigDict(frozen=True)

    pack: str
    claim_kind: str
    word: str


class EntryPointRaised(BaseModel):
    """A pack's ``register_fn`` callable raised while composing (not while
    the entry point resolved to a manifest -- that failure is a generic
    ``regolith.plugins.PluginEntryPointRaised``, folded into ``skipped``
    the same way). Third-party pack code is a plugin boundary: its
    exceptions are OUR recoverable data (the pack is skipped loudly),
    never a crashed build.
    """

    model_config = ConfigDict(frozen=True)

    pack: str
    message: str


# The union of pack-load failure values: each names its pack and is
# surfaced in the build report (never a silent partial load). Includes
# the generic seam-level failures (malformed manifest, duplicate id,
# entry point raised while loading) alongside this seam's own
# model-specific checks (duplicate model id, method-named-kind).
PackLoadError = (
    DuplicateModelId | EntryPointRaised | MethodNamedKind | PluginDiscoveryError
)


class PackLoadOutcome(BaseModel):
    """The total result of one pack-composition pass.

    Loading is TOTAL: bad packs land in ``skipped`` as values (the WO's
    skip-loudly contract) rather than aborting composition, so one
    broken pack can never take the others down.
    """

    model_config = ConfigDict(frozen=True)

    loaded: tuple[PackInfo, ...] = ()
    skipped: tuple[PackLoadError, ...] = ()


def _stage_pack(
    manifest: PluginManifest, registry: ModelRegistry
) -> tuple[ModelRegistry, str] | PackLoadError:
    """Run one pack's ``register_fn`` against a STAGING registry.

    Returns the staged registry (nothing touched the real one yet) or
    the error value that skips the pack. Staging is what makes a
    mid-registration failure leave NO partial load.
    """
    staging = ModelRegistry(version=registry.version)
    try:
        manifest.register_fn(staging)
    except Exception as exc:  # noqa: BLE001 -- plugin boundary: pack bugs are our data
        return EntryPointRaised(pack=manifest.id, message=f"register() raised: {exc}")
    staged = staging.all_models()
    # D94 (sec. 8.1): a claim kind names WHAT is claimed, never a
    # method/tool/tier -- lint every staged model's kind before any
    # duplicate check.
    for model in staged:
        kind = model.signature.claim_kind
        word = method_named_kind_violation(kind)
        if word is not None:
            return MethodNamedKind(pack=manifest.id, claim_kind=kind, word=word)
    # D94: the registry key is (claim_kind, model_id) -- one model MAY
    # register under two DIFFERENT kinds; a duplicate is the SAME key
    # appearing twice, within this pack or against what is already
    # registered.
    staged_keys = [(model.signature.claim_kind, model.model_id) for model in staged]
    if len(staged_keys) != len(set(staged_keys)):
        dup = sorted({k for k in staged_keys if staged_keys.count(k) > 1})[0]
        return DuplicateModelId(pack=manifest.id, model_id=dup[1])
    collisions = sorted(set(staged_keys) & registry.registered_keys())
    if collisions:
        return DuplicateModelId(pack=manifest.id, model_id=collisions[0][1])
    return staging, manifest.version


def load_packs(
    registry: ModelRegistry,
    *,
    entry_points_override: Iterable[PluginEntryPoint] | None = None,
) -> PackLoadOutcome:
    """Discover and compose every ``model_pack`` plugin into ``registry``.

    Deterministic: plugins are processed in sorted-by-entry-point-name
    order (``regolith.plugins.discover_plugins``), after whatever is
    already registered (built-ins first). Each pack registers against a
    staging registry and is merged only when clean; a failing pack is
    skipped LOUDLY (WARNING log + error value), never silently and never
    partially. The outcome is also recorded on the registry so the
    orchestrator's build report can name skipped packs.
    ``entry_points_override`` injects fakes for tests (AD-11).
    """
    discovery = discover_plugins(
        PluginKind.MODEL_PACK, entry_points_override=entry_points_override
    )
    loaded: list[PackInfo] = []
    skipped: list[PackLoadError] = list(discovery.errors)
    for manifest in discovery.manifests:
        staged = _stage_pack(manifest, registry)
        if not isinstance(staged, tuple):
            _log.warning("skipping model pack %r LOUDLY: %r", manifest.id, staged)
            skipped.append(staged)
            continue
        staging, version = staged
        for model in staging.all_models():
            registry.register(model, pack_name=manifest.id, pack_version=version)
        info = PackInfo(name=manifest.id, version=version)
        loaded.append(info)
        _log.info(
            "loaded model pack %s@%s (%d models)",
            info.name,
            info.version,
            len(staging.all_models()),
        )
    outcome = PackLoadOutcome(loaded=tuple(loaded), skipped=tuple(skipped))
    registry.record_packs(outcome.loaded, outcome.skipped)
    return outcome
