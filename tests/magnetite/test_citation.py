"""WO-145/D257 ruling 2: the structured citation models.

An uncited datasheet value must be unrepresentable at the type level
-- these tests prove `Cited`/`CitedInterval` refuse construction
without a `Citation` (a pydantic `ValidationError`/`TypeError`, never
a runtime `if not citation: raise` check a caller could route around).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from regolith.magnetite.citation import Citation, Cited, CitedInterval, MeasCondition

_CITATION_KWARGS = dict(
    manufacturer="Texas Instruments",
    document="SLASE54D",
    revision="D",
    date="2021-01",
    page=29,
    table="8.1 Absolute Maximum Ratings",
    url="https://www.ti.com/lit/gpn/msp430fr5994",
)


def test_citation_constructs_with_every_field() -> None:
    citation = Citation(**_CITATION_KWARGS)
    assert citation.document == "SLASE54D"
    assert citation.page == 29


def test_citation_rejects_missing_field() -> None:
    kwargs = dict(_CITATION_KWARGS)
    del kwargs["page"]
    with pytest.raises(ValidationError):
        Citation(**kwargs)


def test_cited_requires_a_citation_at_construction() -> None:
    """No public constructor for a bare value: omitting `citation`
    entirely is a pydantic validation error, not a silently-accepted
    uncited value."""
    with pytest.raises(ValidationError):
        Cited(value=4.1)  # type: ignore[call-arg]


def test_cited_constructs_with_value_and_citation() -> None:
    cited = Cited(value=4.1, citation=Citation(**_CITATION_KWARGS), confirmed=True)
    assert cited.value == 4.1
    assert cited.confirmed is True
    assert cited.citation.document == "SLASE54D"


def test_cited_confirmed_defaults_false() -> None:
    """An auto-extracted value that has not yet been reviewed defaults
    to `confirmed=False` (D257 ruling 3's human-in-the-loop gate)."""
    cited = Cited(value=1, citation=Citation(**_CITATION_KWARGS))
    assert cited.confirmed is False


def test_cited_interval_requires_a_citation() -> None:
    with pytest.raises(ValidationError):
        CitedInterval(lo=-0.3, hi=4.1, unit="V")  # type: ignore[call-arg]


def test_cited_interval_carries_a_symbolic_bound() -> None:
    """The TI SLASE54D 'VCC + 0.3 V' any-pin absolute-maximum bound: a
    symbolic upper bound is representable as a string, honestly, rather
    than silently collapsed to its resolved numeric worst case."""
    interval = CitedInterval(
        lo=-0.3,
        hi="VCC + 0.3 V",
        unit="V",
        citation=Citation(**_CITATION_KWARGS),
        confirmed=True,
    )
    assert interval.hi == "VCC + 0.3 V"
    assert isinstance(interval.lo, float)


def test_cited_interval_carries_a_meas_condition() -> None:
    """The SLASE54D fSYSTEM case: the same parameter under two named
    wait-state conditions must not collapse to one number."""
    no_wait = CitedInterval(
        lo=0.0,
        hi=8.0,
        unit="MHz",
        citation=Citation(**_CITATION_KWARGS),
        conditions=MeasCondition(note="NWAITSx = 0 (no FRAM wait states)"),
        confirmed=True,
    )
    with_wait = CitedInterval(
        lo=0.0,
        hi=16.0,
        unit="MHz",
        citation=Citation(**_CITATION_KWARGS),
        conditions=MeasCondition(note="NWAITSx = 1 (FRAM wait states)"),
        confirmed=True,
    )
    assert no_wait.hi != with_wait.hi
    assert no_wait.conditions.note != with_wait.conditions.note


def test_models_are_frozen() -> None:
    citation = Citation(**_CITATION_KWARGS)
    with pytest.raises(ValidationError):
        citation.page = 30  # type: ignore[misc]
