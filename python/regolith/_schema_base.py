"""The frozen pydantic base class every generated `_schema` model uses.

Hand-written (the ONE exception to "everything under `_schema/` is
generated") so `make schema` can point datamodel-code-generator's
`--base-class` at a stable import path (AD-5: pydantic v2 frozen).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


# frob:doc docs/modules/py-regolith.md#_schema_base
class FrozenModel(BaseModel):
    """Base for every generated schema model: frozen, per house style."""

    model_config = ConfigDict(frozen=True)
