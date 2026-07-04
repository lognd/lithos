"""INV-14 Trust totality (substrate/13-invariants.md).

Ledger statement:
    **Every evidence item -- registry records, overrides, test reports,
    deviations -- carries a trust tier, and trust floors compare totally.**

Mechanism provided by: WO-16 (quarry trust). Trust is decided locally from
signatures on the content (substrate/11 sec. 10.4), never from where it
was hosted; the tiers form a total order so a claim group's floor compares
totally. This is the deliberate-violation fixture the ledger statement
requires: content below the floor stays below it, never a silent upgrade.
"""

from __future__ import annotations

from rockhead.quarry import KeySet, Signature, TrustTier, verify_trust


def test_inv_14_tiers_are_a_total_order() -> None:
    """certified > tested > community, compared totally (floors are total)."""
    assert TrustTier.CERTIFIED > TrustTier.TESTED > TrustTier.COMMUNITY
    assert TrustTier.CERTIFIED.meets(TrustTier.TESTED)
    assert not TrustTier.COMMUNITY.meets(TrustTier.TESTED)


def test_inv_14_hosting_confers_no_trust() -> None:
    """Only a trusted signature over the exact bytes earns a tier."""
    content = "blake3:record"
    keyset = KeySet(ceilings=(("authority.mmpds", TrustTier.CERTIFIED),))
    # Unsigned content is community -- the honest floor.
    assert verify_trust(content, (), keyset) == TrustTier.COMMUNITY
    # A trusted authority signature over these exact bytes earns certified.
    good = Signature(
        key_id="authority.mmpds", grants=TrustTier.CERTIFIED, over_hash=content
    )
    assert verify_trust(content, (good,), keyset) == TrustTier.CERTIFIED


def test_inv_14_below_floor_stays_below_floor() -> None:
    """An untrusted key cannot upgrade a community record past a tested floor."""
    content = "blake3:record"
    keyset = KeySet(ceilings=(("authority.mmpds", TrustTier.CERTIFIED),))
    forged = Signature(key_id="stranger", grants=TrustTier.CERTIFIED, over_hash=content)
    earned = verify_trust(content, (forged,), keyset)
    assert earned == TrustTier.COMMUNITY
    # A `tested` floor is not met by community content (INV-14 totality).
    assert not earned.meets(TrustTier.TESTED)
