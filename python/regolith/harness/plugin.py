"""Entry-point discovery of external model packs (WO-20/AD-19).

Design: `docs/implementation/design/20-solver-abstraction.md` sec. D-B. A pack
is a normal Python distribution exposing one entry point in the group
``regolith.model_packs`` whose target is ``register(registry) -> None``;
regolith discovers packs by name only and NEVER imports one by module
path (no dependency cycle is representable). Composition is
deterministic: built-ins first (``default_registry``), then packs in
sorted-by-name order. A bad pack is skipped LOUDLY -- its error is a
value recorded on the registry and named in the build report, and its
models are staged so a mid-registration failure never leaves a partial
load -- but it never aborts the other packs and never raises.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from importlib.metadata import entry_points
from typing import Protocol, cast

from pydantic import BaseModel, ConfigDict

from regolith.harness.registry import ModelRegistry, method_named_kind_violation
from regolith.logging_setup import get_logger

_log = get_logger(__name__)

# The one entry-point group regolith discovers packs from (D-B):
#   [project.entry-points."regolith.model_packs"]
#   feldspar = "feldspar.pack:register"
ENTRY_POINT_GROUP = "regolith.model_packs"

# The version string recorded for a pack whose distribution metadata is
# unavailable (e.g. a synthetic test entry point without a dist).
UNKNOWN_PACK_VERSION = "unknown"


class PackDistribution(Protocol):
    """The slice of ``importlib.metadata.Distribution`` discovery reads."""

    @property
    def version(self) -> str:
        """The distribution's version string."""
        ...


class PackEntryPoint(Protocol):
    """The slice of ``importlib.metadata.EntryPoint`` discovery reads.

    A structural protocol so the AD-11 test fakes need no real installed
    distribution.
    """

    @property
    def name(self) -> str:
        """The entry-point name (== the pack name)."""
        ...

    @property
    def dist(self) -> PackDistribution | None:
        """The owning distribution, when known."""
        ...

    def load(self) -> object:
        """Resolve the entry point's target object."""
        ...


class PackInfo(BaseModel):
    """One successfully loaded model pack's identity (name + version).

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
    """A pack's entry point raised while loading or registering.

    Third-party pack code is a plugin boundary: its exceptions are OUR
    recoverable data (the pack is skipped loudly), never a crashed
    build.
    """

    model_config = ConfigDict(frozen=True)

    pack: str
    message: str


class BadRegisterSignature(BaseModel):
    """A pack's entry point did not resolve to a callable ``register``."""

    model_config = ConfigDict(frozen=True)

    pack: str
    message: str


# The union of pack-load failure values: each names its pack and is
# surfaced in the build report (never a silent partial load).
PackLoadError = (
    DuplicateModelId | EntryPointRaised | BadRegisterSignature | MethodNamedKind
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


def _pack_version(ep: PackEntryPoint) -> str:
    """The pack's distribution version, or the explicit unknown marker."""
    dist = ep.dist
    if dist is None:
        return UNKNOWN_PACK_VERSION
    return dist.version


def _stage_pack(
    ep: PackEntryPoint, registry: ModelRegistry
) -> tuple[ModelRegistry, str] | PackLoadError:
    """Run one pack's ``register`` against a STAGING registry.

    Returns the staged registry (nothing touched the real one yet) or
    the error value that skips the pack. Staging is what makes a
    mid-registration failure leave NO partial load.
    """
    try:
        target = ep.load()
    except Exception as exc:  # noqa: BLE001 -- plugin boundary: pack bugs are our data
        return EntryPointRaised(pack=ep.name, message=f"entry point load failed: {exc}")
    if not callable(target):
        return BadRegisterSignature(
            pack=ep.name,
            message=f"entry point target {target!r} is not callable",
        )
    # The protocol's whole surface: `register(registry) -> None` (D-B).
    # A wrong-arity callable raises TypeError below, which is the same
    # skipped-loudly EntryPointRaised arm as any other pack bug.
    register = cast("Callable[[ModelRegistry], object]", target)
    staging = ModelRegistry(version=registry.version)
    try:
        register(staging)
    except Exception as exc:  # noqa: BLE001 -- plugin boundary: pack bugs are our data
        return EntryPointRaised(pack=ep.name, message=f"register() raised: {exc}")
    staged = staging.all_models()
    # D94 (sec. 8.1): a claim kind names WHAT is claimed, never a
    # method/tool/tier -- lint every staged model's kind before any
    # duplicate check.
    for model in staged:
        kind = model.signature.claim_kind
        word = method_named_kind_violation(kind)
        if word is not None:
            return MethodNamedKind(pack=ep.name, claim_kind=kind, word=word)
    # D94: the registry key is (claim_kind, model_id) -- one model MAY
    # register under two DIFFERENT kinds; a duplicate is the SAME key
    # appearing twice, within this pack or against what is already
    # registered.
    staged_keys = [(model.signature.claim_kind, model.model_id) for model in staged]
    if len(staged_keys) != len(set(staged_keys)):
        dup = sorted({k for k in staged_keys if staged_keys.count(k) > 1})[0]
        return DuplicateModelId(pack=ep.name, model_id=dup[1])
    collisions = sorted(set(staged_keys) & registry.registered_keys())
    if collisions:
        return DuplicateModelId(pack=ep.name, model_id=collisions[0][1])
    return staging, _pack_version(ep)


def load_packs(
    registry: ModelRegistry,
    *,
    entry_points_override: Iterable[PackEntryPoint] | None = None,
) -> PackLoadOutcome:
    """Discover and compose every model pack into ``registry`` (D-B).

    Deterministic: entry points are processed in sorted-by-name order,
    after whatever is already registered (built-ins first). Each pack
    registers against a staging registry and is merged only when clean;
    a failing pack is skipped LOUDLY (WARNING log + error value), never
    silently and never partially. The outcome is also recorded on the
    registry so the orchestrator's build report can name skipped packs.
    ``entry_points_override`` injects fakes for tests (AD-11).
    """
    discovered: Iterable[PackEntryPoint] = (
        entry_points_override
        if entry_points_override is not None
        else entry_points(group=ENTRY_POINT_GROUP)
    )
    loaded: list[PackInfo] = []
    skipped: list[PackLoadError] = []
    for ep in sorted(discovered, key=lambda e: e.name):
        staged = _stage_pack(ep, registry)
        if isinstance(
            staged,
            DuplicateModelId
            | EntryPointRaised
            | BadRegisterSignature
            | MethodNamedKind,
        ):
            _log.warning("skipping model pack %r LOUDLY: %r", ep.name, staged)
            skipped.append(staged)
            continue
        staging, version = staged
        for model in staging.all_models():
            registry.register(model, pack_name=ep.name, pack_version=version)
        info = PackInfo(name=ep.name, version=version)
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
