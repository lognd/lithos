"""The docs-agreement sweeps (WO-121, D230): mechanically-checkable
agreement between the docs and the repo they describe, folded into
the health `consistency` leg (D219). Each check is standalone
(`python -m tools.health.docs_agreement [--check NAME]`).

Checks:

* **guide_index** -- `docs/guide/README.md`'s index table lists
  exactly the `docs/guide/*.md` files present (minus README.md
  itself): no phantom row (a file that does not exist), no orphan
  file (a guide with no index row).
* **cli_verbs** -- every backtick-quoted, verb-shaped token in root
  `README.md`'s "## The CLI" section names a REAL top-level `regolith`
  command (introspected from the live typer app, never a second
  hard-coded verb list) or a known magnetite subcommand.
* **dead_names** -- the retired names (`mill`, `loom`, `dcad`, `deda`,
  `quarry`, `lodestone`, and calcite's dead `.calc` draft usage,
  CLAUDE.md's "Names" table) appear nowhere in living docs/source
  outside `docs/workflow/design-log/` (verbatim history) and the
  negative-fixture corpus (`examples/negative/`, which intentionally
  exercises retired-name diagnostics).

Detail is DEBUG; ONE INFO row and a loud verdict, matching every other
health sub-check's shape (`tools.health.consistency`,
`tools.stdlib.organization`).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from regolith.logging_setup import get_logger

from tools.stdlib.organization import SubCheck, is_excluded

_log = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
GUIDE_DIR = REPO_ROOT / "docs" / "guide"


def _guide_index_entries() -> set[str]:
    """Filenames named as `doc` cells in the guide README's index table."""
    text = (GUIDE_DIR / "README.md").read_text()
    return set(re.findall(r"^\|\s*`([\w.-]+\.md)`", text, re.MULTILINE))


def check_guide_index() -> SubCheck:
    """The guide index lists exactly the guide files present."""
    on_disk = {p.name for p in GUIDE_DIR.glob("*.md") if p.name != "README.md"}
    indexed = _guide_index_entries()
    missing_files = sorted(indexed - on_disk)  # indexed but absent (phantom row)
    orphan_files = sorted(on_disk - indexed)  # present but not indexed
    for m in missing_files:
        _log.error("docs_agreement: guide index names missing file %s", m)
    for o in orphan_files:
        _log.error("docs_agreement: guide file %s has no index row", o)
    ok = not missing_files and not orphan_files
    return SubCheck(
        "guide_index",
        ok,
        len(indexed),
        f"{len(missing_files)} phantom, {len(orphan_files)} orphan",
    )


def _real_cli_verbs() -> set[str]:
    """The live set of top-level `regolith` commands (typer introspection,
    never a second hard-coded verb list -- the tripwire this check itself
    exists to catch)."""
    from regolith.cli.app import app
    from typer.main import get_command

    return set(get_command(app).commands.keys())


#: magnetite subcommands the root README cites as its own subtree
#: (`regolith magnetite <name>`), not top-level verbs.
_MAGNETITE_SUBCOMMANDS = frozenset(
    {"new", "vendor", "fetch", "key", "index", "manifest"}
)

#: Words that are verb-shaped (bare lowercase backtick tokens) but name
#: something other than a CLI verb in the CLI section's prose (flags,
#: file/module names, sub-noun phrases) -- reviewed by hand once; a new
#: false positive here should be added with a one-line reason, not
#: silently grown.
_NOT_A_VERB = frozenset(
    {
        "test",  # also a verb; kept for clarity where prose reuses the word
        "get",
        "set",
        "list",
        "where",
        "try",
        "check",  # magnetite manifest check
        "regolith",  # the binary name itself, not a verb
        "magnetite",  # the subtree name itself, not a verb
    }
)


def check_cli_verbs() -> SubCheck:
    """Every verb-shaped backtick token in root README's CLI section
    names a real `regolith` command or magnetite subcommand."""
    text = (REPO_ROOT / "README.md").read_text()
    m = re.search(r"^## The CLI\n(.*?)(?=\n## )", text, re.MULTILINE | re.DOTALL)
    section = m.group(1) if m else ""
    tokens = set(re.findall(r"`([a-z][a-z_]*)`", section))
    real = _real_cli_verbs() | _MAGNETITE_SUBCOMMANDS | _NOT_A_VERB
    stale = sorted(tokens - real)
    for s in stale:
        _log.error("docs_agreement: README CLI section names unknown verb '%s'", s)
    return SubCheck("cli_verbs", not stale, len(tokens), f"{len(stale)} stale token(s)")


#: The retired names (CLAUDE.md "Names" table, D132/D133) and their
#: word-boundary patterns. calcite's dead draft extension `.calc` is
#: checked separately (a substring match would false-positive on
#: "calculate"/"calculation" etc).
_DEAD_NAME_RE = re.compile(r"\b(mill|loom|dcad|deda|quarry|lodestone)\b", re.IGNORECASE)
_DEAD_CALC_EXT_RE = re.compile(r"\.calc\b")

#: Directories where retired names are EXPECTED and never flagged:
#: verbatim design-log history, and the negative corpus (which
#: exercises retired-name diagnostics on purpose).
_DEAD_NAME_ALLOWED_DIRS = (
    Path("docs/workflow/design-log"),
    Path("examples/negative"),
)

#: Words/phrases that make a bare "mill" hit a machining operation
#: (lathe/mill, CNC milling), not the retired language name -- reviewed
#: false positives, grown only with a real new one found.
_MACHINING_MILL_CONTEXT = re.compile(
    r"(cnc|lathe|end.?mill|face.?mill|ball.?mill|3.?axis|drill|router|"
    r"machin|toolpath|g.?code|spindle|std\.machines|family|class|stage|"
    r"process|brake|cut|tool|hole|fit|reach|dfm)",
    re.IGNORECASE,
)

