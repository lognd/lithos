"""The payload-kind vocabulary the D96 channel carries (WO-30, sec. 8.3).

Single-homed here so no signature or discharge request ever hard-codes
a payload-kind string: registration lints signature ``payload_kinds``
values against this tuple. The strings are feldspar 09 sec. 4's list
VERBATIM -- the contract is the string, not a regolith re-styling of
it.
"""

from __future__ import annotations

# feldspar 09 sec. 4, verbatim (do not restyle these strings):
#   geometry.parametric   frozen pydantic family params
#   geometry.realized     STEP ref + topology summary (WO-22 record)
#   mesh                  MeshData digest
#   table                 interpolation table ref (property data)
#   spectrum | profile | mask   regolith/02 sec. 5 time/frequency objects
#   field                 discretized result field (nodal/element arrays)
#   flownet               fluid-circuit topology (fluorite lowering)
#   plan                  manufacturing plan artifact
# frob:doc docs/modules/py-harness.md#payloads
PAYLOAD_KINDS: tuple[str, ...] = (
    "geometry.parametric",
    "geometry.realized",
    "mesh",
    "table",
    "spectrum",
    "profile",
    "mask",
    "field",
    "flownet",
    "plan",
)


# frob:doc docs/modules/py-harness.md#payloads
# frob:waive TEST001 reason="thin accessor, tested transitively via harness tests"
def is_known_payload_kind(kind: str) -> bool:
    """True iff ``kind`` is one of the vocabulary-owned payload kinds."""
    return kind in PAYLOAD_KINDS
