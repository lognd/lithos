"""The ``fleet`` health leg: every D210 project ships, green, on census.

For every fleet project (an ``examples/`` directory with a
``magnetite.toml``, minus documented exemptions) this leg drives the
REAL CLI -- ``regolith build --release`` then ``regolith ship`` -- and
asserts, per project:

* ``build --release`` exits 0 with ``release_ok=true`` and zero stale
  waivers (E0701);
* ``ship`` writes a package whose every manifest file re-hashes clean
  (integrity, not signature -- D216.3 packages are unsigned clean-gate);
* every backend family is present-or-named-absent (the shipped family
  set is recorded in the census);
* the per-project census -- ``{obligations, discharged,
  accepted_deviation, violated, families, waived_by_class, deferred}``
  -- matches the committed golden
  ``tests/golden/data/fleet_census.json`` (regeneration is the
  ordinary golden flow with diff review).

Census v2 (WO-117, D220.3): ``discharged`` means MODEL-BACKED RESOLVED
(``evidence.status == "discharged"``, the same predicate the release
gate's ``is_resolved`` uses -- never merely "no deferral", which
double-counted the pin-unmatched indeterminate, WO117-F1);
``waived_by_class`` classifies every listed deviation into the D220.2
closed classes (``tools.health.waiver_classes``, one home);
``deferred`` counts the results carrying a named non-violated deferral
or unresolved (non-discharged) evidence -- the machinery-residual
mass, acceptance-independent. The leg FAILS with a NAMED row on any
per-class rigor regression: a ``discharged`` decrease against the
golden, or any waiver outside the closed classes (``unclassified``
must be zero everywhere, never merely golden-compared).

Calc-book completeness (WO-117 deliverable 3): every shipped package's
``calc/audit_index.json`` must balance (WO-114's zero-unexplained-rows
partition); the outcome rides ``fleet_results.json`` so the
consistency leg gates on it without rebuilding.

Determinism sub-leg: one mech-heavy project ships twice and every
deterministic artifact is byte-compared (a manifest-hash equality).

Detail is DEBUG; ONE INFO row and a loud verdict per D219/WO-107. The
per-project census + diagnostics are cached under ``.regolith/health``
so the ``consistency`` leg can read waiver integrity without rebuilding.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from regolith.logging_setup import get_logger
from regolith.progress import log_progress
from regolith.progress import start as progress_start

from tools.health.report import HEALTH_OUT, REPO_ROOT, LegSummary
from tools.health.waiver_classes import WAIVER_CLASSES, classify_deviations

_log = get_logger(__name__)

# D210: exemptions from the fleet (documented, by directory name). The
# retired examples/systems/cnc_router is already deleted; negative/
# registry/hdl carry no magnetite.toml so they never enter discovery.
# This set stays EMPTY by design -- an entry here must cite its reason.
# frob:doc docs/modules/tools.md#health-fleet-leg
FLEET_EXEMPTIONS: frozenset[str] = frozenset()

# The mech-heavy project the determinism sub-leg ships twice. dune_buggy
# is the largest multi-file mech system and realizes no byte-unstable
# geometry (identity BOM rows), so all its artifacts are byte-comparable.
# frob:doc docs/modules/tools.md#health-fleet-leg
DETERMINISM_PROJECT = "dune_buggy"

# The small project the `make check` health-smoke builds+ships (one
# project only) -- timber_pavilion is the fastest fleet member (10
# obligations, release_ok=true) so the smoke stays cheap.
# frob:doc docs/modules/tools.md#health-fleet-leg
SMOKE_PROJECT = "timber_pavilion"

# Extensions whose bytes are NOT platform-stable (OCCT's STEP serializer,
# WO-22 acceptance) -- excluded from the determinism byte-compare.
_NONDETERMINISTIC_EXT: frozenset[str] = frozenset({".step", ".stp"})

# frob:doc docs/modules/tools.md#health-fleet-leg
CENSUS_GOLDEN = REPO_ROOT / "tests" / "golden" / "data" / "fleet_census.json"


# frob:doc docs/modules/tools.md#health-fleet-leg
class ProjectCensus(BaseModel):
    """One project's stable census row (the golden-compared shape).

    Census v2 (D220.3): ``discharged`` is model-backed resolved
    (``evidence.status == "discharged"``); ``waived_by_class`` is the
    D220.2 per-class accounting over the listed deviations (keys
    ``a``/``b``/``c``/``d``, always all present); ``deferred`` is the
    named-machinery-residual row count (non-violated deferrals plus
    unresolved evidence), independent of waiver coverage.
    """

    model_config = ConfigDict(frozen=True)

    obligations: int
    discharged: int
    accepted_deviation: int
    violated: int
    deferred: int
    waived_by_class: dict[str, int]
    families: tuple[str, ...]


# frob:doc docs/modules/tools.md#health-fleet-leg
class ProjectResult(BaseModel):
    """A fleet project's full per-run outcome (cached, not all golden).

    ``unclassified_waivers`` (never golden -- always must be empty) and
    ``calc_book_balanced`` ride the cache so the consistency leg reads
    both without rebuilding.
    """

    model_config = ConfigDict(frozen=True)

    project: str
    root: str
    release_ok: bool
    ship_clean: bool
    stale_waivers: int
    census: ProjectCensus
    unclassified_waivers: tuple[str, ...] = ()
    calc_book_balanced: bool = False
    # WO-125 (charter 40 sec. 1 acceptance): `ship --emit-profile debug`
    # succeeds wherever release ships today, with the census/verdict
    # surface IDENTICAL between profiles (gate summary + evidence
    # rollup byte-equal). Default True so a cached pre-WO-125 row does
    # not fail retroactively; freshly-run rows always set it.
    debug_profile_clean: bool = True


# frob:doc docs/modules/tools.md#health-fleet-leg
def discover_fleet() -> list[tuple[str, Path]]:
    """Every fleet project as ``(name, root)``, sorted, minus exemptions."""
    found: list[tuple[str, Path]] = []
    for manifest in sorted((REPO_ROOT / "examples").rglob("magnetite.toml")):
        root = manifest.parent
        name = root.name
        if name in FLEET_EXEMPTIONS:
            _log.debug("fleet: skipping exempt project %s", name)
            continue
        found.append((name, root))
    return found


def _run_cli(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run ``regolith <args>`` through the installed console script."""
    _log.debug("fleet: regolith %s", " ".join(args))
    return subprocess.run(
        ["regolith", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def _census_from_report(
    report: dict,
) -> tuple[ProjectCensus, bool, int, tuple[str, ...]]:
    """Derive ``(census, release_ok, stale_waivers, unclassified)`` from
    a build report.

    Census v2 (D220.3; kept in LOCKSTEP with
    ``regolith.backends.calc.build_calc_book`` -- the reconciliation
    golden proves it):

    * ``discharged`` = results with no deferral AND ``evidence.status
      == "discharged"`` (model-backed resolved, the release gate's own
      ``is_resolved`` predicate; a pin-unmatched indeterminate is NOT
      discharged, WO117-F1);
    * ``violated`` = results whose deferral is a ``violated`` verdict;
    * ``deferred`` = every other non-discharged result (named
      non-violated deferrals + unresolved evidence), independent of
      waiver coverage -- the machinery-residual mass;
    * ``accepted_deviation`` = the acceptance ledger's accepted hashes;
    * ``waived_by_class`` = the D220.2 per-class classification of the
      listed deviations' bases (``unclassified`` returned separately --
      it FAILS the leg, never lands in the golden);
    * ``stale_waivers`` = deviations the harvest marked stale plus
      ledger errors (each is an E0701 the build is not clean under).
    """
    final = report["final"]
    results = final["results"]
    obligations = len(results)
    discharged = sum(
        1
        for r in results
        if r["deferral"] is None
        and r.get("evidence") is not None
        and r["evidence"].get("status") == "discharged"
    )
    violated = sum(
        1
        for r in results
        if r["deferral"] is not None and r["deferral"].get("reason") == "violated"
    )
    deferred = obligations - discharged - violated
    acceptance = final["acceptance"]
    accepted = len(acceptance["accepted_hashes"])
    waived_by_class, unclassified = classify_deviations(
        [d.get("basis", "") for d in acceptance["deviations"]]
    )
    stale = sum(1 for d in acceptance["deviations"] if d.get("kind") == "stale")
    stale += len(acceptance["errors"])
    census = ProjectCensus(
        obligations=obligations,
        discharged=discharged,
        accepted_deviation=accepted,
        violated=violated,
        deferred=deferred,
        waived_by_class=waived_by_class,
        families=(),  # filled from the ship package below
    )
    return census, bool(final["release_ok"]), stale, tuple(unclassified)


def _ship_families(ship_dir: Path) -> tuple[str, ...]:
    """The backend families present in a ship package (manifest-derived)."""
    manifest = ship_dir / "manifest.json"
    if not manifest.is_file():
        return ()
    data = json.loads(manifest.read_text())
    families: set[str] = set()
    for entry in data.get("files", ()):
        rel = entry["relpath"]
        if "/" in rel:
            families.add(rel.split("/", 1)[0])
    return tuple(sorted(families))


def _ship_integrity(ship_dir: Path) -> bool:
    """Re-hash every manifest file and confirm the recorded sha256.

    Integrity, not signature (D216.3 packages are unsigned clean-gate),
    so this never needs a TrustKeySet -- it is the ``verify-clean``
    property the health gate can prove on an unsigned package.
    """
    import hashlib

    manifest = ship_dir / "manifest.json"
    if not manifest.is_file():
        return False
    data = json.loads(manifest.read_text())
    for entry in data.get("files", ()):
        path = ship_dir / entry["relpath"]
        if not path.is_file():
            _log.debug("fleet: ship names missing file %s", entry["relpath"])
            return False
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        recorded = entry["sha256"].removeprefix("sha256:")
        if digest != recorded:
            _log.debug("fleet: hash drift on %s", entry["relpath"])
            return False
    return True


def _ship_hashes(ship_dir: Path) -> dict[str, str]:
    """``relpath -> sha256`` for every packaged file (determinism compare)."""
    data = json.loads((ship_dir / "manifest.json").read_text())
    return {e["relpath"]: e["sha256"] for e in data.get("files", ())}


def _calc_book_balanced(ship_dir: Path) -> bool:
    """WO-114's zero-unexplained-rows check over a shipped package.

    Validates ``calc/audit_index.json`` with the REAL
    ``regolith.backends.calc.AuditIndex`` model and invokes its
    ``summary.balanced()`` (never a re-implementation), plus the
    one-row-per-obligation property. A package without the file fails
    -- every release package carries the calc family (D221).
    """
    from regolith.backends.calc import AuditIndex

    index_path = ship_dir / "calc" / "audit_index.json"
    if not index_path.is_file():
        _log.error("fleet: %s carries no calc/audit_index.json", ship_dir)
        return False
    index = AuditIndex.model_validate_json(index_path.read_bytes())
    balanced = index.summary.balanced()
    rows_total = len(index.rows) == index.summary.obligations
    if not balanced or not rows_total:
        _log.error(
            "fleet: %s audit index has unexplained rows (balanced=%s rows=%d/%d)",
            index.project,
            balanced,
            len(index.rows),
            index.summary.obligations,
        )
    return balanced and rows_total


def _debug_ship_matches(
    name: str,
    root: Path,
    build_dir: Path,
    ship_dir: Path,
    work: Path,
    spec: Path,
) -> bool:
    """WO-125: ship the SAME release build under ``--emit-profile
    debug`` and prove the fleet acceptance facts -- exit 0, package
    integrity, and verdict/census equality with the release package
    (``gate_summary.json`` bytes and the manifest ``evidence_rollup``
    identical; D206/D220.1 untouchable)."""
    debug_dir = work / "ship_debug"
    args = [
        "ship",
        str(root),
        "--build",
        str(build_dir),
        "--out",
        str(debug_dir),
        "--emit-profile",
        "debug",
    ]
    if spec.is_file():
        args += ["--spec", str(spec)]
    debug = _run_cli(args, cwd=REPO_ROOT)
    if debug.returncode != 0 or not _ship_integrity(debug_dir):
        _log.error(
            "fleet: %s debug-profile ship failed (rc=%d)", name, debug.returncode
        )
        _log.debug("fleet: %s debug ship stderr: %s", name, debug.stderr[-2000:])
        return False
    gate_equal = (ship_dir / "gate_summary.json").read_bytes() == (
        debug_dir / "gate_summary.json"
    ).read_bytes()
    rollup_release = json.loads((ship_dir / "manifest.json").read_text())[
        "evidence_rollup"
    ]
    rollup_debug = json.loads((debug_dir / "manifest.json").read_text())[
        "evidence_rollup"
    ]
    if not gate_equal or rollup_release != rollup_debug:
        _log.error(
            "fleet: %s debug profile drifted the verdict surface "
            "(gate_equal=%s rollup_equal=%s) -- D206 violation",
            name,
            gate_equal,
            rollup_release == rollup_debug,
        )
        return False
    _log.debug("fleet: %s debug-profile ship clean + census-identical", name)
    return True


def _build_and_ship(name: str, root: Path, work: Path) -> ProjectResult | None:
    """Build --release + ship one project into ``work``; ``None`` on rc!=0."""
    build_dir = work / "build"
    ship_dir = work / "ship"
    spec = root / "ship.spec.json"
    build_args = [
        "build",
        "--release",
        str(root),
        "--json",
        "--out",
        str(build_dir),
    ]
    # `build` reads ONLY the spec's `elec_boards` block (WO-42 elec leg):
    # an elec project must realize its boards at build time so the later
    # `ship --build` package carries the boards family (mainboard_mx).
    if spec.is_file():
        build_args += ["--spec", str(spec)]
    build = _run_cli(build_args, cwd=REPO_ROOT)
    if not build.stdout.strip():
        _log.error("fleet: %s build emitted no JSON (rc=%d)", name, build.returncode)
        _log.debug("fleet: %s build stderr: %s", name, build.stderr[-2000:])
        return None
    report = json.loads(build.stdout)
    census, release_ok, stale, unclassified = _census_from_report(report)

    # `ship --build` consumes the already-run release; the `--spec`
    # carries the mech/elec BOM + drawings set. An elec project's board
    # is realized during `build --spec` (to the fixed
    # `.regolith/board/board.kicad_pcb`), so `ship --build` finds it and
    # packages the boards family.
    ship_args = ["ship", str(root), "--build", str(build_dir), "--out", str(ship_dir)]
    if spec.is_file():
        ship_args += ["--spec", str(spec)]
    ship = _run_cli(ship_args, cwd=REPO_ROOT)
    ship_clean = ship.returncode == 0 and _ship_integrity(ship_dir)
    if not ship_clean:
        _log.debug("fleet: %s ship stderr: %s", name, ship.stderr[-2000:])

    # WO-125 fleet acceptance (charter 40 sec. 1): the SAME build ships
    # under the debug profile too -- rc 0 + integrity + verdict/census
    # equality (gate summary + evidence rollup byte-equal between the
    # two packages; D206/D220.1). Only meaningful when the release ship
    # itself was clean.
    debug_profile_clean = ship_clean and _debug_ship_matches(
        name, root, build_dir, ship_dir, work, spec
    )

    census = census.model_copy(update={"families": _ship_families(ship_dir)})
    return ProjectResult(
        project=name,
        root=str(root.relative_to(REPO_ROOT)),
        release_ok=release_ok,
        ship_clean=ship_clean,
        stale_waivers=stale,
        census=census,
        unclassified_waivers=unclassified,
        calc_book_balanced=ship_clean and _calc_book_balanced(ship_dir),
        debug_profile_clean=debug_profile_clean,
    )


def _cross_dir_design_hash_ok(root: Path) -> bool:
    """The shipped design_hash is stable across checkout paths (WO-106).

    ``ship._design_hash`` used to hash ABSOLUTE source paths, so a
    byte-identical design shipped a DIFFERENT ``design_hash`` from every
    worktree/checkout. It now hashes project-relative paths; this proves
    it by hashing the same project from its real root and from a copy
    under a temporary root and asserting equality.
    """
    import shutil

    from regolith.backends.ship import _design_hash

    real = _design_hash((str(root),), str(root))
    with tempfile.TemporaryDirectory() as td:
        dest = Path(td) / root.name
        shutil.copytree(root, dest)
        copied = _design_hash((str(dest),), str(dest))
    if real != copied:
        _log.error("fleet: design_hash drifts across checkout paths (%s)", root.name)
    return real == copied


def _determinism_ok(name: str, root: Path) -> bool:
    """Ship one project twice; byte-compare every deterministic artifact,
    then confirm the design_hash is stable across checkout paths."""
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        r1 = _build_and_ship(name, root, Path(a))
        r2 = _build_and_ship(name, root, Path(b))
        if r1 is None or r2 is None:
            return False
        h1 = _ship_hashes(Path(a) / "ship")
        h2 = _ship_hashes(Path(b) / "ship")
        deterministic = {
            rel for rel in h1 if Path(rel).suffix.lower() not in _NONDETERMINISTIC_EXT
        }
        for rel in sorted(deterministic):
            if h1.get(rel) != h2.get(rel):
                _log.error("fleet: determinism drift on %s (%s)", name, rel)
                return False
        _log.debug("fleet: determinism OK over %d artifacts", len(deterministic))
    return _cross_dir_design_hash_ok(root)


# frob:doc docs/modules/tools.md#health-fleet-leg
def load_census_golden() -> dict[str, ProjectCensus]:
    """The committed per-project census golden (empty map if absent).

    A row that does not validate against the CURRENT census shape (a
    pre-v2 golden lacking ``waived_by_class``/``deferred``) is dropped
    with a loud ERROR -- the fleet leg then reports the project as
    census drift (it is "not in the golden"), so a stale-shape golden
    can only ever fail toward regeneration, never silently pass.
    """
    from pydantic import ValidationError

    if not CENSUS_GOLDEN.is_file():
        return {}
    raw = json.loads(CENSUS_GOLDEN.read_text())
    rows: dict[str, ProjectCensus] = {}
    for name, row in raw.items():
        try:
            rows[name] = ProjectCensus.model_validate(row)
        except ValidationError:
            _log.error(
                "fleet: census golden row %s has a stale (pre-v2) shape; "
                "regenerate with REGOLITH_UPDATE_GOLDEN=1",
                name,
            )
    return rows


def _write_census_golden(rows: dict[str, ProjectCensus]) -> None:
    """Rewrite the census golden (ordinary golden flow, diff-reviewed)."""
    payload = {k: rows[k].model_dump(mode="json") for k in sorted(rows)}
    CENSUS_GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    CENSUS_GOLDEN.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")


# frob:doc docs/modules/tools.md#health-fleet-leg
def run(*, smoke: bool = False, update_golden: bool = False) -> LegSummary:
    """Run the fleet leg; return its standardized summary row.

    ``smoke`` restricts the leg to a single project (the cheap
    ``make check`` probe). ``update_golden`` rewrites the census golden
    instead of comparing (``REGOLITH_UPDATE_GOLDEN=1``).
    """
    fleet = discover_fleet()
    if smoke:
        fleet = [next((n, r) for n, r in fleet if n == SMOKE_PROJECT)]
    _log.info("fleet: %d project(s)%s", len(fleet), " (smoke)" if smoke else "")

    golden = load_census_golden()
    results: list[ProjectResult] = []
    green = 0
    census_mismatch: list[str] = []
    rigor_regressions: list[str] = []
    fresh: dict[str, ProjectCensus] = {}

    # WO-119 (D228): the fleet loop was silent between the one INFO row
    # above and each project's DEBUG summary below -- a long fleet run
    # gave a progress-agnostic consumer nothing to render. One DEBUG
    # progress record per project (done/total over the whole fleet).
    fleet_started = progress_start()
    for i, (name, root) in enumerate(fleet, start=1):
        log_progress(
            phase="fleet", subject=name, done=i, total=len(fleet), started=fleet_started
        )
        with tempfile.TemporaryDirectory() as work:
            res = _build_and_ship(name, root, Path(work))
        if res is None:
            _log.error("fleet: %s FAILED to build/ship", name)
            continue
        results.append(res)
        fresh[name] = res.census
        ok = (
            res.release_ok
            and res.ship_clean
            and res.stale_waivers == 0
            and res.census.violated == 0
            # WO-125: debug-profile ship succeeds + census identical
            # wherever release ships today (charter 40 sec. 1).
            and res.debug_profile_clean
        )
        # D220.3: an out-of-class waiver fails REGARDLESS of the golden
        # (never merely golden-compared -- a regenerated golden must not
        # be able to launder one in).
        for basis in res.unclassified_waivers:
            rigor_regressions.append(
                f"{name}: waiver outside the D220.2 classes: {basis[:120]!r}"
            )
            ok = False
        if not update_golden and name in golden:
            before = golden[name]
            # D220.3 per-class regression: a discharged->waived/deferred
            # move is named, not just "mismatch".
            if res.census.discharged < before.discharged:
                rigor_regressions.append(
                    f"{name}: discharged regressed "
                    f"{before.discharged} -> {res.census.discharged}"
                )
            for cls in WAIVER_CLASSES:
                got = res.census.waived_by_class.get(cls, 0)
                was = before.waived_by_class.get(cls, 0)
                if got > was:
                    rigor_regressions.append(
                        f"{name}: waived class {cls} grew {was} -> {got}"
                    )
            if before != res.census:
                census_mismatch.append(name)
                ok = False
        elif not update_golden:
            # Not enrolled (or its golden row failed v2 validation --
            # see load_census_golden): drift toward regeneration.
            census_mismatch.append(name)
            ok = False
        if ok:
            green += 1
        _log.debug(
            "fleet: %s release_ok=%s ship_clean=%s stale=%d census=%s",
            name,
            res.release_ok,
            res.ship_clean,
            res.stale_waivers,
            res.census.model_dump(),
        )

    det_ok = True
    if not smoke:
        det_root = dict(fleet).get(DETERMINISM_PROJECT)
        if det_root is None:
            _log.error(
                "fleet: determinism project %s not discovered", DETERMINISM_PROJECT
            )
            det_ok = False
        else:
            det_ok = _determinism_ok(DETERMINISM_PROJECT, det_root)

    if update_golden:
        _write_census_golden(fresh)
        _log.info("fleet: rewrote census golden (%d rows)", len(fresh))

    # Cache the per-project results for the consistency leg (waiver ledger).
    HEALTH_OUT.mkdir(parents=True, exist_ok=True)
    (HEALTH_OUT / "fleet_results.json").write_text(
        json.dumps(
            {r.project: r.model_dump(mode="json") for r in results},
            sort_keys=True,
            indent=2,
        )
        + "\n"
    )

    ok = (
        len(results) == len(fleet)
        and green == len(fleet)
        and det_ok
        and not census_mismatch
        and not rigor_regressions
    )
    counts = {
        "projects": len(fleet),
        "green": green,
        "mismatch": len(census_mismatch),
        "rigor_regressions": len(rigor_regressions),
    }
    for row in rigor_regressions:
        _log.error("fleet: rigor regression -- %s", row)
    evidence = "tests/golden/data/fleet_census.json"
    if rigor_regressions:
        evidence = f"rigor regression: {'; '.join(rigor_regressions[:3])}"
    elif census_mismatch:
        drift = ", ".join(census_mismatch)
        evidence = f"census drift: {drift} (regen: REGOLITH_UPDATE_GOLDEN=1)"
    elif not det_ok:
        evidence = f"determinism drift on {DETERMINISM_PROJECT}"
    return LegSummary(leg="fleet", ok=ok, counts=counts, evidence=evidence)


# frob:doc docs/modules/tools.md#health-fleet-leg
# frob:waive TEST001 reason="CLI entry pt driving full fleet rebuilds; see make health"
def main(argv: list[str] | None = None) -> int:
    """Run the fleet leg standalone; exit 0 iff green."""
    import argparse
    import os

    parser = argparse.ArgumentParser(description="The fleet health leg.")
    parser.add_argument("--smoke", action="store_true", help="One project only.")
    args = parser.parse_args(argv)
    update = os.environ.get("REGOLITH_UPDATE_GOLDEN") == "1"
    summary = run(smoke=args.smoke, update_golden=update)
    print(summary.row())
    return 0 if summary.ok else 1


if __name__ == "__main__":
    sys.exit(main())
