"""std.dfm: the realized-geometry manufacturability pack (WO-110).

One registration point, the `cam`/`hdl` subdirectory convention
(charter 39 sec. 5.2): `register_dfm_models` is called from
`regolith.harness.models.register_all`.
"""

from __future__ import annotations

from regolith.harness.models.dfm.models import ManufacturableModel
from regolith.harness.registry import ModelRegistry


# frob:doc docs/modules/py-harness.md#models-dfm-init
# frob:waive TEST001 reason="registration fn, tested via registry build (transitive)"
def register_dfm_models(registry: ModelRegistry) -> None:
    """Register the manufacturability model family (v1: mill)."""
    registry.register(ManufacturableModel())


__all__ = ["ManufacturableModel", "register_dfm_models"]
