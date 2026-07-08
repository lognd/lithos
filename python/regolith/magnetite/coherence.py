"""Trait-coherence resolution (WO-16).

Spec: regolith/09 sec. 5. The one rulebook for all registry-like
mechanisms: canonical (unordered where applicable) keys; resolution picks
the unique most-specific record or errors; ``override <record> by
<evidence>`` shadows at the same key with a mandatory evidence clause;
``use { A, B }`` / ``use <impl>`` pins ambiguous resolution; every
resolution is lockfile-provenanced.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from regolith.errors import MagnetiteError
from regolith.logging_setup import get_logger
from regolith.magnetite.records import Record

_log = get_logger(__name__)


class ContactKey(BaseModel):
    """A canonical unordered pair key (``contact{A, B}`` == ``contact{B, A}``)."""

    model_config = ConfigDict(frozen=True)

    a: str
    b: str

    def canonical(self) -> tuple[str, str]:
        """The order-independent key: the pair sorted."""
        return (self.a, self.b) if self.a <= self.b else (self.b, self.a)


def _specificity(record: Record) -> int:
    """More dot-qualified keys are more specific (a package-qualified key
    shadows a bare one) -- the coherence rulebook's specificity order."""
    return record.address.key.count(".")


def resolve_most_specific(
    candidates: tuple[Record, ...], pins: tuple[str, ...]
) -> Result[Record, MagnetiteError]:
    """Pick the unique most-specific record among ``candidates``.

    Ambiguous specificity without a ``use`` pin is an error; ``pins``
    disambiguates. Every resolution is recorded for the lockfile (WO-14).
    """
    if not candidates:
        return Err(MagnetiteError(kind="no_candidates", message="no candidate records"))

    max_specificity = max(_specificity(record) for record in candidates)
    most_specific = tuple(
        record for record in candidates if _specificity(record) == max_specificity
    )

    if len(most_specific) == 1:
        winner = most_specific[0]
        _log.debug(
            "resolved %s/%s by specificity", winner.address.package, winner.address.key
        )
        return Ok(winner)

    if pins:
        pinned = tuple(
            record for record in most_specific if record.address.package in pins
        )
        if len(pinned) == 1:
            winner = pinned[0]
            _log.debug(
                "resolved %s/%s by use-pin", winner.address.package, winner.address.key
            )
            return Ok(winner)

    _log.warning(
        "ambiguous coherence resolution among %d candidates: %s",
        len(most_specific),
        [r.address.package for r in most_specific],
    )
    return Err(
        MagnetiteError(
            kind="ambiguous",
            message=(
                "ambiguous resolution among equally specific records: "
                + ", ".join(sorted(r.address.package for r in most_specific))
                + "; use a `use` pin to disambiguate"
            ),
        )
    )
