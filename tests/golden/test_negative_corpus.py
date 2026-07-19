"""Negative corpus: the rule-breaking corpus, self-calibrated against
real compiler output (design-log cycle 23 / D123).

Every file under `examples/negative/` breaks EXACTLY ONE rule and
declares it in a header this driver parses:

    # BREAKS: <one-line rule statement, citing the spec section>
    # EXPECT: E0104            (code(s) the compiler MUST emit today)
    # EXPECT-TODO: INV-4       (known-uncaught: driver xfails -- this IS
    #                           the demand signal for a lint/check)
    # WITH: stdlib/std.board_correctness   (optional: extra session
    #                           roots, repo-root-relative -- a fixture
    #                           whose break needs attached rule packs
    #                           in session; WO-87. A WITH fixture also
    #                           gets the registry-records payload, the
    #                           same input the CLI resolves by default)

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
_WITH_RE = re.compile(r"^#\s*WITH:\s*(.+)$")


@dataclass(frozen=True)
class NegativeHeader:
    """One fixture's parsed `# BREAKS:`/`# EXPECT*:` header contract."""

    path: Path
    breaks: str
    expect_codes: tuple[str, ...]
    expect_todo: str | None
    with_roots: tuple[str, ...] = ()


def _parse_header(path: Path) -> NegativeHeader:
    """Read the leading `#`-comment block and extract the header
    contract. Only the FIRST matching line of each directive counts
    (one rule per file -- the corpus's own discipline)."""
    breaks = ""
    expect_codes: tuple[str, ...] = ()
    expect_todo: str | None = None
    with_roots: tuple[str, ...] = ()
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
            elif m := _WITH_RE.match(stripped):
                with_roots = tuple(m.group(1).strip().split())
    assert breaks, f"{path}: missing # BREAKS: header"
    assert expect_codes or expect_todo, f"{path}: no # EXPECT:/# EXPECT-TODO: header"
    return NegativeHeader(
        path=path,
        breaks=breaks,
        expect_codes=expect_codes,
        expect_todo=expect_todo,
        with_roots=with_roots,
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
        "lint": 800,
    }
    codes = []
    for diag in payload["diagnostics"]:  # type: ignore[index]
        code = diag["code"]
        family = code["family"]
        number = bases[family] + code["offset"]
        prefix = "L" if family == "lint" else "E"
        codes.append(f"{prefix}{number:04d}")
    return codes


def _discover_fixtures() -> list[Path]:
    if not _NEGATIVE_DIR.is_dir():
        return []
    # Extension strings come from the ONE registry (ground rule 6 /
    # AD-14), reached through the compiled extension, never hard-coded
    # here (the WO-47 tripwire: adding `.calx` at cycle 26 must not
    # require touching this suffix tuple by hand).
    suffixes = tuple(f".{ext}" for ext, _lang in compiler.extensions())
    # `.test.<ext>` files are DESIGN TESTS (WO-83, charter toolchain/37
    # sec. 1.1's discovery convention), not negative fixtures: the
    # diagnostic-expectation negative TWINS live beside their broken
    # subjects here but carry a `test <name>:` declaration, not a
    # `# BREAKS:` contract -- `regolith test` is their driver.
    return sorted(
        p
        for p in _NEGATIVE_DIR.iterdir()
        if p.suffix in suffixes and p.is_file() and ".test." not in p.name
    )


_FIXTURES = _discover_fixtures()


@pytest.mark.parametrize("fixture", _FIXTURES, ids=[p.name for p in _FIXTURES])
# frob:tests python/regolith/magnetite/records_payload.py::registry_records_payload kind="unit"
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

    # `# WITH:` fixtures (WO-87) need extra roots in session (attached
    # rule packs) plus the registry-records payload -- the same inputs
    # the CLI `check` verb resolves by default.
    roots: tuple[str, ...] = (str(fixture),)
    realized_inputs: tuple[compiler.RealizedInput, ...] = ()
    if header.with_roots:
        repo_root = _NEGATIVE_DIR.parent.parent
        roots = roots + tuple(str(repo_root / w) for w in header.with_roots)
        from regolith.magnetite.records_payload import registry_records_payload

        payload_tuple = registry_records_payload((str(repo_root / "stdlib"),))
        if payload_tuple is not None:
            digest, kind, subject, payload_bytes = payload_tuple
            realized_inputs = (
                compiler.RealizedInput(
                    digest=digest,
                    kind=kind,
                    subject=subject,
                    payload_bytes=payload_bytes,
                ),
            )

    result = compiler.check(roots, realized_inputs=realized_inputs)
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
