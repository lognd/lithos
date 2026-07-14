"""The `diag_codes` health sub-check (D247.4b, WO-131): no user-facing
failure is raised with a bare string `kind`.

Scope (the WO's own words): "the backends/gate/harness surfaces" --
concretely `python/regolith/backends/` (which contains `ship.py`, the
release GATE, and `harness_pack.py`/`debug_taps.py`, the bring-up
HARNESS). AST-based, not regex: a `BackendError(kind=...)` call site is
a VIOLATION iff `kind` is a string literal (`ast.Constant`); a `kind=`
that names an imported constant (`ast.Name`, e.g. `kind=FAB_SET_INCOMPLETE`
from the generated `regolith._codes`) is exactly what D247.1 requires
and passes clean. This is what makes the rule able to FAIL (D247.4):
a fresh `BackendError(kind="new_bare_string")` trips it immediately,
proven by the negative test in `tests/health/test_diag_codes.py`.

A small number of PRE-EXISTING bare-string kinds this WO's sweep found
are not backfilled by this WO (the codes new families+the four named
bare strings were; see WO-131 close-out). Each is individually
EXEMPTED here, by exact (relpath, lineno) location, with the reason
recorded -- never a blanket exemption, per D247.4's "explicit and
small" instruction. Every exemption is a DEFERRAL (a real user-facing
failure that deserves a code, tracked as escalation F-WO131-2), not a
false claim that the failure is not user-facing.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from regolith.logging_setup import get_logger

_log = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
SWEEP_ROOT = REPO_ROOT / "python" / "regolith" / "backends"

# The one Python-side error model this sweep polices (WO-131 scope:
# BackendError is the manufacturing-backend/ship/gate/harness failure
# type, AD-7). Other error models (MagnetiteError, LockfileError,
# OrchestratorError, DocError, CoreFailure) are a separate surface,
# out of this WO's literal "backends/gate/harness" scope -- see close-
# out escalation F-WO131-3.
ERROR_CLASS_NAMES = frozenset({"BackendError"})


@dataclass(frozen=True)
class BareKindViolation:
    """One `BackendError(kind="...")` bare-string call site."""

    relpath: str
    lineno: int
    kind: str


# EXEMPT[(relpath, lineno)] = reason. Regenerate this list by running
# the sweep with exemptions cleared if line numbers drift after an
# edit -- a stale (relpath, lineno) simply stops exempting (the sweep
# fails loudly rather than silently exempting the wrong line).
EXEMPT: dict[tuple[str, int], str] = {
    # -- manifest.py: package signature/hash integrity verification.
    # Real user-facing failures; deferred (not backfilled by WO-131's
    # sweep scope, which prioritized the four D247.2-named kinds).
    (
        "python/regolith/backends/manifest.py",
        188,
    ): "deferred: F-WO131-2 (manifest integrity)",
    (
        "python/regolith/backends/manifest.py",
        193,
    ): "deferred: F-WO131-2 (manifest integrity)",
    (
        "python/regolith/backends/manifest.py",
        207,
    ): "deferred: F-WO131-2 (manifest integrity)",
    (
        "python/regolith/backends/manifest.py",
        232,
    ): "deferred: F-WO131-2 (manifest integrity)",
    (
        "python/regolith/backends/manifest.py",
        242,
    ): "deferred: F-WO131-2 (manifest integrity)",
    # -- ship.py: the release gate itself.
    ("python/regolith/backends/ship.py", 888): "deferred: F-WO131-2 (ship gate)",
    ("python/regolith/backends/ship.py", 902): "deferred: F-WO131-2 (ship gate)",
    ("python/regolith/backends/ship.py", 1126): "deferred: F-WO131-2 (ship gate)",
    ("python/regolith/backends/ship.py", 1141): "deferred: F-WO131-2 (ship gate)",
    # -- realized-IR availability guards (mech/elec/registry/three_d).
    ("python/regolith/backends/mech.py", 98): "deferred: F-WO131-2 (IR availability)",
    (
        "python/regolith/backends/registry.py",
        263,
    ): "deferred: F-WO131-2 (IR availability)",
    (
        "python/regolith/backends/registry.py",
        278,
    ): "deferred: F-WO131-2 (IR availability)",
    (
        "python/regolith/backends/registry.py",
        293,
    ): "deferred: F-WO131-2 (IR availability)",
    (
        "python/regolith/backends/registry.py",
        310,
    ): "deferred: F-WO131-2 (IR availability)",
    (
        "python/regolith/backends/registry.py",
        329,
    ): "deferred: F-WO131-2 (IR availability)",
    (
        "python/regolith/backends/registry.py",
        344,
    ): "deferred: F-WO131-2 (IR availability)",
    (
        "python/regolith/backends/registry.py",
        363,
    ): "deferred: F-WO131-2 (IR availability)",
    (
        "python/regolith/backends/registry.py",
        451,
    ): "deferred: F-WO131-2 (unknown drawing track)",
    (
        "python/regolith/backends/three_d/backend.py",
        66,
    ): "deferred: F-WO131-2 (IR availability)",
    (
        "python/regolith/backends/three_d/backend.py",
        123,
    ): "deferred: F-WO131-2 (IR availability)",
    ("python/regolith/backends/elec.py", 100): "deferred: F-WO131-2 (IR availability)",
    (
        "python/regolith/backends/elec.py",
        271,
    ): "deferred: F-WO131-2 (tool availability)",
    ("python/regolith/backends/elec.py", 281): "deferred: F-WO131-2 (export failure)",
    # -- native artifact store.
    (
        "python/regolith/backends/artifacts.py",
        101,
    ): "deferred: F-WO131-2 (native artifact store)",
    (
        "python/regolith/backends/artifacts.py",
        122,
    ): "deferred: F-WO131-2 (native artifact store)",
    (
        "python/regolith/backends/artifacts.py",
        132,
    ): "deferred: F-WO131-2 (native artifact store)",
    # -- debug tap infrastructure (harness surface; the D247.2-named
    # `tap_map_artifact_mismatch` WAS backfilled to E1103 -- these
    # siblings were not, in this pass).
    ("python/regolith/backends/debug_taps.py", 163): "deferred: F-WO131-2 (tap infra)",
    ("python/regolith/backends/debug_taps.py", 180): "deferred: F-WO131-2 (tap infra)",
    ("python/regolith/backends/debug_taps.py", 326): "deferred: F-WO131-2 (tap infra)",
    ("python/regolith/backends/debug_taps.py", 358): "deferred: F-WO131-2 (tap infra)",
    ("python/regolith/backends/debug_taps.py", 366): "deferred: F-WO131-2 (tap infra)",
    ("python/regolith/backends/debug_taps.py", 507): "deferred: F-WO131-2 (tap infra)",
    ("python/regolith/backends/debug_taps.py", 525): "deferred: F-WO131-2 (tap infra)",
    ("python/regolith/backends/debug_taps.py", 574): "deferred: F-WO131-2 (tap infra)",
    ("python/regolith/backends/debug_taps.py", 582): "deferred: F-WO131-2 (tap infra)",
    ("python/regolith/backends/debug_taps.py", 621): "deferred: F-WO131-2 (tap infra)",
    # -- harness_pack.py: one sibling malformed-input kind, not the
    # D247.2-named `expectation_provenance_unresolved` (which WAS
    # backfilled to E1101).
    (
        "python/regolith/backends/harness_pack.py",
        405,
    ): "deferred: F-WO131-2 (expected-signals shape)",
}


def _find_violations(
    root: Path, *, repo_root: Path | None = None
) -> list[BareKindViolation]:
    """Walk every `.py` under `root`, AST-scan for bare-string
    `BackendError(kind="...")` call sites not covered by `EXEMPT`.

    `repo_root` lets tests point `relpath` at a synthetic fixture tree
    (defaults to the real `REPO_ROOT` for production use)."""
    base = repo_root if repo_root is not None else REPO_ROOT
    violations: list[BareKindViolation] = []
    for path in sorted(root.rglob("*.py")):
        relpath = str(path.relative_to(base))
        tree = ast.parse(path.read_text(), filename=relpath)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = (
                func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
            )
            if name not in ERROR_CLASS_NAMES:
                continue
            for kw in node.keywords:
                if kw.arg != "kind":
                    continue
                if not (
                    isinstance(kw.value, ast.Constant)
                    and isinstance(kw.value.value, str)
                ):
                    continue
                lineno = kw.value.lineno
                if (relpath, lineno) in EXEMPT:
                    continue
                violations.append(
                    BareKindViolation(
                        relpath=relpath, lineno=lineno, kind=kw.value.value
                    )
                )
    return violations


def check_explain_completeness() -> tuple[bool, int, int]:
    """D247.4a: every registered code has an explain entry, and the STUB
    count is reported (never hidden -- the debt stays visible).

    Returns `(ok, entryless_count, stub_count)`. Reads the GENERATED
    `regolith._codes` (single-sourced from the Rust registry): an
    entry-less code cannot even reach this module, since the Rust
    `explain::completeness_is_total` test fails the build first -- so
    `entryless` is a belt-and-braces re-assertion on the Python side of
    the fence, and the stub count is the number the WO asks us to
    surface.
    """
    from regolith._codes import ALL as ALL_CODES

    entryless = [e.code for e in ALL_CODES if not e.meaning.strip()]
    stubs = [e.code for e in ALL_CODES if not e.authored]
    for code in entryless:
        _log.error("diag_codes: registered code %s has no explain entry", code)
    _log.info(
        "diag_codes: %d code(s) registered, %d authored, %d honest stub(s)",
        len(ALL_CODES),
        len(ALL_CODES) - len(stubs),
        len(stubs),
    )
    return not entryless, len(entryless), len(stubs)


def run() -> tuple[bool, int, str]:
    """`(ok, violation_count, note)` -- the standardized sub-check shape.

    Two legs, both of which must be able to FAIL (D247.4): (a) every
    registered code has an explain entry, stub count REPORTED; (b) no
    user-facing failure carries a bare string kind.
    """
    complete, entryless, stubs = check_explain_completeness()
    violations = _find_violations(SWEEP_ROOT)
    exempt_count = len(EXEMPT)
    ok = complete and not violations
    if violations:
        detail = "; ".join(
            f"{v.relpath}:{v.lineno} kind={v.kind!r}" for v in violations[:5]
        )
        note = f"{len(violations)} bare-string kind(s), e.g. {detail}"
    elif entryless:
        note = f"{entryless} registered code(s) with NO explain entry"
    else:
        note = (
            f"0 bare-string kind(s), {exempt_count} explicitly exempted "
            f"(deferred); explain entries complete, {stubs} honest stub(s)"
        )
    return ok, len(violations) + entryless, note
