"""WO-83 slice B: `regolith test`, the runner (charter toolchain/37).

Discovery walks the given roots for the `.test.<ext>` convention
(the ONE extension registry, `compiler.extensions()`); each test
file's `test <name>:` declarations are the slice-A lowering surface
(`BuildPayload.tests`, a `TestDeclPayload` per declaration). Each
declared test is one SCENARIO run through the ORDINARY build door
(:mod:`regolith.orchestrator.test_scenario`, AD-22 -- no private
pipeline) and its `expect:` block evaluated against the real output
(:mod:`regolith.orchestrator.test_expect`).

Content-address caching (charter sec. 1.4): a scenario's digest
(scenario_entries, canonical JSON) crossed with the design file's
digest (raw bytes) keys a small JSON store under
`<project>/.regolith/test-cache.json` -- an unchanged scenario over an
unchanged design is a cache hit, mirroring
:mod:`regolith.orchestrator.cache`'s existing convention (same
blake3-domain-tag discipline, a SIBLING cache file, never a rewrite of
that module).
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import blake3

from regolith import compiler
from regolith._schema.models import Obligation, TestDeclPayload
from regolith.logging_setup import get_logger
from regolith.orchestrator import test_expect
from regolith.orchestrator.optimize import domains_from_choice_points, optimize_discrete
from regolith.orchestrator.orchestrate import build as orchestrated_build
from regolith.orchestrator.test_scenario import (
    ScenarioPlan,
    build_overlay_project,
    classify_scenario,
    design_path_for,
)
from regolith.orchestrator.tiers import BuildTier

_log = get_logger(__name__)

_CACHE_DOMAIN = "regolith.orchestrator.test_cache"
_CACHE_FILENAME = "test-cache.json"


def _digest(data: bytes) -> str:
    digest = blake3.blake3(_CACHE_DOMAIN.encode() + b"\x00" + data).hexdigest()
    return f"blake3:{digest}"


def discover_test_files(roots: tuple[str, ...]) -> tuple[Path, ...]:
    """Every `.test.<ext>` file under `roots` (the ONE extension
    registry decides `<ext>`, never a second hard-coded list)."""
    exts = {ext for ext, _lang in compiler.extensions()}
    found: list[Path] = []
    for root in roots:
        p = Path(root)
        if p.is_file():
            if p.suffix.lstrip(".") in exts and ".test." in p.name:
                found.append(p)
            continue
        for ext in exts:
            found.extend(sorted(p.rglob(f"*.test.{ext}")))
    return tuple(sorted(set(found)))


@dataclass(frozen=True)
class CaseResult:
    """One test declaration's outcome: pass iff every expectation held."""

    test_file: Path
    name: str
    ok: bool
    from_cache: bool
    details: tuple[str, ...] = field(default_factory=tuple)
    error: str | None = None


def _load_cache(project_root: Path) -> dict[str, dict[str, object]]:
    cache_path = project_root / ".regolith" / _CACHE_FILENAME
    if not cache_path.is_file():
        return {}
    try:
        raw = json.loads(cache_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        _log.warning("test cache unreadable at %s: %s; rebuilding", cache_path, exc)
        return {}
    # Full-shape entries only ({"ok", "details", "error"}): a hit must
    # replay the WHOLE CaseResult, not a degraded ok-bool (the pre-fix
    # bool shape dropped details/error on every hit). Legacy bool
    # entries are treated as misses and upgraded on the next save.
    entries = {k: v for k, v in raw.items() if isinstance(v, dict) and "ok" in v}
    if len(entries) != len(raw):
        _log.debug(
            "test cache at %s: dropped %d legacy entr(ies)",
            cache_path,
            len(raw) - len(entries),
        )
    return entries


def _save_cache(project_root: Path, entries: dict[str, dict[str, object]]) -> None:
    cache_dir = project_root / ".regolith"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / _CACHE_FILENAME).write_text(json.dumps(entries, sort_keys=True))


def _cache_key(scenario_entries: list[str], design_bytes: bytes) -> str:
    scenario_json = json.dumps(scenario_entries, sort_keys=True).encode()
    return _digest(scenario_json + b"\x00design\x00" + design_bytes)


