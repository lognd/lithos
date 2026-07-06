"""The mech realizer's model-pack entry point (AD-19 / WO-20 D-B).

Wired the same way any external pack is: a ``register(registry) ->
None`` callable, discoverable via the ``regolith.model_packs`` entry
point group (``pyproject.toml``'s ``[project.entry-points]`` table).
Kept in-tree (not a separate distribution) since this pack ships with
the realizer itself, matching how the built-in `regolith.harness.models`
packs are composed by `default_registry()`.
"""

from __future__ import annotations

from regolith.harness.registry import ModelRegistry
from regolith.logging_setup import get_logger
from regolith.realizer.mech.model import GeometryRealizableModel

_log = get_logger(__name__)

# The pack identity every evidence hash this pack produces folds in
# (AD-19): bump on any change to the mech realizer's geometry/compare
# behavior so upgrading it invalidates exactly its own cached evidence.
PACK_NAME = "regolith-realizer-mech"
PACK_VERSION = "1"


def register(registry: ModelRegistry) -> None:
    """Add every model this pack discharges to ``registry``."""
    registry.register(
        GeometryRealizableModel(), pack_name=PACK_NAME, pack_version=PACK_VERSION
    )
    _log.debug("registered mech realizer pack %s@%s", PACK_NAME, PACK_VERSION)
