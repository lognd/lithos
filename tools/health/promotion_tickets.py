"""The ``promotion-tickets`` health leg (WO-162, AD-22 teeth, D267).

Every forward-authored contract type (a hand-written stand-in for a
not-yet-promoted, properly-schema'd type -- today's standing instance
is ``FeatureProgram`` in ``regolith.realizer.mech.schema``, per
hematite/07 sec. 2a's deferral) must carry a ``frob:ticket T-####``
directive immediately above its class definition, same DSL family as
``frob:doc``/``frob:tests``/``frob:invariant``/``frob:todo``/
``frob:waive`` (this repo's CLAUDE.md). Promotion (landing the real
schema'd type) closes that ticket AND deletes the shadow type in the
SAME change -- never separately.

Enforcement home (WO-162 deliverable 3): this leg, not a ``frob.toml``
``[[policy]]`` rule. ``frob.policy`` only supports three rule kinds --
``forbidden-import``, ``pattern`` (a tree-sitter query over syntax
shape), and ``norm`` (a max-diff-lines budget) -- per
``frob.policy.PolicyKind`` (``../frob/src/frob/policy/_models.py``).
None of the three can express "the ticket ID this directive names must
be `state: queued` or `state: in-progress` in ``tickets.md``": that is
a cross-file semantic lookup (parse the marker's ticket id, then parse
``tickets.md``'s ticket ledger, then join on id), not a syntax-local
tree-sitter match or an import-forbidding rule. Home (b) -- a small
``tools/`` script mirroring ``tools/health``'s existing D264-exception
pattern (``check.py``'s ``make check`` shell-out precedent) -- is the
only home that can express the join, so this WO takes it.

A forward-authored type with a missing/closed/nonexistent ticket is a
hard failure (``main`` exits 1); a properly promoted type (marker
removed in the same change the ticket closes) never trips this leg
again -- nothing to find.
"""

# frob:waive TEST003 reason="each function has a direct unit test; exercised end to end by make check/make promotion-tickets-check (not in-test), same posture as tools/health/check.py"

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from regolith.logging_setup import get_logger

_log = get_logger(__name__)

# frob:doc docs/modules/tools.md#health-promotion-tickets-leg
REPO_ROOT = Path(__file__).resolve().parents[2]

#: Directories the marker scan walks; keep this list small and explicit
#: rather than "the whole repo" so a stray hit in generated/vendored
#: trees never becomes a build failure (mirrors ``frob.toml``'s
#: ``[graph] exclude`` posture for ``_schema``/``_codes``).
_SCAN_ROOTS = ("python/regolith",)

#: One line: ``# frob:ticket T-####`` (optional trailing ``reason=...``,
#: same convention as ``frob:waive``), immediately above a ``class``
#: definition.
_MARKER_RE = re.compile(r"^\s*#\s*frob:ticket\s+(T-\d+)\b")
_CLASS_RE = re.compile(r"^\s*class\s+\w+")

#: Ticket states the WO-162 gate treats as "the promotion is still
#: pending, honestly" -- anything else (``done``, or the id missing
#: from ``tickets.md`` entirely) is a violation.
_OPEN_STATES = frozenset({"queued", "in-progress"})

_TICKET_BLOCK_RE = re.compile(
    r"<!--\s*ticket:(T-\d+)\s*-->\s*```yaml\n(.*?)```", re.DOTALL
)
_TICKET_STATE_RE = re.compile(r"^state:\s*(\S+)", re.MULTILINE)


# frob:doc docs/modules/tools.md#health-promotion-tickets-leg
@dataclass(frozen=True)
class MarkerHit:
    """One ``frob:ticket`` marker found above a forward-authored class."""

    file: Path
    line: int
    class_name: str
    ticket_id: str


# frob:doc docs/modules/tools.md#health-promotion-tickets-leg
@dataclass(frozen=True)
class Violation:
    """One marker whose referenced ticket is missing, done, or absent."""

    hit: MarkerHit
    reason: str


