"""The ``renderer`` plugin kind (WO-99 registries + AD-26 one seam).

Third-party emission producers and renderers register through the same
``regolith.plugins`` group as every other extension kind
(``kind=renderer``): a manifest's ``register_fn(bundle: RegistryBundle)
-> None`` callable adds its producer kinds and/or drawing formats to the
composition by calling ``bundle.producers.register(...)`` /
``bundle.renderers.register(...)``. The built-in producers/renderers stay
built directly from the default registries; a third-party plugin composes
alongside them: a built-in (or an earlier plugin's) kind/format id is
never overridden by a plugin claiming the same id -- a loud duplicate,
not silent last-wins.

Trust is unaffected by this seam (INV-14/28): installing a renderer
plugin confers no trust; this module only discovers what is already
installed in the environment.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from regolith.backends.registry import (
    ProducerRegistry,
    RendererRegistry,
    default_producer_registry,
    default_renderer_registry,
)
from regolith.logging_setup import get_logger
from regolith.plugins import (
    DuplicatePluginId,
    PluginDiscoveryError,
    PluginEntryPoint,
    PluginEntryPointRaised,
    PluginKind,
    discover_plugins,
)

_log = get_logger(__name__)


@dataclass(frozen=True)
class RegistryBundle:
    """The pair of registries a ``renderer``-kind plugin registers into.

    Deliberately a plain dataclass (not pydantic): the registries hold
    callables, not validatable data.
    """

    producers: ProducerRegistry
    renderers: RendererRegistry


@dataclass(frozen=True)
class RendererPluginOutcome:
    """The total result of one ``renderer`` plugin composition pass:
    the merged registry bundle plus every loud discovery/collision error.
    """

    bundle: RegistryBundle
    errors: tuple[PluginDiscoveryError, ...] = ()


def load_renderer_plugins(
    *,
    producers: ProducerRegistry | None = None,
    renderers: RendererRegistry | None = None,
    entry_points_override: Iterable[PluginEntryPoint] | None = None,
) -> RendererPluginOutcome:
    """The built-in registries plus every ``renderer`` plugin (sorted-by-id).

    Each plugin stages into fresh registries first; a producer kind or
    renderer format id that collides with a built-in (or an earlier
    plugin's) id is a loud duplicate that skips the WHOLE plugin (never a
    partial merge, never a silent shadow); a plugin whose ``register_fn``
    raises is skipped the same way (plugin boundary: its bugs are our
    data).
    """
    base_producers = producers if producers is not None else default_producer_registry()
    base_renderers = renderers if renderers is not None else default_renderer_registry()
    discovery = discover_plugins(
        PluginKind.RENDERER, entry_points_override=entry_points_override
    )
    errors: list[PluginDiscoveryError] = list(discovery.errors)
    for manifest in discovery.manifests:
        staged = RegistryBundle(
            producers=ProducerRegistry(), renderers=RendererRegistry()
        )
        try:
            manifest.register_fn(staged)
        except Exception as exc:  # noqa: BLE001 -- plugin boundary: their bugs are our data
            _log.warning("renderer plugin %r raised LOUDLY: %s", manifest.id, exc)
            errors.append(
                PluginEntryPointRaised(
                    source=manifest.id, message=f"register() raised: {exc}"
                )
            )
            continue
        collision = _first_collision(base_producers, base_renderers, staged)
        if collision is not None:
            _log.warning(
                "renderer plugin %r claims id %r already registered LOUDLY",
                manifest.id,
                collision,
            )
            errors.append(DuplicatePluginId(source=manifest.id, plugin_id=collision))
            continue
        for registration in staged.producers.registrations():
            base_producers.register(registration)
        for family in ("drawing",):
            for registration in staged.renderers.for_family(family):
                base_renderers.register(registration)
        _log.info("registered renderer plugin %s@%s", manifest.id, manifest.version)
    return RendererPluginOutcome(
        bundle=RegistryBundle(producers=base_producers, renderers=base_renderers),
        errors=tuple(errors),
    )


def _first_collision(
    base_producers: ProducerRegistry,
    base_renderers: RendererRegistry,
    staged: RegistryBundle,
) -> str | None:
    """The first staged id colliding with an already-registered one, or
    ``None`` -- checked before any merge so a collision skips the whole
    plugin (all-or-nothing)."""
    existing_kinds = set(base_producers.kinds())
    for registration in staged.producers.registrations():
        if registration.kind in existing_kinds:
            return registration.kind
    existing_formats = set(base_renderers.formats())
    for registration in staged.renderers.for_family("drawing"):
        if registration.format_id in existing_formats:
            return registration.format_id
    return None
