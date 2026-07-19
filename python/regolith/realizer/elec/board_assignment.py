"""`RealizedBoardAssignment` put seam (WO-163, AD-47 sec. 5, A7 closure):
the board-shaped realized-kind for substrate-and-assignment capabilities
OTHER than an etched-copper KiCad board (perf-board today, WO-165; any
future substrate-and-assignment capability later).

Recon correction recorded here (see WO-163 close-out for the full
statement): the `layout.realized` put seam
(`regolith.realizer.elec.realized.put_realized_layout`) IS landed and
IS wired into the staged build loop
(`regolith.orchestrator.orchestrate.py` around the elec leg) -- the gap
AD-47 sec. 5 actually names is that `RealizedLayout` is COPPER-BOARD-
SHAPED (a mandatory `copper: CopperSummary` and a
`kicad_pcb_content_hash` pin, both meaningless for a perf-board
substrate with no etched copper and no `.kicad_pcb` native file). This
module is the sibling type deliverable (b) WO-163 designed: a NEW,
independent realized-kind, not a `RealizedLayout` field.

Schema-bump note (D211 sequencing, read before editing): `RealizedLayout`
is schemars-sourced from `crates/regolith-oblig/src/layout.rs`, mirrored
generated-only into `python/regolith/_schema/models.py`. A schemars-
sourced sibling type would need a NEW SCHEMA_VERSION bump; WO-147 owns
the cycle-37 SCHEMA_VERSION bump (D261.4) and is still `open` as of this
WO's dispatch, so per the WO-160 D211 precedent this WO may NOT open a
second bump itself -- it must ride WO-147's bump or escalate to the
coordinator. Rather than block this WO's whole acceptance on that
escalation, `RealizedBoardAssignment` is defined here as a PLAIN
pydantic model (no schemars mirror, no crates/ touch), the same posture
`ArtifactRow` held before WO-160 folded it into a schemars type: usable
today, and promotable into a schemars-sourced type as a passenger on a
future SCHEMA_VERSION bump without changing this seam's shape or the
`put_realized_board_assignment` call site. This is a forward-authored
contract type in the AD-22/WO-162 sense (see `frob:ticket` marker
convention) until that promotion lands.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from regolith.logging_setup import get_logger
from regolith.orchestrator.payload_store import PayloadStore

_log = get_logger(__name__)

#: The D96 realized-kind string for a board-shaped, non-copper
#: substrate/jumper/wire-assignment payload -- named consistently with
#: `layout.realized`/`geometry.realized` (`regolith.orchestrator.
#: orchestrate`'s `_REALIZER_PACK_BY_KIND`/`_LOCK_SLOT_SUFFIX_BY_KIND`).
# frob:doc docs/modules/py-realizer.md#elec-realized
BOARD_ASSIGNMENT_DOMAIN_TAG = "board_assignment.realized"


# frob:doc docs/modules/py-realizer.md#elec-realized
class WireAssignment(BaseModel):
    """One wire/jumper run between two fixed-grid perf-board holes."""

    model_config = ConfigDict(frozen=True)

    net: str
    from_hole: str
    to_hole: str
    length_mm: float


# frob:doc docs/modules/py-realizer.md#elec-realized
class ComponentAssignment(BaseModel):
    """One component's fixed-grid hole assignment on a perf-board substrate."""

    model_config = ConfigDict(frozen=True)

    reference: str
    footprint: str
    anchor_hole: str
    rotation_deg: float = 0.0


# NOTE (escalation, see this WO's close-out): this is a forward-authored
# plain-pydantic stand-in for a future schemars-sourced type in the
# AD-22/WO-162 sense (D211 sequencing note above). It does NOT yet carry
# a `frob:ticket` marker because minting its promotion ticket requires a
# tickets.md write this dispatch's rules forbid; the ticket must be
# created (and this marker added) by whoever has that write authority
# before the WO-162 gate is wired to enforce this file.
# frob:doc docs/modules/py-realizer.md#elec-realized
class RealizedBoardAssignment(BaseModel):
    """The serialized realized-board-assignment payload (WO-163, A7): a
    board-shaped realized kind for substrate-and-assignment capabilities
    that are NOT an etched-copper KiCad board -- no `copper` field, no
    `kicad_pcb_content_hash` pin, since neither concept applies to a
    fixed-grid perf-board substrate.

    Follows the exact `put_realized_layout`/`put_realized_geometry`
    put-seam pattern (`PayloadStore.put`, fresh digest) via
    :func:`put_realized_board_assignment`.
    """

    model_config = ConfigDict(frozen=True)

    netlist_hash: str
    board_outline_ref: str
    substrate_kind: str
    components: tuple[ComponentAssignment, ...] = ()
    wires: tuple[WireAssignment, ...] = ()


# frob:doc docs/modules/py-realizer.md#elec-realized
def put_realized_board_assignment(
    store: PayloadStore, assignment: RealizedBoardAssignment
) -> str:
    """Store ``assignment`` (kind `board_assignment.realized`) into the
    WO-30 payload store, returning its content digest.

    Same shape as `regolith.realizer.elec.realized.put_realized_layout`
    and `regolith.orchestrator.orchestrate.put_realized_geometry`:
    `PayloadStore.put` (fresh digest), not `put_at` -- the returned
    digest is what a later staged build would supply as a
    `RealizedInput` key.
    """
    data = assignment.model_dump_json().encode("utf-8")
    digest = store.put(data)
    _log.debug(
        "payload store: put board_assignment.realized for netlist_hash=%s digest=%s",
        assignment.netlist_hash,
        digest,
    )
    return digest