# frob:doc docs/modules/tools.md#health-promotion-tickets-leg
# frob:tests tests/health/test_promotion_tickets.py::test_load_ticket_states_parses_state_field kind="unit"
def load_ticket_states(tickets_md: Path) -> dict[str, str]:
    """Parse ``tickets.md``'s ledger into ``{ticket_id: state}``.

    Missing/unparsable ``state:`` fields are absent from the returned
    mapping (never defaulted to "open") so a malformed ticket block
    reads as "ticket not found," the same honest failure as a
    nonexistent id.
    """
    text = tickets_md.read_text(encoding="utf-8")
    states: dict[str, str] = {}
    for match in _TICKET_BLOCK_RE.finditer(text):
        ticket_id, body = match.group(1), match.group(2)
        state_match = _TICKET_STATE_RE.search(body)
        if state_match:
            states[ticket_id] = state_match.group(1).strip("'\"")
    return states


# frob:doc docs/modules/tools.md#health-promotion-tickets-leg
# frob:tests tests/health/test_promotion_tickets.py::test_find_markers_locates_the_marker_above_a_class kind="unit"
def find_markers(roots: tuple[str, ...] = _SCAN_ROOTS) -> list[MarkerHit]:
    """Scan ``roots`` for ``frob:ticket`` markers immediately above a class."""
    hits: list[MarkerHit] = []
    for root in roots:
        base = REPO_ROOT / root
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            lines = path.read_text(encoding="utf-8").splitlines()
            for idx, line in enumerate(lines):
                marker = _MARKER_RE.match(line)
                if not marker:
                    continue
                # The class def is the next non-comment, non-blank line
                # (other frob:* directives / decorators may sit between).
                for lookahead in lines[idx + 1 :]:
                    stripped = lookahead.strip()
                    if (
                        not stripped
                        or stripped.startswith("#")
                        or stripped.startswith("@")
                    ):
                        continue
                    class_match = _CLASS_RE.match(lookahead)
                    if class_match:
                        name = (
                            lookahead.split("class", 1)[1]
                            .strip()
                            .split("(")[0]
                            .split(":")[0]
                            .strip()
                        )
                        hits.append(
                            MarkerHit(
                                file=path,
                                line=idx + 1,
                                class_name=name,
                                ticket_id=marker.group(1),
                            )
                        )
                    break
    return hits


# frob:doc docs/modules/tools.md#health-promotion-tickets-leg
def check(
    roots: tuple[str, ...] = _SCAN_ROOTS,
    tickets_md: Path | None = None,
) -> list[Violation]:
    """Return every ``frob:ticket`` marker whose ticket is not open.

    A ticket id absent from ``tickets.md`` entirely, or present with a
    ``state`` outside ``{queued, in-progress}`` (most notably ``done``),
    is a violation -- this is the AD-22 teeth WO-162 adds: an unbound
    or stale-bound forward-authored type is a build failure, not a
    documented convention.
    """
    tickets_path = tickets_md if tickets_md is not None else REPO_ROOT / "tickets.md"
    states = load_ticket_states(tickets_path)
    violations: list[Violation] = []
    for hit in find_markers(roots):
        state = states.get(hit.ticket_id)
        if state is None:
            violations.append(
                Violation(hit=hit, reason=f"{hit.ticket_id} not found in tickets.md")
            )
        elif state not in _OPEN_STATES:
            violations.append(
                Violation(
                    hit=hit,
                    reason=f"{hit.ticket_id} is state={state!r}, not queued/in-progress",
                )
            )
    return violations


# frob:doc docs/modules/tools.md#health-promotion-tickets-leg
# frob:tests tests/health/test_promotion_tickets.py::test_main_exits_nonzero_on_violation kind="unit"
def main() -> int:
    """Run the promotion-tickets leg standalone; exit 0 iff every
    forward-authored marker points at an open ticket."""
    violations = check()
    if not violations:
        _log.info("promotion-tickets: 0 forward-authored markers unbound")
        print("promotion-tickets: pass (0 unbound forward-authored markers)")
        return 0
    for violation in violations:
        _log.error(
            "promotion-tickets: %s:%d class=%s ticket=%s: %s",
            violation.hit.file,
            violation.hit.line,
            violation.hit.class_name,
            violation.hit.ticket_id,
            violation.reason,
        )
        print(
            f"promotion-tickets: FAIL {violation.hit.file}:{violation.hit.line} "
            f"class={violation.hit.class_name}: {violation.reason}"
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
