"""The ONE typed discovery seam for out-of-wheel extensions (AD-26/WO-44).

Generalizes WO-20's proven model-pack discipline to every kind of
out-of-wheel extension: model packs, rule packs, MCU-family packs, and
manufacturing backends. Exactly one entry-point group,
``regolith.plugins``; each entry point resolves to a :class:`PluginManifest`
(frozen, self-describing: id, kind, version, and a kind-specific
``register_fn`` callable). Composition is deterministic (sorted by
entry-point name); a duplicate id within a kind, a malformed manifest, or
an entry point that raises while loading are all loud typed error
values -- never a crash and never last-wins (mirroring
``regolith.harness.plugin``'s pre-WO-44 pack discipline, which this
module now backs).

Trust is unaffected by this seam (INV-14/INV-28): installing a plugin
confers no trust, its evidence/attestation is signed by ITS OWN key.
Distribution is ordinary magnetite/PyPI packaging; this module only
discovers what is already installed in the environment.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from enum import StrEnum
from importlib.metadata import entry_points
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from regolith.logging_setup import get_logger

_log = get_logger(__name__)

# The one entry-point group every out-of-wheel extension registers
# through (AD-26). Nothing else may hard-code a discovery group name.
# frob:doc docs/modules/py-regolith.md#plugins
PLUGIN_ENTRY_POINT_GROUP = "regolith.plugins"


# frob:doc docs/modules/py-regolith.md#plugins
class PluginKind(StrEnum):
    """The closed v1 set of extension kinds (AD-26). Adding a kind is a
    spec change (a new charter/AD), never a caller-side convention."""

    MODEL_PACK = "model_pack"
    RULE_PACK = "rule_pack"
    MCU_PACK = "mcu_pack"
    BACKEND = "backend"
    RENDERER = "renderer"


# frob:doc docs/modules/py-regolith.md#plugins
class PluginManifest(BaseModel):
    """One plugin's identity plus its kind-specific registration callable.

    ``version`` is author-declared (not derived from installed
    distribution metadata) and folds into evidence/cache keys exactly as
    WO-20 folded pack versions (INV-1): bumping it re-keys exactly this
    plugin's own evidence. ``register_fn``'s signature is kind-specific
    (e.g. a ``ModelRegistry`` for ``model_pack``); each seam casts/calls
    it against the object it owns, mirroring the discipline WO-20's pack
    protocol already proved.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    id: str
    kind: PluginKind
    version: str
    register_fn: Callable[..., object]


# frob:doc docs/modules/py-regolith.md#plugins
class PluginEntryPoint(Protocol):
    """The slice of ``importlib.metadata.EntryPoint`` discovery reads.

    A structural protocol so tests inject fakes (AD-11) with no real
    installed distribution.
    """

    @property
    # frob:doc docs/modules/py-regolith.md#plugins
    def name(self) -> str:
        """The entry-point name (a human-readable label, not the plugin id)."""
        ...

    # frob:doc docs/modules/py-regolith.md#plugins
    def load(self) -> object:
        """Resolve the entry point's target object."""
        ...


# frob:doc docs/modules/py-regolith.md#plugins
class DuplicatePluginId(BaseModel):
    """Two plugins of the same kind declared the same id (AD-26: ids are
    globally unique per kind; the second is skipped, named by its
    source entry point)."""

    model_config = ConfigDict(frozen=True)

    source: str
    plugin_id: str


# frob:doc docs/modules/py-regolith.md#plugins
class MalformedPluginManifest(BaseModel):
    """An entry point's target was not a :class:`PluginManifest`."""

    model_config = ConfigDict(frozen=True)

    source: str
    message: str


# frob:doc docs/modules/py-regolith.md#plugins
class PluginEntryPointRaised(BaseModel):
    """An entry point raised while loading (third-party code is a plugin
    boundary: its exceptions are our recoverable data, never a crashed
    discovery pass)."""

    model_config = ConfigDict(frozen=True)

    source: str
    message: str


# The union of discovery-level failures every kind's loader may see.
PluginDiscoveryError = (
    DuplicatePluginId | MalformedPluginManifest | PluginEntryPointRaised
)


