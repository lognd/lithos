"""The ``backend`` plugin kind (WO-25 framework + WO-44/AD-26 one seam).

Third-party manufacturing backends register through the same
``regolith.plugins`` group as every other extension kind
(``kind=backend``): a manifest's ``register_fn(backends: dict[str,
Backend]) -> None`` callable adds its named backend(s) to the composition. The two
in-tree backends (``mech``, ``elec``) stay built directly from a ship
spec (`regolith.cli.app`) -- they are not plugins themselves -- but a
third-party backend plugin composes alongside them: built-ins are never
overridden by a plugin naming the same key (a loud duplicate, not
silent last-wins).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from regolith.backends.framework import Backend
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


# frob:doc docs/modules/py-backends.md#backends-plugin
@dataclass(frozen=True)
class BackendPluginOutcome:
    """The total result of one ``backend`` plugin composition pass.

    Deliberately not a pydantic model (mirroring ``BackendInputs``):
    ``Backend`` is a structural ``Protocol``, not a runtime-checkable
    class pydantic can validate a container of.
    """

    backends: dict[str, Backend] = field(default_factory=dict)
    errors: tuple[PluginDiscoveryError, ...] = ()


# frob:doc docs/modules/py-backends.md#backends-plugin
def load_backend_plugins(
    builtin: Mapping[str, Backend],
    *,
    entry_points_override: Iterable[PluginEntryPoint] | None = None,
) -> BackendPluginOutcome:
    """``builtin`` backends plus every ``backend`` plugin (sorted-by-id).

    A plugin naming a key already present in ``builtin`` (or claimed by
    an earlier plugin) is a loud duplicate, skipped -- built-ins are
    never shadowed silently; a plugin whose ``register_fn`` raises is
    skipped the same way (plugin boundary: its bugs are our data).
    """
    backends = dict(builtin)
    discovery = discover_plugins(
        PluginKind.BACKEND, entry_points_override=entry_points_override
    )
    errors: list[PluginDiscoveryError] = list(discovery.errors)
    for manifest in discovery.manifests:
        staging: dict[str, Backend] = {}
        try:
            manifest.register_fn(staging)
        except Exception as exc:  # noqa: BLE001 -- plugin boundary: their bugs are our data
            _log.warning("backend plugin %r raised LOUDLY: %s", manifest.id, exc)
            errors.append(
                PluginEntryPointRaised(
                    source=manifest.id, message=f"register() raised: {exc}"
                )
            )
            continue
        collision = next((key for key in staging if key in backends), None)
        if collision is not None:
            _log.warning(
                "backend plugin %r claims key %r already registered LOUDLY",
                manifest.id,
                collision,
            )
            errors.append(DuplicatePluginId(source=manifest.id, plugin_id=collision))
            continue
        backends.update(staging)
        _log.info("registered backend plugin %s@%s", manifest.id, manifest.version)
    return BackendPluginOutcome(backends=backends, errors=tuple(errors))
