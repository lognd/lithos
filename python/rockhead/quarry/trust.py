"""Trust tiers and signature verification (substrate/11 sec. 7 + 10; INV-14).

Trust is a property of *signatures on a record*, verified locally against
the consumer's key set -- never a property of where a package was fetched
from (substrate/11 sec. 10.4). A certified MMPDS record is certified from
any mirror; no registry operator can mint certification by hosting. The
tiers form a total order (``certified > tested > community``) so a claim
group's trust floor compares totally (INV-14): a signature below the floor
is not an error, it downgrades the usable tier.
"""

from __future__ import annotations

from enum import IntEnum

from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from rockhead.errors import QuarryError
from rockhead.logging_setup import get_logger

_log = get_logger(__name__)


class TrustTier(IntEnum):
    """The total order of evidence trust (substrate/11 sec. 7).

    The integer value IS the rank, so ``TrustTier.CERTIFIED > TrustTier.
    TESTED`` and floor comparison are the same fact (INV-14 totality).
    """

    COMMUNITY = 0  # unsigned
    TESTED = 1  # attached test reports
    CERTIFIED = 2  # authority/vendor-signed

    def meets(self, floor: TrustTier) -> bool:
        """True iff this tier satisfies a required ``floor`` (>= in order)."""
        return self >= floor


_TIER_BY_NAME = {t.name.lower(): t for t in TrustTier}


def tier_from_name(name: str) -> Result[TrustTier, QuarryError]:
    """Parse a tier name (``certified``/``tested``/``community``) totally."""
    tier = _TIER_BY_NAME.get(name.strip().lower())
    if tier is None:
        return Err(
            QuarryError(
                kind="unknown_trust_tier", message=f"unknown trust tier {name!r}"
            )
        )
    return Ok(tier)


class Signature(BaseModel):
    """A signature on a record: which key signed it, and the tier it grants."""

    model_config = ConfigDict(frozen=True)

    key_id: str
    grants: TrustTier
    # The signed content hash the signature vouches for (INV-22 binding):
    # a signature is only meaningful against the exact bytes it covers.
    over_hash: str


class KeySet(BaseModel):
    """The consumer's trusted keys and the maximum tier each may grant.

    A key present here is trusted up to its mapped tier; a signature by an
    unknown key, or one claiming a tier above its key's ceiling, does not
    count. Hosting is deliberately absent -- trust is decided entirely by
    this local set (substrate/11 sec. 10.4).
    """

    model_config = ConfigDict(frozen=True)

    ceilings: tuple[tuple[str, TrustTier], ...] = ()

    def ceiling(self, key_id: str) -> TrustTier | None:
        """The maximum tier ``key_id`` may grant, or ``None`` if untrusted."""
        for kid, tier in self.ceilings:
            if kid == key_id:
                return tier
        return None


def verify_trust(
    content_hash: str,
    signatures: tuple[Signature, ...],
    keyset: KeySet,
) -> TrustTier:
    """The tier a record earns from its signatures, verified locally.

    Returns the HIGHEST tier for which some signature (a) is over exactly
    ``content_hash`` (INV-22: the signature must cover the pinned bytes),
    (b) is by a key in ``keyset``, and (c) claims a tier at or below that
    key's ceiling. Unsigned or unverifiable content is ``community`` -- the
    honest floor, never a silent upgrade.
    """
    earned = TrustTier.COMMUNITY
    for sig in signatures:
        if sig.over_hash != content_hash:
            _log.debug("signature by %s ignored: covers other bytes", sig.key_id)
            continue
        ceiling = keyset.ceiling(sig.key_id)
        if ceiling is None:
            _log.debug("signature by untrusted key %s ignored", sig.key_id)
            continue
        granted = min(sig.grants, ceiling)
        if granted > earned:
            earned = granted
    _log.debug("verified trust tier %s for %s", earned.name, content_hash)
    return earned