def _run_winner(
    payload: dict[str, object], plan: ScenarioPlan
) -> dict[str, str] | None:
    """Run the real discrete optimizer over `BuildPayload.choice_points`
    (D161/D168), seeded per the scenario -- the winner-expectation
    evaluation path (charter sec. 1.2)."""
    raw_choice_points = payload.get("choice_points", {})
    if not isinstance(raw_choice_points, dict) or not raw_choice_points:
        return None
    choice_points: dict[str, dict[str, object]] = {
        str(k): {str(fk): fv for fk, fv in v.items()}
        for k, v in raw_choice_points.items()
        if isinstance(v, dict)
    }
    domains, evaluator, screen, objective = domains_from_choice_points(
        choice_points, {}
    )
    if not domains:
        return None
    trace = optimize_discrete(
        domains,
        evaluator,
        objective,
        seed=plan.optimizer.seed,
        budget_evals=plan.optimizer.budget_evals,
        screen=screen,
    )
    if trace.winner is None:
        return None
    winner = trace.candidates[trace.winner]
    return dict(item.root for item in winner.assignment)


def _evaluate_decl(
    decl: TestDeclPayload, overlay_design: Path
) -> tuple[bool, tuple[str, ...]]:
    """Run the ordinary build over `overlay_design`'s project and check
    every expectation against the real output. Never raises for a
    build-level failure -- an unbuildable overlay is an honest fail
    with the core's own rendered message as the detail."""
    plan = classify_scenario(decl.scenario_entries)
    report = orchestrated_build((str(overlay_design.parent),), BuildTier.BUILD)
    if report.is_err:
        return False, (f"scenario build failed: {report.danger_err.message}",)
    built = report.danger_ok
    payload = json.loads(built.payload_json) if built.payload_json else {}
    obligations_raw = payload.get("obligations", [])
    obligations = (
        [Obligation.model_validate(o) for o in obligations_raw]
        if isinstance(obligations_raw, list)
        else []
    )
    named_results = list(
        zip((ob.claim.name or "" for ob in obligations), built.results, strict=False)
    )
    resolutions_raw = payload.get("resolutions", [])
    resolutions: list[dict[str, object]] = (
        [r for r in resolutions_raw if isinstance(r, dict)]
        if isinstance(resolutions_raw, list)
        else []
    )

    winner_assignment: dict[str, str] | None = None
    needs_winner = any(e.form == "winner" for e in decl.expectations)
    if needs_winner:
        winner_assignment = _run_winner(payload, plan)

    details: list[str] = []
    ok = True
    for exp in decl.expectations:
        if exp.form is None or exp.tail is None:
            details.append(f"FAIL: unrecognized expectation form (raw): {exp!r}")
            ok = False
            continue
        outcome: test_expect.ExpectOutcome
        if exp.form == "diagnostic":
            outcome = test_expect.eval_diagnostic(exp.tail, built.rendered)
        elif exp.form == "verdict":
            outcome = test_expect.eval_verdict(exp.tail, named_results)
        elif exp.form == "value":
            outcome = test_expect.eval_value(exp.tail, resolutions)
        elif exp.form == "count":
            outcome = test_expect.eval_count(exp.tail, payload)
        elif exp.form == "winner":
            outcome = test_expect.eval_winner(exp.tail, winner_assignment)
        else:
            outcome = test_expect.ExpectOutcome(False, f"unknown form {exp.form!r}")
        details.append(f"{'ok' if outcome.ok else 'FAIL'}: {outcome.detail}")
        ok = ok and outcome.ok
    return ok, tuple(details)


