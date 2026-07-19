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
EXEMPTED here, by the exact (relpath, raised-kind-string) pair, with
the reason recorded -- never a blanket exemption, per D247.4's
"explicit and small" instruction. Every exemption is a DEFERRAL (a
real user-facing failure that deserves a code, tracked as escalation
F-WO131-2), not a false claim that the failure is not user-facing.

F154 (cycle 36): the exemption list was originally keyed by
(relpath, lineno). A line number is not a stable identity -- any edit
above a call site shifts it, and the sweep started failing for
reasons unrelated to what it guards. Rekeyed on (relpath, kind): the
literal string a deferred call site raises is exactly the thing being
deferred, and it survives refactors that only move code around.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from regolith.logging_setup import get_logger

_log = get_logger(__name__)

# frob:doc docs/modules/tools.md#health-diag-codes
REPO_ROOT = Path(__file__).resolve().parents[2]
# frob:doc docs/modules/tools.md#health-diag-codes
SWEEP_ROOT = REPO_ROOT / "python" / "regolith" / "backends"

# The one Python-side error model this sweep polices (WO-131 scope:
# BackendError is the manufacturing-backend/ship/gate/harness failure
# type, AD-7). Other error models (MagnetiteError, LockfileError,
# OrchestratorError, DocError, CoreFailure) are a separate surface,
# out of this WO's literal "backends/gate/harness" scope -- see close-
# out escalation F-WO131-3.
# frob:doc docs/modules/tools.md#health-diag-codes
ERROR_CLASS_NAMES = frozenset({"BackendError"})


# frob:doc docs/modules/tools.md#health-diag-codes
@dataclass(frozen=True)
class BareKindViolation:
    """One `BackendError(kind="...")` bare-string call site."""

    relpath: str
    lineno: int
    kind: str