# frob:doc docs/modules/py-regolith.md#plugins
class PluginDiscoveryOutcome(BaseModel):
    """The total result of one discovery pass for one :class:`PluginKind`.

    ``sources`` maps each loaded manifest's id to its owning installed
    distribution's project name (``None`` when unavailable, e.g. a
    synthetic test entry point with no real distribution) -- the
    "source distribution" column `regolith plugin list` prints.
    """

    model_config = ConfigDict(frozen=True)

    manifests: tuple[PluginManifest, ...] = ()
    errors: tuple[PluginDiscoveryError, ...] = ()
    sources: dict[str, str | None] = {}


def _load_manifest(ep: PluginEntryPoint) -> PluginManifest | PluginDiscoveryError:
    """Resolve one entry point to a manifest, or the error value that skips it."""
    try:
        target = ep.load()
    except Exception as exc:  # noqa: BLE001 -- plugin boundary: their bugs are our data
        return PluginEntryPointRaised(
            source=ep.name, message=f"entry point load failed: {exc}"
        )
    if not isinstance(target, PluginManifest):
        return MalformedPluginManifest(
            source=ep.name,
            message=f"entry point target {target!r} is not a PluginManifest",
        )
    return target


# frob:doc docs/modules/py-regolith.md#plugins
def discover_plugins(
    kind: PluginKind,
    *,
    entry_points_override: Iterable[PluginEntryPoint] | None = None,
) -> PluginDiscoveryOutcome:
    """Discover every :class:`PluginManifest` of ``kind`` from the one group.

    Deterministic: entry points are processed in sorted-by-name order.
    Manifests of a different ``kind`` are silently skipped (they belong
    to a different loader's discovery pass, not an error); a malformed
    manifest, a raising entry point, or a duplicate id within ``kind``
    is a loud typed error, appended to ``errors`` -- discovery never
    raises and never partially composes past a bad entry. Nothing here
    reads ``importlib.metadata.Distribution`` -- the manifest's own
    ``version`` field is the identity, not installed package metadata.
    """
    discovered: Iterable[PluginEntryPoint] = (
        entry_points_override
        if entry_points_override is not None
        else entry_points(group=PLUGIN_ENTRY_POINT_GROUP)
    )
    manifests: list[PluginManifest] = []
    errors: list[PluginDiscoveryError] = []
    sources: dict[str, str | None] = {}
    seen_ids: set[str] = set()
    for ep in sorted(discovered, key=lambda e: e.name):
        loaded = _load_manifest(ep)
        if not isinstance(loaded, PluginManifest):
            _log.warning(
                "skipping malformed plugin entry point %r LOUDLY: %r",
                ep.name,
                loaded,
            )
            errors.append(loaded)
            continue
        if loaded.kind is not kind:
            continue
        if loaded.id in seen_ids:
            _log.warning(
                "skipping duplicate plugin id %r from %r LOUDLY (kind=%s)",
                loaded.id,
                ep.name,
                kind.value,
            )
            errors.append(DuplicatePluginId(source=ep.name, plugin_id=loaded.id))
            continue
        seen_ids.add(loaded.id)
        manifests.append(loaded)
        dist = getattr(ep, "dist", None)
        sources[loaded.id] = getattr(dist, "name", None) if dist is not None else None
        _log.info(
            "discovered %s plugin %s@%s (source=%s)",
            kind.value,
            loaded.id,
            loaded.version,
            ep.name,
        )
    return PluginDiscoveryOutcome(
        manifests=tuple(manifests), errors=tuple(errors), sources=sources
    )


# frob:doc docs/modules/py-regolith.md#plugins
# frob:waive TEST001 reason="entry-point discovery, tested via plugin-seam tests"
def discover_rule_pack_plugins(
    *,
    entry_points_override: Iterable[PluginEntryPoint] | None = None,
) -> PluginDiscoveryOutcome:
    """The RESERVED ``rule_pack`` kind loader (WO-44 deliverable 2).

    The in-language rule-pack format is WO-28's remainder to design, not
    this WO's to invent; this stub proves the kind is wired into the one
    seam (discovery would find manifests of this kind) while always
    composing an empty set until WO-28 lands.

    # TODO(WO-28): once the rule-pack authoring format + engine exist,
    # replace this stub with a real composition step (mirroring
    # `discover_plugins(PluginKind.RULE_PACK, ...)` fed into the
    # AD-21 engine), matching the `model_pack`/`mcu_pack`/`backend`
    # kinds' shape.
    """
    del entry_points_override  # reserved: unused until WO-28
    _log.debug("rule_pack plugin kind is RESERVED (WO-28); composing an empty set")
    return PluginDiscoveryOutcome()