def run_one_test_file(
    test_file: Path, name_filter: str | None
) -> tuple[CaseResult, ...]:
    """Discover + run every `test <name>:` declaration in `test_file`,
    applying `-k name_filter` as a substring match on `name` (cargo
    convention)."""
    check_result = compiler.check((str(test_file),))
    if check_result.is_err:
        return (
            CaseResult(
                test_file=test_file,
                name="(discovery)",
                ok=False,
                from_cache=False,
                error=check_result.danger_err.message,
            ),
        )
    payload = json.loads(check_result.danger_ok.payload_json)
    decls_raw = payload.get("tests", [])
    decls = [TestDeclPayload.model_validate(d) for d in decls_raw]
    if name_filter is not None:
        decls = [d for d in decls if name_filter in d.name]

    design = design_path_for(test_file)
    design_bytes = design.read_bytes() if design.is_file() else b""
    project_root = test_file.parent
    cache = _load_cache(project_root)
    cache_dirty = False

    def _run_uncached(decl: TestDeclPayload) -> CaseResult:
        """One scenario, in its own isolated overlay temp dir -- the
        parallel-safe unit (no shared mutable state; the cache is
        read before and written after the parallel section)."""
        plan = classify_scenario(decl.scenario_entries)
        with tempfile.TemporaryDirectory(prefix="regolith-test-") as tmp:
            overlay_design = build_overlay_project(test_file, plan, Path(tmp))
            ok, details = _evaluate_decl(decl, overlay_design)
        return CaseResult(
            test_file=test_file,
            name=decl.name,
            ok=ok,
            from_cache=False,
            details=details,
        )

    keyed = [(decl, _cache_key(decl.scenario_entries, design_bytes)) for decl in decls]
    uncached = [(decl, key) for decl, key in keyed if cache.get(key) is None]
    # Parallel scenarios (charter sec. 1.4): each uncached scenario is
    # an independent overlay build; `compiler.check`/`compile` release
    # the GIL across the core call, so a small thread pool overlaps the
    # Rust-side work. Declaration order is preserved in the returned
    # tuple regardless of completion order (INV-10 posture).
    ran: dict[str, CaseResult] = {}
    if len(uncached) > 1:
        with ThreadPoolExecutor(max_workers=min(4, len(uncached))) as pool:
            for (_decl, key), case in zip(
                uncached,
                pool.map(_run_uncached, (d for d, _ in uncached)),
                strict=True,
            ):
                ran[key] = case
    elif uncached:
        decl, key = uncached[0]
        ran[key] = _run_uncached(decl)

    results: list[CaseResult] = []
    for decl, key in keyed:
        case = ran.get(key)
        if case is None:
            entry = cache[key]
            raw_details = entry.get("details")
            raw_error = entry.get("error")
            results.append(
                CaseResult(
                    test_file=test_file,
                    name=decl.name,
                    ok=bool(entry["ok"]),
                    from_cache=True,
                    details=(
                        tuple(str(d) for d in raw_details)
                        if isinstance(raw_details, list)
                        else ()
                    ),
                    error=str(raw_error) if raw_error is not None else None,
                )
            )
            continue
        results.append(case)
        cache[key] = {
            "ok": case.ok,
            "details": list(case.details),
            "error": case.error,
        }
        cache_dirty = True

    if cache_dirty:
        _save_cache(project_root, cache)
    return tuple(results)


def run_tests(
    roots: tuple[str, ...], name_filter: str | None = None
) -> tuple[CaseResult, ...]:
    """Discover and run every test declaration under `roots` (cargo-test
    UX: `-k` filters by name; scenarios within one file run in
    parallel -- see :func:`run_one_test_file`; files run sequentially
    so per-project cache writes never race)."""
    files = discover_test_files(roots)
    all_results: list[CaseResult] = []
    for f in files:
        all_results.extend(run_one_test_file(f, name_filter))
    return tuple(all_results)


def discover_rule_pack_files(roots: tuple[str, ...]) -> tuple[str, ...]:
    """Every source file under `roots` that declares `expect: pass`/
    `expect: fail` fixtures (WO-28's authoring convention -- rule packs
    are ordinary source files, no separate extension) -- the
    unification deliverable's discovery half: `regolith test` finds
    them the same way a human author would grep for them."""
    exts = {ext for ext, _lang in compiler.extensions()}
    found: list[str] = []
    for root in roots:
        p = Path(root)
        candidates = [p] if p.is_file() else []
        if p.is_dir():
            for ext in exts:
                candidates.extend(sorted(p.rglob(f"*.{ext}")))
        for c in candidates:
            if ".test." in c.name:
                continue
            try:
                text = c.read_text()
            except OSError:
                continue
            if "pass:" in text and "expect:" in text:
                found.append(str(c))
    return tuple(found)


def render_summary(results: Iterable[CaseResult]) -> tuple[str, bool]:
    """Cargo-style one-line-per-test output plus a trailing summary
    line; returns `(text, all_ok)`."""
    lines: list[str] = []
    passed = 0
    failed = 0
    for r in results:
        marker = "ok" if r.ok else "FAIL"
        cache_note = " (cached)" if r.from_cache else ""
        lines.append(f"test {r.test_file}::{r.name} ... {marker}{cache_note}")
        if not r.ok:
            if r.error:
                lines.append(f"    error: {r.error}")
            for d in r.details:
                if d.startswith("FAIL"):
                    lines.append(f"    {d}")
        if r.ok:
            passed += 1
        else:
            failed += 1
    lines.append("")
    lines.append(
        f"test result: {'ok' if failed == 0 else 'FAILED'}. "
        f"{passed} passed; {failed} failed"
    )
    return "\n".join(lines), failed == 0