#: Pre-existing one-line "this name is retired" footnotes in normative
#: docs (the CLAUDE.md Names-table convention applied inline: e.g.
#: docs/README.md's own "Retired names: ..." sentence, fluorite/
#: calcite READMEs noting `.calc` is dead, cuprite's open-questions
#: history). These predate this check (WO-121 sweep finding) and are
#: reported (WARNING) but do not gate -- rewriting a normative spec's
#: own historical footnote is a content decision outside this WO's
#: scope, not a structure fix. Placeholder WO121-F1. Reopen: a file
#: is edited for another reason in the same change as removing its
#: retired-name footnote (or the footnote is moved to a design-log
#: entry) -- drop its entry here then.
_DEAD_NAME_FOOTNOTE_BASELINE = frozenset(
    {
        "README.md",
        "TODO.md",
        "docs/README.md",
        "docs/spec/calcite/README.md",
        "docs/spec/cuprite/06-lowering.md",
        "docs/spec/cuprite/08-open-questions.md",
        "docs/spec/fluorite/README.md",
    }
)

#: Scope: the WO-121 README/guide sweep set only (root/docs/guide/
#: stdlib/examples/fuzz/editors READMEs + every guide page), NOT a
#: repo-wide source or corpus sweep. The retired tokens (`mill`
#: especially) are ordinary English words with real, unrelated,
#: legitimate uses throughout the `.hema`/`.cupr` design corpus (a
#: literal CNC mill process) and the normative specs/work-orders
#: (`quarry/trust.py`-era comments, vocabulary sections) that are out
#: of THIS work order's charter to edit; bounding the sweep to the
#: docs this WO actually owns keeps the check both correct and honest
#: about what it covers (a repo-wide dead-name purge is a separate,
#: much larger undertaking, not invented here).
_DEAD_NAME_SCAN_FILES: tuple[Path, ...] = (
    REPO_ROOT / "README.md",
    REPO_ROOT / "TODO.md",
    REPO_ROOT / "docs" / "README.md",
    REPO_ROOT / "stdlib" / "README.md",
    REPO_ROOT / "examples" / "README.md",
    REPO_ROOT / "fuzz" / "README.md",
    REPO_ROOT / "editors" / "vscode" / "README.md",
    REPO_ROOT / "examples" / "hdl" / "README.md",
    REPO_ROOT / "examples" / "negative" / "README.md",
    *sorted((REPO_ROOT / "docs" / "guide").glob("*.md")),
)


def _dead_name_offenders() -> tuple[list[str], list[str]]:
    """`(gating, baseline)` -- every `<file>:<line>` hit of a retired
    name in the docs this WO sweeps, minus "mill" hits that are plainly
    a machining operation, split by the footnote baseline."""
    gating: list[str] = []
    baseline: list[str] = []
    for path in _DEAD_NAME_SCAN_FILES:
        if not path.is_file():
            continue
        rel = path.relative_to(REPO_ROOT)
        if is_excluded(rel):
            continue
        if any(str(rel).startswith(str(d)) for d in _DEAD_NAME_ALLOWED_DIRS):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        hits: list[str] = []
        for i, line in enumerate(text.splitlines(), 1):
            for m in _DEAD_NAME_RE.finditer(line):
                word = m.group(1).lower()
                if word == "mill" and _MACHINING_MILL_CONTEXT.search(line):
                    continue
                hits.append(f"{rel}:{i}: '{m.group(1)}'")
            if _DEAD_CALC_EXT_RE.search(line):
                hits.append(f"{rel}:{i}: '.calc' (dead draft extension)")
        if not hits:
            continue
        if str(rel) in _DEAD_NAME_FOOTNOTE_BASELINE:
            baseline.extend(hits)
        else:
            gating.extend(hits)
    return gating, baseline


def check_dead_names() -> SubCheck:
    """Retired names appear only in design-log history + negative/ (or
    the recorded footnote baseline, report-only, WO121-F1)."""
    gating, baseline = _dead_name_offenders()
    for o in gating:
        _log.error("docs_agreement: retired name outside history: %s", o)
    for o in baseline:
        _log.warning(
            "docs_agreement: retired-name footnote baseline (WO121-F1, "
            "report-only): %s",
            o,
        )
    return SubCheck(
        "dead_names",
        not gating,
        0,
        f"{len(gating)} new, {len(baseline)} baseline (WO121-F1)",
    )


_ALL_CHECKS = {
    "guide_index": check_guide_index,
    "cli_verbs": check_cli_verbs,
    "dead_names": check_dead_names,
}


def run_all() -> list[SubCheck]:
    """Run every docs-agreement sweep; return the list of sub-checks."""
    return [fn() for fn in _ALL_CHECKS.values()]


def main(argv: list[str] | None = None) -> int:
    """Standalone CLI: run one named check (`--check NAME`) or all."""
    import argparse

    parser = argparse.ArgumentParser(description="Docs-agreement sweeps (D230).")
    parser.add_argument("--check", choices=sorted(_ALL_CHECKS), default=None)
    args = parser.parse_args(argv)

    checks = [_ALL_CHECKS[args.check]()] if args.check else run_all()
    ok = True
    for c in checks:
        print(f"  [{'PASS' if c.ok else 'FAIL'}] {c.name:16} {c.note}")
        ok = ok and c.ok
    print("DOCS_AGREEMENT: PASS" if ok else "DOCS_AGREEMENT: FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
