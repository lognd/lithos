"""The `std.` organization sweeps (WO-118, D227/AD-37, charter 39): the
mechanically-checkable rules charter 39 sec. 5.4 requires live in the
health consistency leg. Each check is a standalone function AND
runnable alone (`python -m tools.stdlib.organization [--check NAME]`).

Checks:

* **prefix**       -- `std.` is reserved (charter 39 sec. 1.1): every
  package whose `magnetite.toml` `[package] name` starts with `std.`
  must live under `stdlib/<name>/`; nothing outside `stdlib/` may
  claim the prefix.
* **one_family**   -- one record family per file (charter 39 sec.
  2.2): every `stdlib/**/records/*.toml` declares exactly one
  distinct `[[table]]` array-of-tables key.
* **citations**    -- citation presence (charter 39 secs. 3.1/3.2):
  every record row carries an `evidence.reference` (or top-level
  `reference`) field, and every registered built-in model's
  `.citation` is non-None (WO-114's citations() accessor). WO-145/
  D257 ruling 2 strengthening: a row whose `evidence` has opted into
  the structured citation shape (a `document` field present) must
  also carry non-empty `revision`/`page`/`table` -- additive, existing
  prose-`reference`-only rows are unaffected.
* **generated_drift** -- extends the WO-66 generator drift test
  (`tools/stdlib/generate_all.py`) into a standalone health check.
* **models_manifest** -- `std.models`'s `[provides].models` names
  every module `register_all()` actually registers, nothing phantom
  (the WO110-F7 fix, charter 39 sec. 5.4).
* **double_home**  -- no claim kind resolvable from both a lithos
  built-in and a feldspar pack model without a recorded router
  preference (charter 39 sec. 4); best-effort against the sibling
  feldspar checkout (degrades honestly when absent, the feldspar-link
  posture).
* **charter_drift** -- charter 39 sec. 4 and feldspar spec 12 sec. 4
  (the shared boundary rule) compared byte-for-byte modulo heading,
  against the sibling feldspar checkout.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from regolith.logging_setup import get_logger

_log = get_logger(__name__)

# frob:doc docs/modules/tools.md#stdlib-organization-sweeps
REPO_ROOT = Path(__file__).resolve().parents[2]
# frob:doc docs/modules/tools.md#stdlib-organization-sweeps
STDLIB_DIR = REPO_ROOT / "stdlib"
# frob:doc docs/modules/tools.md#stdlib-organization-sweeps
FELDSPAR_DIR = Path(
    __import__("os").environ.get("FELDSPAR_DIR", str(REPO_ROOT.parent / "feldspar"))
)

_TOML_KEY_RE = re.compile(r"^\[package\]")
_NAME_RE = re.compile(r'^\s*name\s*=\s*"([^"]+)"')
_TABLE_RE = re.compile(r"^\[\[([a-zA-Z_][\w.]*)\]\]")

#: Directory names no repo-wide sweep may descend into: venvs (incl.
#: `apps/*/.venv`), build output, caches, and `.git` itself. Nested
#: agent worktrees (`.claude/worktrees/...`) are handled as a path
#: PAIR in `is_excluded` -- see below. THE one exclusion home for
#: every filesystem walk in the organization sweeps (WO118b: the
#: unfiltered `REPO_ROOT.rglob` false-positived on every std. package
#: inside a live agent worktree on the coordinator's main checkout).
_EXCLUDED_DIR_NAMES = frozenset(
    {".git", ".venv", "target", "node_modules", "__pycache__", ".regolith"}
)


# frob:doc docs/modules/tools.md#stdlib-organization-sweeps
def is_excluded(path: Path) -> bool:
    """True when `path` sits inside a directory no repo sweep may see.

    Excludes any path with a component in `_EXCLUDED_DIR_NAMES`, and
    any path under a nested agent worktree (a `.claude/worktrees`
    component pair -- another checkout's whole tree, never this
    checkout's content). Every repo-rooted walk in this module MUST
    filter through this predicate; fixed-shape globs rooted inside
    `stdlib/` (which a nested worktree path can never match) are safe
    by construction and documented as such at each site.
    """
    parts = path.parts
    if any(p in _EXCLUDED_DIR_NAMES for p in parts):
        return True
    return any(
        p == ".claude" and parts[i + 1] == "worktrees" for i, p in enumerate(parts[:-1])
    )


# frob:doc docs/modules/tools.md#stdlib-organization-sweeps
class SubCheck:
    """One named sub-check result: ok, a count, and a one-line note."""

    def __init__(self, name: str, ok: bool, count: int, note: str) -> None:
        self.name = name
        self.ok = ok
        self.count = count
        self.note = note

    def __repr__(self) -> str:  # pragma: no cover -- debug convenience
        return f"SubCheck({self.name!r}, ok={self.ok}, note={self.note!r})"


def _package_name(magnetite_toml: Path) -> str | None:
    """Extract `[package] name` from a magnetite.toml, or None."""
    in_package = False
    for line in magnetite_toml.read_text().splitlines():
        if _TOML_KEY_RE.match(line):
            in_package = True
            continue
        if line.startswith("[") and not _TOML_KEY_RE.match(line):
            in_package = False
        if in_package:
            m = _NAME_RE.match(line)
            if m:
                return m.group(1)
    return None


# frob:doc docs/modules/tools.md#stdlib-organization-sweeps
def check_prefix_reservation() -> SubCheck:
    """`std.` is reserved: every `std.*` package lives under `stdlib/`."""
    offenders: list[str] = []
    seen = 0
    for magnetite in sorted(REPO_ROOT.rglob("magnetite.toml")):
        if is_excluded(magnetite.relative_to(REPO_ROOT)):
            continue
        name = _package_name(magnetite)
        if name is None:
            continue
        if name.startswith("std."):
            seen += 1
            try:
                rel = magnetite.relative_to(STDLIB_DIR)
            except ValueError:
                offenders.append(f"{magnetite.relative_to(REPO_ROOT)} (name={name})")
                continue
            expected_dir = rel.parts[0]
            if expected_dir != name:
                offenders.append(
                    f"{magnetite.relative_to(REPO_ROOT)}: dir "
                    f"'{expected_dir}' != package name '{name}'"
                )
    for off in offenders:
        _log.error("organization: std.-prefix violation: %s", off)
    return SubCheck(
        "prefix", not offenders, seen, f"{len(offenders)} misplaced std. package(s)"
    )


#: Pre-existing one-family-per-file violations (WO-118 sweep finding,
#: reported not fixed per the WO's scope guard: WO-113 is actively
#: adding rows to these same files on another branch, and a split is a
#: content-restructuring decision, not a structure-only move).
#: Placeholder WO118-F1. Reopen: a real family split lands for one of
#: these files, in the SAME change as a corpus sweep (charter 39 sec.
#: 5.3's additive-only/migration rule) -- remove its entry here then.
_ONE_FAMILY_BASELINE = {
    "stdlib/std.civil/records/materials.toml",
    "stdlib/std.civil/records/occupancy.toml",
    "stdlib/std.elec/records/cells.toml",
    "stdlib/std.elec/records/motor_frames.toml",
    "stdlib/std.fluid/records/components.toml",
    "stdlib/std.fluid/records/pipe.toml",
}


# frob:doc docs/modules/tools.md#stdlib-organization-sweeps
# frob:waive PERF004 reason="one-shot sort of a small set, never re-sorted"
def check_one_family_per_file() -> SubCheck:
    """Each `records/*.toml` declares exactly one array-of-tables key.

    Baseline violations (`_ONE_FAMILY_BASELINE`) are reported (WARNING)
    but do not gate -- they predate this check and are WO113-scope
    content, not this WO's to restructure. Any NEW multi-family file
    gates the check (a fresh violation is not baseline debt)."""
    offenders: list[str] = []
    baseline_hits: list[str] = []
    files = 0
    # Fixed-shape glob rooted at stdlib/: a nested-worktree path can
    # never match `stdlib/*/records/*.toml`, so no is_excluded filter
    # is needed here (see is_excluded's doc).
    for records_toml in sorted(STDLIB_DIR.glob("*/records/*.toml")):
        files += 1
        keys = {
            m.group(1)
            for line in records_toml.read_text().splitlines()
            for m in [_TABLE_RE.match(line)]
            if m
        }
        if len(keys) > 1:
            rel = records_toml.relative_to(REPO_ROOT).as_posix()
            note = f"{rel}: {sorted(keys)}"
            if rel in _ONE_FAMILY_BASELINE:
                baseline_hits.append(note)
            else:
                offenders.append(note)
    for off in offenders:
        _log.error("organization: one-family-per-file violation: %s", off)
    for b in baseline_hits:
        _log.warning(
            "organization: one-family-per-file baseline debt (WO118-F1, "
            "report-only): %s",
            b,
        )
    return SubCheck(
        "one_family",
        not offenders,
        files,
        f"{len(offenders)} new, {len(baseline_hits)} baseline (WO118-F1)",
    )


#: Pre-existing uncited built-ins (WO-118 sweep finding, reported not
#: fixed: supplying a real citation per model is a content/research
#: decision, out of this WO's structure-and-tooling scope). Placeholder
#: WO118-F2. `Model.citation`'s own base-class docstring already
#: names this state ("the base default keeps every existing model
#: valid"; WO-110 began landing citations "in parallel", not fleet-
#: wide). Keyed on the model's bare `signature.name` (version-
#: independent -- a version bump is not a citation fix). Reopen: a
#: model gains a real citation (its `.citation` override lands) in the
#: same change as removing its entry here.
_UNCITED_MODEL_BASELINE = {
    "buck_output_ripple_ccm",
    "beam_cantilever_deflection_eb",
    "beam_utilization_interaction",
    "beam_simple_span_deflection_udl",
    "post_embedment_declared_vs_required",
    "footing_bearing_pressure",
    "link_budget_margin_db",
    "lame_cylinder_bore_stress",
    "sheet_min_bend_radius",
    "tolerance_worst_case_stack",
    "conformance_refinement_upper",
    "conformance_refinement_lower",
    "workload_realization_identity",
    "buck_efficiency_loss_budget",
    "converter_settling_dominant_pole",
    "thermo_lumped_steady",
    "cost_elec_bom",
    "cost_fluid_bom",
    "cost_civil_takeoff",
    "cam_parse_gcode_fanuc",
    "cam_envelope_gcode_fanuc",
    "cam_collision_coarse_gcode_fanuc",
    "cam_removal_gcode_fanuc",
    "cam_coverage_gcode_fanuc",
    "cam_parse_gcode_marlin",
    "cam_envelope_gcode_marlin",
    "cam_collision_coarse_gcode_marlin",
    "cam_removal_gcode_marlin",
    "cam_coverage_gcode_marlin",
    "hdl_build",
    "hdl_sim_assert_counter",
    "hdl_equiv_directed_counter",
    # WO-155 (D264): the source-generic `hdl.sim_assert` model
    # (`HdlSimAssertGenericModel`) is the exact same "no literature
    # citation to attach" shape as its `hdl_build`/`hdl_sim_assert_
    # counter` siblings immediately above -- the method IS running the
    # request's own bytes through verilator against a declared
    # `signal_table` stimulus, not a closed-form formula from a paper
    # or standard. Baselined for the identical reason those three are,
    # not a new gap this WO opened.
    "hdl_sim_assert_generic",
}


#: D257 ruling 2: a record row that has opted INTO the structured
#: citation shape (its `evidence` table carries a `document` field --
#: the decomposed-reference precedent already at
#: `stdlib/std.power/records/transformer_dry_type.toml:75`'s
#: `xr_ratio_evidence`, generalized here) must carry every field the
#: shape promises: `document`, `revision`, `page`, `table` all
#: non-empty. Existing prose-`reference`-only rows (std.power/ti.logic/
#: st.mcu) have no `document` key and are UNAFFECTED -- this is an
#: ADDITIVE strengthening for the new shape, never a retrofit of the
#: existing corpus (WO-145 body, deliverable 2).
_STRUCTURED_CITATION_FIELDS = ("document", "revision", "page", "table")
_STRUCTURED_FIELD_RE = {
    field: re.compile(rf'{field}\s*=\s*("(?P<sval>[^"]*)"|(?P<ival>-?\d+))')
    for field in _STRUCTURED_CITATION_FIELDS
}


def _structured_citation_offenses(block: str) -> list[str]:
    """Fields missing/empty in a row that opted into the D257 ruling 2
    structured citation shape (detected by the presence of `document`).
    Empty list when the row never opted in (nothing to check)."""
    if not re.search(r"\bdocument\s*=", block):
        return []
    offenses: list[str] = []
    for field in _STRUCTURED_CITATION_FIELDS:
        m = _STRUCTURED_FIELD_RE[field].search(block)
        if m is None:
            offenses.append(f"missing '{field}'")
            continue
        value = m.group("sval") if m.group("sval") is not None else m.group("ival")
        if value is None or value == "":
            offenses.append(f"empty '{field}'")
    return offenses


# frob:doc docs/modules/tools.md#stdlib-organization-sweeps
# frob:waive PERF002 reason="one-shot index/count over a small per-call set"
def check_citations() -> SubCheck:
    """Record rows and model docstrings all carry a citation.

    Baseline uncited built-ins (`_UNCITED_MODEL_BASELINE`) are reported
    (WARNING) but do not gate; any NEW uncited built-in model gates.
    Rows opted into the D257 ruling 2 structured citation shape (a
    `document` field present) additionally gate on
    `_structured_citation_offenses` -- the charter 39 sec. 5.4
    strengthening from "string non-empty" to "page cited, doc/rev
    known", exercised for real by `stdlib/ti.mcu`."""
    offenders: list[str] = []
    rows = 0
    # Fixed-shape glob rooted at stdlib/ -- safe by construction, same
    # note as check_one_family_per_file.
    for records_toml in sorted(STDLIB_DIR.glob("*/records/*.toml")):
        text = records_toml.read_text()
        row_starts = [m.start() for m in re.finditer(r"^\[\[", text, re.MULTILINE)]
        for i, start in enumerate(row_starts):
            end = row_starts[i + 1] if i + 1 < len(row_starts) else len(text)
            block = text[start:end]
            rows += 1
            line_no = text.count("\n", 0, start) + 1
            if "reference" not in block and "citation" not in block:
                offenders.append(
                    f"{records_toml.relative_to(REPO_ROOT)}:{line_no}: no citation"
                )
                continue
            structured_offenses = _structured_citation_offenses(block)
            if structured_offenses:
                offenders.append(
                    f"{records_toml.relative_to(REPO_ROOT)}:{line_no}: "
                    f"structured citation incomplete: {', '.join(structured_offenses)}"
                )

    from regolith.harness.registry import default_registry

    registry = default_registry()
    uncited: list[str] = []
    baseline_hits: list[str] = []
    for model in registry.all_models():
        if registry.pack_of(model.model_id)[0] != "regolith":
            continue  # only lithos built-ins are this check's business
        if model.citation is not None:
            continue
        bare_name = model.signature.name
        if bare_name in _UNCITED_MODEL_BASELINE:
            baseline_hits.append(model.model_id)
        else:
            uncited.append(model.model_id)
    for u in uncited:
        _log.error("organization: model with no citation: %s", u)
    for b in baseline_hits:
        _log.warning(
            "organization: uncited model baseline debt (WO118-F2, report-only): %s", b
        )
    for off in offenders:
        _log.error("organization: record row with no citation: %s", off)
    ok = not offenders and not uncited
    return SubCheck(
        "citations",
        ok,
        rows,
        f"{len(offenders)} uncited row(s), {len(uncited)} new + "
        f"{len(baseline_hits)} baseline (WO118-F2) uncited model(s)",
    )


# frob:doc docs/modules/tools.md#stdlib-organization-sweeps
def check_generated_drift() -> SubCheck:
    """Extends the WO-66 generator drift test into a standalone check."""
    from tools.stdlib.generate_all import generate_all

    mismatches: list[str] = []
    for path_str, expected in generate_all().items():
        path = Path(path_str)
        if not path.is_file():
            mismatches.append(f"{path}: missing")
            continue
        if path.read_text(encoding="utf-8") != expected:
            mismatches.append(f"{path}: drifted")
    for m in mismatches:
        _log.error("organization: generated-file drift: %s", m)
    return SubCheck(
        "generated_drift", not mismatches, len(mismatches), f"{len(mismatches)} drifted"
    )


#: Module stem -> manifest group name, for the pre-existing manifest
#: entries that predate this checker and name a group differently from
#: its bare module stem (the established `std.models` precedent, not a
#: convention this checker is free to renormalize).
_GROUP_ALIASES = {
    "conformance": "conformance_refinement",
}


def _registered_builtin_groups() -> set[str]:
    """The canonical `std.models` group name per registered built-in.

    A model's group is its module's directory name if it lives under a
    subpackage of `harness/models/` (the `cam`/`dfm`/`hdl` precedent),
    else its module's file stem (`beam_bending`, `buck_ripple`, ...),
    aliased per `_GROUP_ALIASES` where the manifest's established name
    differs from the bare stem.
    """
    from regolith.harness.registry import default_registry

    registry = default_registry()
    groups: set[str] = set()
    models_root = "regolith.harness.models"
    for model in registry.all_models():
        if registry.pack_of(model.model_id)[0] != "regolith":
            continue  # only built-ins live in this manifest
        module = type(model).__module__
        if not module.startswith(models_root):
            continue
        rest = module[len(models_root) + 1 :]  # e.g. "cam.models" or "beam_bending"
        group = rest.split(".", 1)[0]
        groups.add(_GROUP_ALIASES.get(group, group))
    return groups


# frob:doc docs/modules/tools.md#stdlib-organization-sweeps
# frob:waive PERF004 reason="one-shot sort of a small set, never re-sorted"
def check_models_manifest() -> SubCheck:
    """`std.models`'s manifest names every registered built-in module."""
    manifest_path = STDLIB_DIR / "std.models" / "magnetite.toml"
    text = manifest_path.read_text()
    m = re.search(r"models\s*=\s*\[(.*?)\]", text, re.DOTALL)
    declared: set[str] = set()
    if m:
        for line in m.group(1).splitlines():
            line = line.split("#", 1)[0].strip().strip(",")
            if line.startswith('"') and line.endswith('"'):
                declared.add(line.strip('"'))

    actual = _registered_builtin_groups()
    missing = sorted(actual - declared)
    phantom = sorted(declared - actual)
    for name in missing:
        _log.error("organization: std.models manifest missing '%s'", name)
    for name in phantom:
        _log.error("organization: std.models manifest names phantom '%s'", name)
    ok = not missing and not phantom
    return SubCheck(
        "models_manifest",
        ok,
        len(actual),
        f"{len(missing)} missing, {len(phantom)} phantom",
    )


def _feldspar_claim_kinds() -> set[str] | None:
    """Best-effort: claim kinds the feldspar pack exposes to lithos.

    Returns None (skip, not a failure) when no sibling checkout is
    present or its manifest surface cannot be introspected -- the
    established feldspar-link degrade-honestly posture (WO-109/D223).
    """
    if not FELDSPAR_DIR.is_dir():
        return None
    try:
        import importlib
        import sys as _sys

        _sys.path.insert(0, str(FELDSPAR_DIR / "python"))
        catalog = importlib.import_module("feldspar.catalog")
        from feldspar.pack.payload_bridge import NoStoreResolver

        registry = catalog.build_engine_catalog(NoStoreResolver())
        kinds = {info.solver_id.rsplit(".", 1)[0] for info, _fn in registry}
        return kinds
    except Exception as exc:  # pragma: no cover -- degrade, never fail the sweep
        _log.warning("organization: feldspar introspection unavailable: %s", exc)
        return None


# frob:doc docs/modules/tools.md#stdlib-organization-sweeps
def check_double_home() -> SubCheck:
    """No claim kind resolvable from both a built-in and a pack model
    without a recorded router preference (charter 39 sec. 4)."""
    from regolith.harness.registry import default_registry

    registry = default_registry()
    builtin_kinds = {
        model.signature.claim_kind
        for model in registry.all_models()
        if registry.pack_of(model.model_id)[0] == "regolith"
    }
    feldspar_kinds = _feldspar_claim_kinds()
    if feldspar_kinds is None:
        return SubCheck("double_home", True, 0, "feldspar unavailable, skipped")
    both = sorted(builtin_kinds & feldspar_kinds)
    for kind in both:
        _log.error("organization: double-home claim kind (no router pref): %s", kind)
    return SubCheck("double_home", not both, len(both), f"{len(both)} double-home")


# frob:doc docs/modules/tools.md#stdlib-organization-sweeps
def check_charter_cross_drift() -> SubCheck:
    """Charter 39 sec. 4 == feldspar spec 12 sec. 4, modulo heading."""
    lithos_charter = (
        REPO_ROOT / "docs" / "spec" / "toolchain" / "39-stdlib-organization.md"
    )
    feldspar_spec = FELDSPAR_DIR / "docs" / "spec" / "12-solver-organization.md"
    if not feldspar_spec.is_file():
        return SubCheck("charter_drift", True, 0, "feldspar unavailable, skipped")

    def _sec4(path: Path) -> str:
        text = path.read_text()
        m = re.search(r"^## 4\. .*?\n(.*?)(?=^## 5\.)", text, re.MULTILINE | re.DOTALL)
        return m.group(1).strip() if m else ""

    lhs, rhs = _sec4(lithos_charter), _sec4(feldspar_spec)
    ok = lhs == rhs and bool(lhs)
    if not ok:
        _log.error("organization: charter 39 sec. 4 drifted from feldspar spec 12")
    return SubCheck(
        "charter_drift", ok, len(lhs), "byte-identical" if ok else "DRIFTED"
    )


_ALL_CHECKS = {
    "prefix": check_prefix_reservation,
    "one_family": check_one_family_per_file,
    "citations": check_citations,
    "generated_drift": check_generated_drift,
    "models_manifest": check_models_manifest,
    "double_home": check_double_home,
    "charter_drift": check_charter_cross_drift,
}


# frob:doc docs/modules/tools.md#stdlib-organization-sweeps
def run_all() -> list[SubCheck]:
    """Run every organization sweep; return the list of sub-checks."""
    return [fn() for fn in _ALL_CHECKS.values()]


# frob:doc docs/modules/tools.md#stdlib-organization-sweeps
# frob:waive TEST001 reason="CLI entry pt; see test_stdlib_organization.py"
# frob:waive TEST005 reason="measured 8.3% branch on 2026-07-19; backfill T-0036"
def main(argv: list[str] | None = None) -> int:
    """Standalone CLI: run one named check (`--check NAME`) or all."""
    import argparse

    parser = argparse.ArgumentParser(description="Stdlib organization sweeps.")
    parser.add_argument("--check", choices=sorted(_ALL_CHECKS), default=None)
    args = parser.parse_args(argv)

    checks = [_ALL_CHECKS[args.check]()] if args.check else run_all()
    ok = True
    for c in checks:
        print(f"  [{'PASS' if c.ok else 'FAIL'}] {c.name:16} {c.note}")
        ok = ok and c.ok
    print("ORGANIZATION: PASS" if ok else "ORGANIZATION: FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
