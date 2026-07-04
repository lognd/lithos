"""Trait-coherence resolution (WO-16).

Spec: substrate/09 sec. 5. The one rulebook for all registry-like
mechanisms: canonical (unordered where applicable) keys; resolution picks
the unique most-specific record or errors; ``override <record> by
<evidence>`` shadows at the same key with a mandatory evidence clause;
``use { A, B }`` / ``use <impl>`` pins ambiguous resolution; every
resolution is lockfile-provenanced.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from typani.result import Result

from rockhead.errors import QuarryError
from rockhead.quarry.records import Record


class ContactKey(BaseModel):
    """A canonical unordered pair key (``contact{A, B}`` == ``contact{B, A}``)."""

    model_config = ConfigDict(frozen=True)

    a: str
    b: str

    def canonical(self) -> tuple[str, str]:
        """The order-independent key: the pair sorted."""
        return (self.a, self.b) if self.a <= self.b else (self.b, self.a)


def resolve_most_specific(
    candidates: tuple[Record, ...], pins: tuple[str, ...]
) -> Result[Record, QuarryError]:
    """Pick the unique most-specific record among ``candidates``.

    Ambiguous specificity without a ``use`` pin is an error; ``pins``
    disambiguates. Every resolution is recorded for the lockfile (WO-14).
    """
    raise NotImplementedError(
        "STUB WO-16: unique-most-specific-or-error; apply use-pins; record provenance"
    )
