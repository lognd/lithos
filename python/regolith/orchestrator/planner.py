"""The planner-model shape (WO-26 D105c): one home, no new evidence kind.

D105(c): a plan artifact is a ``plan``-kind payload on the D96 channel
(content-addressed through the orchestrator :class:`PayloadStore`), and
every lockfile row a planner pins carries ``cause: planner(<what>)``
(regolith/07 sec. 6's "plan = evidence", INV-21 provenance) -- NO new
evidence shape. This module is that shape's single home: the cause
formatter every planner writes through, and the adapter base class
that turns a planner's decisions into its content-addressed payload
ref plus lockfile rows. The WO-24 binding search and the WO-35 pin-mux
planner are the retrofitted customers (their cause literals moved
here; one shape, NO DUPLICATION).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from regolith._schema.models import PayloadRef
from regolith.logging_setup import get_logger
from regolith.orchestrator.lockfile import LockRow
from regolith.orchestrator.payload_store import PayloadStore

_log = get_logger(__name__)

# The D96 payload-kind vocabulary entry a plan artifact rides
# (feldspar 09 sec. 4, adopted verbatim). One home for the string.
PLAN_PAYLOAD_KIND = "plan"


def planner_cause(what: str) -> str:
    """Render the INV-21 planner cause: ``planner(<what>)``.

    Every lockfile row a planner pins goes through this ONE formatter
    (D105c); nothing else spells the ``planner(...)`` cause by hand.
    """
    return f"planner({what})"


class PlannerAdapter(ABC):
    """A planner's evidence shape: plan artifact + caused lockfile rows.

    Subclasses (the WO-24 binding result, the WO-35 pin-mux result)
    provide their identity (:attr:`what`), the canonical plan bytes,
    and the rows their decisions pin; the base owns payload publication
    (content addressing via the store) and the cause rendering.
    """

    @property
    @abstractmethod
    def what(self) -> str:
        """What this planner decided (the ``planner(<what>)`` cause tail)."""

    @abstractmethod
    def plan_bytes(self) -> bytes:
        """The canonical serialized plan artifact (deterministic bytes)."""

    @abstractmethod
    def lock_rows(self) -> tuple[LockRow, ...]:
        """The lockfile rows this plan pins, each planner-caused."""

    @property
    def cause(self) -> str:
        """This plan's rendered lockfile cause."""
        return planner_cause(self.what)

    def publish(self, store: PayloadStore) -> PayloadRef:
        """Content-address the plan artifact as a ``plan``-kind payload.

        The returned ref is the D96 channel handle an obligation (or a
        ship manifest) carries; the artifact bytes live in the store
        under their own digest, exactly like every other payload kind.
        """
        digest = store.put(self.plan_bytes())
        _log.debug(
            "published plan artifact what=%s digest=%s bytes=%d",
            self.what,
            digest,
            len(self.plan_bytes()),
        )
        return PayloadRef(kind=PLAN_PAYLOAD_KIND, digest=digest, origin=self.what)
