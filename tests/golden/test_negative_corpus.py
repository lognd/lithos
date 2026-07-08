"""Negative corpus: the rule-breaking corpus, self-calibrated against
real compiler output (design-log cycle 23 / D123).

Every file under `examples/negative/` breaks EXACTLY ONE rule and
declares it in a header this driver parses:

    # BREAKS: <one-line rule statement, citing the spec section>
    # EXPECT: E0104            (code(s) the compiler MUST emit today)
    # EXPECT-TODO: INV-4       (known-uncaught: driver xfails -- this IS
    #                           the demand signal for a lint/check)

This suite runs `regolith.compiler.check` over each `EXPECT` fixture
and asserts every declared code appears in that file's diagnostics.
`EXPECT-TODO` fixtures are `pytest.xfail`ed by name (they document a
known compiler gap, not a driver bug) -- see each fixture's own
"Self-calibration" comment for what was actually observed. `.fluo`
fixtures ride the same contract as `.hema`/`.cupr` now that the
extension is registered (WO-31): fluid-discipline breaks that the
front end catches carry `# EXPECT: E02xx`; breaks that need WO-32
lowering data (medium mixing, wall compliance) carry `# EXPECT-TODO:
WO-32`.

This suite is NOT part of `_CORPUS` in `test_golden_corpus.py` /
`test_deferral_corpus.py` -- it is its own gate, walking
`examples/negative/` directly. Regeneration-free: there is no golden
file here, only the header contract plus live compiler output: no
`REGOLITH_UPDATE_GOLDEN` step, ever. If a header's `EXPECT` code stops
firing, this suite FAILS (a real regression); if a previously-silent
rule starts firing, flip its `EXPECT-TODO` to `EXPECT` by hand -- never
mechanically.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

import pytest
from regolith import compiler

_log = logging.getLogger(__name__)

_NEGATIVE_DIR = Path(__file__).parent.parent.parent / "examples" / "negative"

_BREAKS_RE = re.compile(r"^#\s*BREAKS:\s*(.+)$")
_EXPECT_RE = re.compile(r"^#\s*EXPECT:\s*(.+)$")
_EXPECT_TODO_RE = re.compile(r"^#\s*EXPECT-TODO:\s*(.+)$")


@dataclass(frozen=True)
class NegativeHeader:
    """One fixture's parsed `# BREAKS:`/`# EXPECT*:` header contract."""

    path: Path
    breaks: str
    expect_codes: tuple[str, ...]
    expect_todo: str | None


def _parse_header(path: Path) -> NegativeHeader:
    """Read the leading `#`-comment block and extract the header
    contract. Only the FIRST matching line of each directive counts
    (one rule per file -- the corpus's own discipline)."""
    breaks = ""
    expect_codes: tuple[str, ...] = ()
    expect_todo: str | None = None
    with path.open(encoding="ascii") as handle:
        for line in handle:
            stripped = line.rstrip("\n")
            if not stripped.startswith("#"):
                if stripped.strip() == "":
                    continue
                break
            if m := _BREAKS_RE.match(stripped):
                breaks = m.group(1).strip()
            elif m := _EXPECT_RE.match(stripped):
                expect_codes = tuple(m.group(1).strip().split())
            elif m := _EXPECT_TODO_RE.match(stripped):
                expect_todo = m.group(1).strip()
    assert breaks, f"{path}: missing # BREAKS: header"
    assert expect_codes or expect_todo, f"{path}: no # EXPECT:/# EXPECT-TODO: header"
    return NegativeHeader(
        path=path,
        breaks=breaks,
        expect_codes=expect_codes,
        expect_todo=expect_todo,
    )


def _diagnostic_codes(payload: dict[str, object]) -> list[str]:
    """Render each diagnostic's `{family, offset}` code as `E0301`-style
    text, matching `regolith_diag::DiagCode`'s `Display` (family base +
    offset, zero-padded to 4 digits)."""
    bases = {
        "parse": 100,
        "fluid_net": 200,
        "references": 300,
        "contracts": 400,
        "instances": 500,
        "rule_packs": 600,
        "evidence": 700,
    }
    codes = []
    for diag in payload["diagnostics"]:  # type: ignore[index]
        code = diag["code"]
        number = bases[code["family"]] + code["offset"]
        codes.append(f"E{number:04d}")
    return codes


def _discover_fixtures() -> list[Path]:
    if not _NEGATIVE_DIR.is_dir():
        return []
    return sorted(
        p
        for p in _NEGATIVE_DIR.iterdir()
        if p.suffix in (".hema", ".cupr", ".fluo") and p.is_file()
    )


_FIXTURES = _discover_fixtures()


@pytest.mark.parametrize("fixture", _FIXTURES, ids=[p.name for p in _FIXTURES])
def test_negative_fixture(fixture: Path) -> None:
    """Each fixture's header contract holds against live compiler output."""
    header = _parse_header(fixture)
    _log.info(
        "negative corpus fixture=%s breaks=%r expect=%r expect_todo=%r",
        fixture.name,
        header.breaks,
        header.expect_codes,
        header.expect_todo,
    )

    if header.expect_todo is not None:
        pytest.xfail(
            f"{fixture.name}: known-uncaught ({header.expect_todo}) -- "
            f"breaks {header.breaks!r}; demand signal for a lint/invariant "
            "check, see examples/negative/README.md"
        )

    result = compiler.check((str(fixture),))
    assert result.is_ok, f"check({fixture}) returned Err: {result}"
    outcome = result.danger_ok
    payload = json.loads(outcome.payload_json)
    codes = _diagnostic_codes(payload)
    for expected in header.expect_codes:
        assert expected in codes, (
            f"{fixture.name}: expected {expected} in diagnostics, got "
            f"{codes} -- breaks {header.breaks!r}"
        )


def test_inv20_gating_on_parse_poison_fixture() -> None:
    """INV-20 check gating, under direct test: a poisoned subject in one
    declaration must not block an unrelated clean sibling subject in the
    SAME file from lowering to an obligation (design-log cycle 23 / D123
    explicit requirement)."""
    fixture = _NEGATIVE_DIR / "01_parse_poison.hema"
    assert fixture.is_file(), "01_parse_poison.hema must exist"
    result = compiler.check((str(fixture),))
    assert result.is_ok
    payload = json.loads(result.danger_ok.payload_json)
    codes = _diagnostic_codes(payload)
    assert "E0193" in codes, f"the poisoned `bad` part must still report E0193: {codes}"
    obligation_names = [ob["claim"]["name"] for ob in payload["obligations"]]
    assert "clean" in obligation_names, (
        "the clean sibling part `good` must still lower to an obligation "
        f"despite `bad`'s poison (INV-20 check gating): {obligation_names}"
    )
