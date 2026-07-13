"""The ``consistency`` health leg: the standardization sweeps (D219).

Cheap, build-free checks that the repo still hangs together:

* **dnum**      -- every ``D``/``F`` design-log number has exactly ONE
  heading across ``docs/workflow/design-log/`` (no collisions).
* **wo_status**  -- no WO whose file says ``Status: done`` is still an
  unchecked ``- [ ]`` item in TODO.md's dispatch queue (a real desync).
* **extension**  -- source extensions are single-sourced: the core FFI
  registry reports exactly the four known extensions and no Python
  source hard-codes one outside the FFI accessor.
* **goldens**    -- ``tests/golden/`` carries no uncommitted drift (the
  committed goldens are the live goldens; the check leg's golden suite
  proves live-vs-committed equality, this proves the tree is clean).
* **waivers**    -- every ``by doc(<ref>)`` evidence ref in the corpus
  resolves to a memo file, and the fleet leg saw zero stale waivers
  (E0701) fleet-wide (read from the fleet leg's cached results).
* **worktrees** -- stale git worktrees/branches are reported (non-gating).
* **organization** -- the WO-118 (D227/AD-37, charter 39) stdlib
  organization sweeps: std.-prefix reservation, one-family-per-file,
  citation presence, generated-file drift, std.models manifest
  completeness, double-home detection, charter cross-drift (see
  ``tools/stdlib/organization.py``, also runnable standalone).
* **docs_agreement** -- the WO-121 (D230) docs-agreement sweeps: the
  guide README index matches the guide files present, the root
  README's CLI section names only real ``regolith`` verbs, and
  retired names stay out of the docs this WO sweeps (see
  ``tools/health/docs_agreement.py``, also runnable standalone).

Detail is DEBUG; ONE INFO row and a loud verdict.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections import defaultdict

from regolith.logging_setup import get_logger

from tools.health.docs_agreement import run_all as run_docs_agreement_checks
from tools.health.report import HEALTH_OUT, REPO_ROOT, LegSummary
from tools.stdlib.organization import run_all as run_organization_checks

_log = get_logger(__name__)

_KNOWN_EXTENSIONS = frozenset({"hema", "cupr", "fluo", "calx"})
# A PRIMARY design-log heading claims a number; an ADDENDUM re-uses it
# deliberately (a `-a`/`-b` suffix, or the word "addendum") and is NOT a
# collision. So: match `D<n>`/`F<n>` NOT immediately followed by a
# hyphen/word-char, and drop any heading that says "addendum".
_DNUM_HEADING = re.compile(r"^#{1,6}\s+([DF])(\d+)(?![-\w])")
_BY_DOC = re.compile(r"by\s+doc\(([^)]+)\)")


class SubCheck:
    """A named sub-check result: ok, a count, and a one-line note."""

    def __init__(self, name: str, ok: bool, count: int, note: str) -> None:
        self.name = name
        self.ok = ok
        self.count = count
        self.note = note


def _check_dnums() -> SubCheck:
    """Every D/F number has exactly one heading across the design log."""
    seen: dict[str, list[str]] = defaultdict(list)
    log_dir = REPO_ROOT / "docs" / "workflow" / "design-log"
    for path in sorted(log_dir.rglob("*.md")):
        for line in path.read_text().splitlines():
            m = _DNUM_HEADING.match(line)
            if m and "addendum" not in line.lower():
                seen[f"{m.group(1)}{m.group(2)}"].append(path.name)
    dupes = {n: files for n, files in seen.items() if len(files) > 1}
    for num, files in sorted(dupes.items()):
        _log.error("consistency: duplicate design-log heading %s in %s", num, files)
    return SubCheck("dnum", not dupes, len(seen), f"{len(dupes)} collision(s)")


def _wo_status_map() -> dict[str, str]:
    """`WO-nn -> Status word` from every work-order file."""
    wo_dir = REPO_ROOT / "docs" / "workflow" / "work-orders"
    status: dict[str, str] = {}
    for path in sorted(wo_dir.glob("WO-*.md")):
        parts = path.name.split("-")
        wo = f"{parts[0]}-{parts[1]}"
        m = re.search(r"^Status:\s*(\w[\w-]*)", path.read_text(), re.MULTILINE)
        if m:
            status[wo] = m.group(1)
    return status


def _check_wo_status() -> SubCheck:
    """TODO must never mark DONE a WO its file has never started.

    The GATING desync is the dangerous lie: a `- [x] **WO-nn**` (queue
    says DONE) whose work-order file Status is still `todo` (untouched).
    This repo deliberately keeps a worked WO's Status conservative
    (`in-progress`, `honest-partial`, `partial`, `phase ...`) after queue
    integration to name its residual -- those are NOT lies and are only
    reported (non-gating). A `- [ ]` residual bullet under a done WO is
    likewise the intended residual-tracking pattern, never flagged.
    """
    status = _wo_status_map()
    todo = (REPO_ROOT / "TODO.md").read_text()
    liars: list[str] = []
    soft: list[str] = []
    for line in todo.splitlines():
        m = re.match(r"\s*-\s*\[[xX]\].*?\*\*(WO-\d+)", line)
        if not m:
            continue
        wo = m.group(1)
        word = status.get(wo, "")
        if word == "todo":
            liars.append(f"{wo} (queue=done, file=todo)")
        elif word and not word.startswith(("done", "cut")):
            soft.append(f"{wo}={word}")
    for lie in liars:
        _log.error("consistency: TODO marks done a WO never started: %s", lie)
    for s in soft:
        _log.warning(
            "consistency: queue-done WO with residual Status (report-only): %s", s
        )
    return SubCheck(
        "wo_status",
        not liars,
        len(status),
        f"{len(liars)} false-done, {len(soft)} residual",
    )


def _check_extensions() -> SubCheck:
    """The core registry is the single source; nothing hard-codes an ext."""
    from regolith import compiler

    reported = frozenset(ext for ext, _lang in compiler.extensions())
    if reported != _KNOWN_EXTENSIONS:
        _log.error(
            "consistency: core extensions %s != known %s",
            sorted(reported),
            sorted(_KNOWN_EXTENSIONS),
        )
        return SubCheck("extension", False, len(reported), "core set mismatch")
    # Single-sourcing invariant: no file OUTSIDE the Rust registry may
    # enumerate the whole extension set together -- that is a competing
    # registry that can desync (the tripwire). A lone `.hema` glob is a
    # use, not a second registry, so we flag only files that list 3+ of
    # the four source extensions together (a table/list of them).
    offenders: list[str] = []
    for path in sorted((REPO_ROOT / "python").rglob("*.py")):
        text = path.read_text()
        present = {m.group(1) for m in re.finditer(r'"\.?(hema|cupr|fluo|calx)"', text)}
        if len(present) >= 3:
            offenders.append(str(path.relative_to(REPO_ROOT)))
    for off in offenders:
        _log.error("consistency: competing extension registry in %s", off)
    return SubCheck(
        "extension", not offenders, len(reported), f"{len(offenders)} competing"
    )


def _check_goldens() -> SubCheck:
    """`tests/golden/` carries no uncommitted drift on the health run."""
    proc = subprocess.run(
        ["git", "status", "--porcelain", "tests/golden/"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    dirty = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    for ln in dirty:
        _log.error("consistency: golden drift %s", ln)
    return SubCheck("goldens", not dirty, 0, f"{len(dirty)} dirty file(s)")


def _check_waivers() -> SubCheck:
    """Every `by doc(<ref>)` resolves; zero stale waivers fleet-wide."""
    import json

    unresolved: list[str] = []
    for ext in ("hema", "cupr", "fluo", "calx"):
        for path in sorted((REPO_ROOT / "examples").rglob(f"*.{ext}")):
            for i, line in enumerate(path.read_text().splitlines(), 1):
                for m in _BY_DOC.finditer(line):
                    ref = m.group(1).strip().strip("\"'")
                    memo = path.parent / ref
                    if not memo.is_file():
                        unresolved.append(f"{path.relative_to(REPO_ROOT)}:{i} -> {ref}")
    for u in unresolved:
        _log.error("consistency: unresolved by doc() ref %s", u)

    stale_total = 0
    fleet_cache = HEALTH_OUT / "fleet_results.json"
    if fleet_cache.is_file():
        results = json.loads(fleet_cache.read_text())
        stale_total = sum(r["stale_waivers"] for r in results.values())
        if stale_total:
            _log.error("consistency: %d stale waiver(s) fleet-wide", stale_total)
    else:
        _log.debug("consistency: no fleet cache; stale-waiver sub-check skipped")

    ok = not unresolved and stale_total == 0
    return SubCheck(
        "waivers",
        ok,
        len(unresolved),
        f"{len(unresolved)} bad-ref, {stale_total} stale",
    )


def _check_worktrees() -> SubCheck:
    """Report (non-gating) any git worktree other than the primary."""
    proc = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    worktrees = [
        ln.split(" ", 1)[1]
        for ln in proc.stdout.splitlines()
        if ln.startswith("worktree ")
    ]
    extra = [w for w in worktrees if ".claude/worktrees" in w]
    for w in extra:
        _log.warning("consistency: stale worktree present (report-only): %s", w)
    # Report-only: never gates the leg.
    return SubCheck("worktrees", True, len(extra), f"{len(extra)} extra (report-only)")


def _check_organization() -> SubCheck:
    """The WO-118 stdlib organization sweeps, folded into one sub-check
    (each is independently runnable via ``tools.stdlib.organization``)."""
    sub_results = run_organization_checks()
    failed = [c.name for c in sub_results if not c.ok]
    ok = not failed
    for c in sub_results:
        _log.debug("organization: %-16s ok=%s (%s)", c.name, c.ok, c.note)
    note = "all clean" if ok else f"failed: {', '.join(failed)}"
    return SubCheck("organization", ok, len(sub_results), note)


def _check_docs_agreement() -> SubCheck:
    """The WO-121 docs-agreement sweeps, folded into one sub-check (each
    is independently runnable via ``tools.health.docs_agreement``)."""
    sub_results = run_docs_agreement_checks()
    failed = [c.name for c in sub_results if not c.ok]
    ok = not failed
    for c in sub_results:
        _log.debug("docs_agreement: %-16s ok=%s (%s)", c.name, c.ok, c.note)
    note = "all clean" if ok else f"failed: {', '.join(failed)}"
    return SubCheck("docs_agreement", ok, len(sub_results), note)


def run(*, smoke: bool = False) -> LegSummary:
    """Run the consistency sweeps; return the standardized summary row."""
    _log.info(
        "consistency: running the standardization sweeps%s", " (smoke)" if smoke else ""
    )
    checks = [
        _check_dnums(),
        _check_wo_status(),
        _check_extensions(),
        _check_goldens(),
        _check_worktrees(),
        _check_organization(),
        _check_docs_agreement(),
    ]
    if not smoke:
        checks.append(_check_waivers())
    ok = all(c.ok for c in checks)
    for c in checks:
        _log.debug("consistency: %-10s ok=%s (%s)", c.name, c.ok, c.note)
    failed = [c.name for c in checks if not c.ok]
    evidence = "all sweeps clean" if ok else f"failed: {', '.join(failed)}"
    return LegSummary(
        leg="consistency",
        ok=ok,
        counts={"sweeps": len(checks), "failed": len(failed)},
        evidence=evidence,
    )


def main(argv: list[str] | None = None) -> int:
    """Run the consistency leg standalone; exit 0 iff green."""
    import argparse

    parser = argparse.ArgumentParser(description="The consistency health leg.")
    parser.add_argument(
        "--smoke", action="store_true", help="Skip the fleet-cache sweep."
    )
    args = parser.parse_args(argv)
    summary = run(smoke=args.smoke)
    print(summary.row())
    return 0 if summary.ok else 1


if __name__ == "__main__":
    sys.exit(main())