# EXEMPT[(relpath, kind)] = reason. Keyed on the exact bare-string
# `kind=` literal a deferred call site raises, not its line number --
# a refactor that moves the call site (without changing what it
# raises) no longer breaks the sweep. Where the SAME kind string is
# raised from more than one call site in a file (debug_taps.py), one
# entry covers every such site: the deferral is of the KIND, not of a
# particular line.
# frob:doc docs/modules/tools.md#health-diag-codes
# frob:ticket T-0040
EXEMPT: dict[tuple[str, str], str] = {
    # -- manifest.py: package signature/hash integrity verification.
    # Real user-facing failures; deferred (not backfilled by WO-131's
    # sweep scope, which prioritized the four D247.2-named kinds).
    (
        "python/regolith/backends/manifest.py",
        "unsigned",
    ): "deferred: F-WO131-2 (manifest integrity)",
    (
        "python/regolith/backends/manifest.py",
        "unknown_key",
    ): "deferred: F-WO131-2 (manifest integrity)",
    (
        "python/regolith/backends/manifest.py",
        "bad_signature",
    ): "deferred: F-WO131-2 (manifest integrity)",
    (
        "python/regolith/backends/manifest.py",
        "file_set_mismatch",
    ): "deferred: F-WO131-2 (manifest integrity)",
    (
        "python/regolith/backends/manifest.py",
        "hash_mismatch",
    ): "deferred: F-WO131-2 (manifest integrity)",
    # -- ship.py: the release gate itself.
    (
        "python/regolith/backends/ship.py",
        "build_failed",
    ): "deferred: F-WO131-2 (ship gate)",
    (
        "python/regolith/backends/ship.py",
        "release_not_ready",
    ): "deferred: F-WO131-2 (ship gate)",
    (
        "python/regolith/backends/ship.py",
        "manifest_not_found",
    ): "deferred: F-WO131-2 (ship gate)",
    (
        "python/regolith/backends/ship.py",
        "file_missing",
    ): "deferred: F-WO131-2 (ship gate)",
    # -- realized-IR availability guards (mech/elec/registry/three_d).
    (
        "python/regolith/backends/mech.py",
        "geometry_ir_unavailable",
    ): "deferred: F-WO131-2 (IR availability)",
    (
        "python/regolith/backends/registry.py",
        "geometry_ir_unavailable",
    ): "deferred: F-WO131-2 (IR availability)",
    (
        "python/regolith/backends/registry.py",
        "flownet_ir_unavailable",
    ): "deferred: F-WO131-2 (IR availability)",
    (
        "python/regolith/backends/registry.py",
        "frame_ir_unavailable",
    ): "deferred: F-WO131-2 (IR availability)",
    (
        "python/regolith/backends/registry.py",
        "harness_ir_unavailable",
    ): "deferred: F-WO131-2 (IR availability)",
    (
        "python/regolith/backends/registry.py",
        "contract_graph_ir_unavailable",
    ): "deferred: F-WO131-2 (IR availability)",
    (
        "python/regolith/backends/registry.py",
        "si_rows_unavailable",
    ): "deferred: F-WO131-2 (IR availability)",
    (
        "python/regolith/backends/registry.py",
        "opt_trace_ir_unavailable",
    ): "deferred: F-WO131-2 (IR availability)",
    (
        "python/regolith/backends/registry.py",
        "unknown_drawing_track",
    ): "deferred: F-WO131-2 (unknown drawing track)",
    (
        "python/regolith/backends/three_d/backend.py",
        "tessellation_unavailable",
    ): "deferred: F-WO131-2 (IR availability)",
    (
        "python/regolith/backends/three_d/backend.py",
        "assembly_3d_unavailable",
    ): "deferred: F-WO131-2 (IR availability)",
    (
        "python/regolith/backends/elec.py",
        "layout_ir_unavailable",
    ): "deferred: F-WO131-2 (IR availability)",
    (
        "python/regolith/backends/elec.py",
        "tool_unavailable",
    ): "deferred: F-WO131-2 (tool availability)",
    (
        "python/regolith/backends/elec.py",
        "export_failed",
    ): "deferred: F-WO131-2 (export failure)",
    # -- native artifact store.
    (
        "python/regolith/backends/artifacts.py",
        "native_artifact_hash_mismatch",
    ): "deferred: F-WO131-2 (native artifact store)",
    (
        "python/regolith/backends/artifacts.py",
        "native_artifact_not_found",
    ): "deferred: F-WO131-2 (native artifact store)",
    (
        "python/regolith/backends/artifacts.py",
        "native_artifact_unreadable",
    ): "deferred: F-WO131-2 (native artifact store)",
    # -- debug tap infrastructure (harness surface; the D247.2-named
    # `tap_map_artifact_mismatch` WAS backfilled to E1103 -- these
    # siblings were not, in this pass). Several of these kinds are
    # each raised from more than one call site in debug_taps.py; one
    # entry per kind covers all of them.
    (
        "python/regolith/backends/debug_taps.py",
        "invalid_tap_capacity",
    ): "deferred: F-WO131-2 (tap infra)",
    (
        "python/regolith/backends/debug_taps.py",
        "unknown_explicit_tap",
    ): "deferred: F-WO131-2 (tap infra)",
    (
        "python/regolith/backends/debug_taps.py",
        "debug_spec_malformed",
    ): "deferred: F-WO131-2 (tap infra)",
    (
        "python/regolith/backends/debug_taps.py",
        "tap_map_malformed",
    ): "deferred: F-WO131-2 (tap infra)",
    (
        "python/regolith/backends/debug_taps.py",
        "ambiguous_explicit_tap",
    ): "deferred: F-WO131-2 (tap infra)",
    (
        "python/regolith/backends/debug_taps.py",
        "tap_header_record_malformed",
    ): "deferred: F-WO131-2 (tap infra)",
    (
        "python/regolith/backends/debug_taps.py",
        "tap_header_record_duplicate",
    ): "deferred: F-WO131-2 (tap infra)",
    # -- harness_pack.py: one sibling malformed-input kind, not the
    # D247.2-named `expectation_provenance_unresolved` (which WAS
    # backfilled to E1101).
    (
        "python/regolith/backends/harness_pack.py",
        "expected_signals_malformed",
    ): "deferred: F-WO131-2 (expected-signals shape)",
    # -- artifact_index.py (WO-130, landed concurrently with WO-131's
    # sweep so this call site was never enumerated in the original 37):
    # `artifact_index_drift` was closed by wiring up the ARTIFACT_INDEX_DRIFT
    # constant WO-131 had already reserved for it (F-WO131-1). This
    # sibling kind has no reserved code yet; deferred under the same
    # F-WO131-2 worklist, found by the corrected sweep rather than
    # silently exempted.
    (
        "python/regolith/backends/artifact_index.py",
        "artifact_family_unregistered",
    ): "deferred: F-WO131-2 (artifact family registration)",
    # -- WO-161 (AD-46): the registration-derived classification sibling
    # of the family-unregistered kind above -- a family IS registered
    # but carries no `path_patterns` entry matching a given relpath.
    # Same F-WO131-2 worklist, same reserved-code-not-yet-assigned
    # deferral shape.
    (
        "python/regolith/backends/artifact_index.py",
        "artifact_path_unclassified",
    ): "deferred: F-WO131-2 (artifact path classification, WO-161)",
    # perfboard v1 (WO-165): realized-IR unavailability refusal; code
    # assignment deferred to the same make-codes next-free batch shape
    # WO-153's siblings used.
    (
        "python/regolith/backends/perfboard.py",
        "board_assignment_ir_unavailable",
    ): "deferred: WO-165 close-out (perfboard realized-IR refusal)",
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
                kind = kw.value.value
                if (relpath, kind) in EXEMPT:
                    continue
                violations.append(
                    BareKindViolation(
                        relpath=relpath, lineno=lineno, kind=kw.value.value
                    )
                )
    return violations


# frob:doc docs/modules/tools.md#health-diag-codes
# frob:waive TEST001 reason="completeness sweep, see test_diag_codes_run_clean"
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


# frob:doc docs/modules/tools.md#health-diag-codes
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
