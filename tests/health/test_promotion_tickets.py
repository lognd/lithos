"""WO-162's promotion-ticket gate (AD-22 teeth): a forward-authored
class's ``frob:ticket T-####`` marker must point at an OPEN ticket
(``state: queued`` or ``state: in-progress``) in ``tickets.md``; a
missing, done, or nonexistent ticket is a hard failure.

Uses scratch fixture trees (never the real ``tickets.md`` or repo
source) so this test never depends on -- or drifts with -- the live
ticket ledger's contents.
"""

from __future__ import annotations

from pathlib import Path

from tools.health.promotion_tickets import check, find_markers, load_ticket_states, main

_TICKETS_MD = """\
<!-- ticket:T-1000 -->
```yaml
id: T-1000
title: 'open promotion ticket'
state: queued
kind: feature
```
some prose.

<!-- ticket:T-1001 -->
```yaml
id: T-1001
title: 'closed promotion ticket'
state: done
kind: feature
```
some prose.
"""

_PASSING_SOURCE = '''\
"""Scratch module."""

# frob:ticket T-1000
class ForwardAuthoredThing:
    """A forward-authored, hand-written stand-in, pending promotion."""
'''

_FAILING_SOURCE_DONE = '''\
"""Scratch module."""

# frob:ticket T-1001
class ShouldHavePromoted:
    """A forward-authored stand-in whose ticket already closed."""
'''

_FAILING_SOURCE_MISSING = '''\
"""Scratch module."""

# frob:ticket T-9999
class NoSuchTicket:
    """A forward-authored stand-in pointing at a nonexistent ticket."""
'''


def _write_fixture(tmp_path: Path, source: str) -> tuple[tuple[str, ...], Path]:
    root = tmp_path / "python" / "regolith"
    root.mkdir(parents=True)
    (root / "scratch.py").write_text(source, encoding="utf-8")
    tickets_md = tmp_path / "tickets.md"
    tickets_md.write_text(_TICKETS_MD, encoding="utf-8")
    return ("python/regolith",), tickets_md


# frob:tests tools/health/promotion_tickets.py::check kind="unit"
def test_marker_pointing_at_a_queued_ticket_passes(tmp_path: Path, monkeypatch) -> None:
    roots, tickets_md = _write_fixture(tmp_path, _PASSING_SOURCE)
    monkeypatch.setattr("tools.health.promotion_tickets.REPO_ROOT", tmp_path)
    violations = check(roots=roots, tickets_md=tickets_md)
    assert violations == []


# frob:tests tools/health/promotion_tickets.py::check kind="unit"
def test_marker_pointing_at_a_done_ticket_fails(tmp_path: Path, monkeypatch) -> None:
    roots, tickets_md = _write_fixture(tmp_path, _FAILING_SOURCE_DONE)
    monkeypatch.setattr("tools.health.promotion_tickets.REPO_ROOT", tmp_path)
    violations = check(roots=roots, tickets_md=tickets_md)
    assert len(violations) == 1
    assert violations[0].hit.ticket_id == "T-1001"
    assert "done" in violations[0].reason


# frob:tests tools/health/promotion_tickets.py::check kind="unit"
def test_marker_pointing_at_a_nonexistent_ticket_fails(
    tmp_path: Path, monkeypatch
) -> None:
    roots, tickets_md = _write_fixture(tmp_path, _FAILING_SOURCE_MISSING)
    monkeypatch.setattr("tools.health.promotion_tickets.REPO_ROOT", tmp_path)
    violations = check(roots=roots, tickets_md=tickets_md)
    assert len(violations) == 1
    assert violations[0].hit.ticket_id == "T-9999"
    assert "not found" in violations[0].reason


def test_load_ticket_states_parses_state_field(tmp_path: Path) -> None:
    tickets_md = tmp_path / "tickets.md"
    tickets_md.write_text(_TICKETS_MD, encoding="utf-8")
    states = load_ticket_states(tickets_md)
    assert states == {"T-1000": "queued", "T-1001": "done"}


def test_find_markers_locates_the_marker_above_a_class(
    tmp_path: Path, monkeypatch
) -> None:
    roots, _tickets_md = _write_fixture(tmp_path, _PASSING_SOURCE)
    monkeypatch.setattr("tools.health.promotion_tickets.REPO_ROOT", tmp_path)
    hits = find_markers(roots=roots)
    assert len(hits) == 1
    assert hits[0].class_name == "ForwardAuthoredThing"
    assert hits[0].ticket_id == "T-1000"


# frob:tests tools/health/promotion_tickets.py::main kind="unit"
def test_main_exits_nonzero_on_violation(tmp_path: Path, monkeypatch, capsys) -> None:
    roots, tickets_md = _write_fixture(tmp_path, _FAILING_SOURCE_MISSING)
    monkeypatch.setattr("tools.health.promotion_tickets.REPO_ROOT", tmp_path)
    monkeypatch.setattr("tools.health.promotion_tickets._SCAN_ROOTS", roots)
    monkeypatch.setattr(
        "tools.health.promotion_tickets.check",
        lambda: check(roots=roots, tickets_md=tickets_md),
    )
    assert main() == 1
    out = capsys.readouterr().out
    assert "FAIL" in out
    assert "T-9999" in out


# frob:tests tools/health/promotion_tickets.py::check kind="unit"
def test_no_markers_is_a_clean_pass(tmp_path: Path, monkeypatch) -> None:
    roots, tickets_md = _write_fixture(
        tmp_path, '"""No markers here."""\n\n\nclass Plain:\n    pass\n'
    )
    monkeypatch.setattr("tools.health.promotion_tickets.REPO_ROOT", tmp_path)
    violations = check(roots=roots, tickets_md=tickets_md)
    assert violations == []
