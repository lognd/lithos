"""The typer application object and its subcommands (AD-10).

Rich/terminal output lives only in this layer; libraries return data.
WO-15 adds ``check``/``build``/``debug``/``fmt``; WO-01 provides
``version`` so the installed console script is exercisable end to end.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import click
import httpx
import typer
from typani.result import Err, Ok, Result

from regolith import compiler, config, core_version
from regolith._schema.models import RealizedLayout, WaiveLedger
from regolith.backends.artifacts import NativeArtifactStore
from regolith.backends.drawings import DrawingsBackend
from regolith.backends.drawings.backend import DrawingSpec
from regolith.backends.elec import AssemblyLine as ElecAssemblyLine
from regolith.backends.elec import ElecBackend
from regolith.backends.framework import Backend
from regolith.backends.mech import AssemblyLine as MechAssemblyLine
from regolith.backends.mech import FabNoteSpec, MechBackend
from regolith.backends.parity import (
    build_parity_report,
    gate_summary_line,
    render_parity_report,
)
from regolith.backends.plugin import load_backend_plugins
from regolith.backends.ship import ship as run_ship
from regolith.backends.ship import verify as run_verify
from regolith.cli.discovery import discover_project_root
from regolith.docgen import claim_statuses, extract_package, render_markdown
from regolith.logging_setup import get_logger
from regolith.magnetite.client import RegistryClient
from regolith.magnetite.index import latest_version, parse_index, select_version
from regolith.magnetite.lints import resolve_lint_config
from regolith.magnetite.manifest import Manifest, load_manifest
from regolith.magnetite.scaffold import VALID_TEMPLATES, scaffold_project
from regolith.magnetite.sources import Registry
from regolith.magnetite.trust import (
    TrustKeySet,
    generate_signing_key,
    keys_dir,
    load_signing_key,
)
from regolith.magnetite.vendor import VendorPin
from regolith.magnetite.vendor import vendor as vendor_pins
from regolith.orchestrator.lockfile import Lockfile, LockRow, LockSection
from regolith.orchestrator.lockfile import parse as parse_lockfile
from regolith.orchestrator.lockfile import render as render_lockfile
from regolith.orchestrator.nogood_cache import NogoodCache
from regolith.orchestrator.optimize import (
    discrete_domains_from_spec,
    load_trace,
    optimize_discrete,
    store_trace,
    winner_lock_row,
)
from regolith.orchestrator.orchestrate import (
    ElecBoardInputs,
    StagedBuildReport,
    staged_build,
)
from regolith.orchestrator.payload_store import PayloadStore
from regolith.orchestrator.test_runner import (
    discover_rule_pack_files,
    render_summary,
    run_tests,
)
from regolith.orchestrator.tiers import TIER_BY_VERB, BuildTier
from regolith.plugins import PluginKind, discover_plugins

_log = get_logger(__name__)

app = typer.Typer(
    name="regolith",
    help="The regolith engineering toolchain (hematite + cuprite).",
    no_args_is_help=True,
)

# Exit codes (WO-15): distinguish clean from diagnostics from internal
# error so CI and humans can branch on them.
EXIT_CLEAN = 0
EXIT_DIAGNOSTICS = 1
EXIT_INTERNAL_ERROR = 2


magnetite_app = typer.Typer(
    name="magnetite",
    help="The magnetite package tool (manifests, registry, scaffolding).",
    no_args_is_help=True,
)
app.add_typer(magnetite_app, name="magnetite")

plugin_app = typer.Typer(
    name="plugin",
    help="Inspect the one regolith.plugins discovery seam (AD-26).",
    no_args_is_help=True,
)
app.add_typer(plugin_app, name="plugin")

config_app = typer.Typer(
    name="config",
    help="The one configuration doctrine (WO-59 D164): "
    "get|set|list|where over regolith.config.",
    no_args_is_help=True,
)
app.add_typer(config_app, name="config")

rules_app = typer.Typer(
    name="rules",
    help="Rule-pack authoring tools (WO-28): expect-fixture runs and try-it loops.",
    no_args_is_help=True,
)
app.add_typer(rules_app, name="rules")

key_app = typer.Typer(
    name="key",
    help="Local signing keys for `ship --key` (wraps regolith.magnetite.trust).",
    no_args_is_help=True,
)
magnetite_app.add_typer(key_app, name="key")
# Promoted to top level too (`regolith key new` == `regolith magnetite key
# new`): `ship --key` needs one and there was previously no way to mint
# one from the CLI at all.
app.add_typer(key_app, name="key")

index_app = typer.Typer(
    name="index",
    help="Inspect a local sparse-index file (wraps regolith.magnetite.index).",
    no_args_is_help=True,
)
magnetite_app.add_typer(index_app, name="index")

manifest_app = typer.Typer(
    name="manifest",
    help="Inspect a magnetite.toml manifest (wraps regolith.magnetite.manifest).",
    no_args_is_help=True,
)
magnetite_app.add_typer(manifest_app, name="manifest")

# `regolith magnetite vendor`/`fetch` (regolith/11 sec. 10.2-10.3): now that
# `load_manifest` parses `[sources]` into `regolith.magnetite.sources.Sources`,
# the CLI has a real config surface to route packages through and can build
# an actual `RegistryClient`. `_LOCKFILE_FILENAME` mirrors `magnetite.toml`'s
# resolution (dir-or-file argument, sibling lockfile).

_LOCKFILE_FILENAME = "regolith.lock"


_FILE_TRANSPORT_MAX_READ_BYTES = 8 * 1024 * 1024  # 8 MiB (M1): cap file:// reads


class _FileTransport(httpx.BaseTransport):
    """Serves ``file://`` GETs from local disk (offline/vendor-mirror sources).

    Lets a manifest's ``[sources]`` point ``index_url``/``archive_url`` at a
    plain directory (a vendor mirror or a test fixture, sec. 10.3) with no
    network involved -- the real CLI client mounts this for ``file://`` and
    falls back to the normal HTTP transport for everything else.

    M1: confined to ``roots`` (the registry's own ``index_url``/
    ``archive_url`` directories) -- httpx normalizes ``..`` dot-segments
    before this transport ever sees the path, but a package/digest name
    the CLI splices into the URL (``fetch "../../../etc/passwd"``) can
    still walk the resolved path outside the mirror. Every resolved
    target must stay under one of ``roots``, must not be a symlink, and
    must be a plain regular file under `_FILE_TRANSPORT_MAX_READ_BYTES`
    -- refusing an existence oracle / DoS via `/dev/zero` or a pipe.
    """

    def __init__(self, roots: tuple[Path, ...]) -> None:
        """Confine served reads to the resolved directories in `roots`."""
        self._roots = tuple(root.resolve() for root in roots)

    def _confined(self, target: Path) -> Path | None:
        resolved = target.resolve()
        for root in self._roots:
            if resolved.is_relative_to(root):
                return resolved
        return None

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if request.method != "GET":
            return httpx.Response(405)
        target = Path(request.url.path)
        resolved = self._confined(target)
        if resolved is None:
            _log.warning("file:// fetch refused (outside registry root): %s", target)
            return httpx.Response(404)
        if resolved.is_symlink() or not resolved.is_file():
            _log.warning("file:// fetch refused (not a regular file): %s", resolved)
            return httpx.Response(404)
        size = resolved.stat().st_size
        if size > _FILE_TRANSPORT_MAX_READ_BYTES:
            _log.warning(
                "file:// fetch refused (%d bytes exceeds cap %d): %s",
                size,
                _FILE_TRANSPORT_MAX_READ_BYTES,
                resolved,
            )
            return httpx.Response(413)
        return httpx.Response(200, content=resolved.read_bytes())


def _registry_client(registry: Registry) -> RegistryClient:
    """Build a `RegistryClient` for `registry` using the real transport.

    `httpx.Client` handles `http(s)://`; `_FileTransport` is mounted for
    `file://` so a local/offline source needs no network at all, confined
    to `registry`'s own index/archive directories (M1). Kept separate
    from `RegistryClient` itself so tests keep injecting their own
    transport (per client.py's docstring) instead of going through this
    real-network path.
    """
    roots = tuple(
        Path(httpx.URL(url).path).parent
        for url in (registry.index_url, registry.archive_url)
        if url.startswith("file://")
    )
    http = httpx.Client(mounts={"file://": _FileTransport(roots)})
    return RegistryClient(registry, http)


def _project_root(path: str) -> Path:
    """The directory holding `magnetite.toml` for a dir-or-file `path`."""
    root = Path(path)
    return root.parent if root.is_file() else root


def _lockfile_pins(project_root: Path) -> Result[tuple[VendorPin, ...], str]:
    """Read `<project_root>/regolith.lock` and flatten every record pin.

    Each lockfile ``pin <package>@<version> = <revision hash>`` row
    (regolith/09 sec. 2-3: "package versions and record revision hashes for
    every registry record consumed") is exactly a `VendorPin` -- the
    revision hash IS the archive's content hash (INV-22). A missing
    lockfile or a pin row that is not `name@version` is a named failure.
    """
    lock_path = project_root / _LOCKFILE_FILENAME
    if not lock_path.is_file():
        return Err(f"no lockfile at {lock_path}")
    parsed = parse_lockfile(lock_path.read_text())
    if parsed.is_err:
        return Err(f"{lock_path}: {parsed.danger_err.message}")
    pins: list[VendorPin] = []
    for section in parsed.danger_ok.sections:
        for package_version, revision_hash in section.record_pins:
            if "@" not in package_version:
                return Err(
                    f"{lock_path}: malformed pin {package_version!r} "
                    "(expected name@version)"
                )
            name, version = package_version.rsplit("@", 1)
            pins.append(
                VendorPin(package=name, version=version, archive_hash=revision_hash)
            )
    return Ok(tuple(pins))


def _route_pins(
    manifest: Manifest, pins: tuple[VendorPin, ...]
) -> Result[dict[str, list[VendorPin]], str]:
    """Group `pins` by the registry name each package routes to (sec. 10.2)."""
    grouped: dict[str, list[VendorPin]] = {}
    for pin in pins:
        routed = manifest.sources.route(pin.package)
        if routed.is_err:
            return Err(routed.danger_err.message)
        grouped.setdefault(routed.danger_ok.name, []).append(pin)
    return Ok(grouped)


@app.callback()
def main() -> None:
    """Keep group behavior so subcommands work even when only one exists."""


@app.command()
def version() -> None:
    """Print the compiler core version (crosses the Rust boundary)."""
    typer.echo(core_version())


def _lints_for(files: list[str]) -> tuple[tuple[str, str], ...]:
    """Resolve `magnetite.toml [lints]` for `files`'s project root (WO-40
    deliverable 4). No manifest at the root is the documented pure-
    defaults path -- every lint stays at `Warning`, never an error."""
    project_root = discover_project_root(files[0] if files else ".")
    loaded = load_manifest(project_root)
    manifest = loaded.danger_ok if loaded.is_ok else None
    if loaded.is_err:
        _log.debug(
            "check: no manifest at %s (%s)", project_root, loaded.danger_err.kind
        )
    return resolve_lint_config(manifest)


def _run_check(files: list[str]) -> tuple[bool, str]:
    """Run one `check()` pass over `files`, resolving `[lints]` first.
    Returns `(ok, rendered)`; an internal error prints and exits inline
    (shared by `check` and `check --watch`)."""
    result = compiler.check(tuple(files), lints=_lints_for(files))
    if result.is_err:
        failure = result.danger_err
        _log.error("check: internal error: %s", failure.message)
        typer.echo(failure.message, err=True)
        raise typer.Exit(EXIT_INTERNAL_ERROR)
    outcome = result.danger_ok
    return outcome.ok, outcome.rendered


def _count_warnings(rendered: str) -> int:
    """The one warning-count rule (L3): every `warning[` line, shared by
    the single-shot clean-summary and `check --watch`'s summary line so
    the two never disagree over a non-L0 warning."""
    return rendered.count("warning[")


def _summary_line(rendered: str, ok: bool) -> str:
    """One summary line: lint/error counts (WO-40 deliverable 5)."""
    errors = rendered.count("error[")
    lints = _count_warnings(rendered)
    return f"check: ok={ok} errors={errors} lints={lints}"


@app.command()
def check(
    files: list[str] = typer.Argument(..., help="Source files or project roots."),
    explain: str | None = typer.Option(
        None, "--explain", help="Explain a diagnostic code."
    ),
    waive: list[str] = typer.Option([], "--waive", help="Waive a Group.claim."),
    target: str | None = typer.Option(None, "--target", help="Build target."),
    watch: bool = typer.Option(
        False, "--watch", help="Re-run on every save (WO-40 deliverable 5)."
    ),
) -> None:
    """Run L0-L3 static checks (geometry-free, simulation-free).

    THE first shippable artifact (hematite/06 Phase B). Prints the one
    renderer's output verbatim and exits CLEAN / DIAGNOSTICS / INTERNAL.
    `--watch` re-runs on every save instead of exiting once (D111: CLI
    and LSP see identical results by construction -- same pipeline,
    same renderer, just re-invoked).
    """
    if watch:
        run_check_watch(files)
        raise typer.Exit(EXIT_CLEAN)

    _log.info("check: %d file(s)", len(files))
    ok, rendered = _run_check(files)
    typer.echo(rendered)
    if ok:
        warnings = _count_warnings(rendered)
        if warnings > 0:
            _log.info("check: clean (%d warnings)", warnings)
            typer.echo(f"check: clean ({warnings} warnings)")
        else:
            _log.info("check: clean")
        raise typer.Exit(EXIT_CLEAN)
    _log.info("check: diagnostics reported")
    raise typer.Exit(EXIT_DIAGNOSTICS)


def run_check_watch(files: list[str]) -> None:
    """`regolith check --watch` (WO-40 deliverable 5): re-run `check()`
    on every save of a registry-extension source file or
    `magnetite.toml` under the watched roots, clear-screen, print the
    ONE renderer's output plus a summary line. Exits 0 on interrupt
    (Ctrl-C) -- a clean stop, not a crash.
    """
    import watchfiles

    watched_exts = {f".{ext}" for ext, _lang in compiler.extensions()}
    watched_exts.add(".toml")

    def _relevant(_change: object, path: str) -> bool:
        return Path(path).suffix in watched_exts

    roots = files or ["."]
    ok, rendered = _run_check(files)
    click.clear()
    typer.echo(rendered)
    typer.echo(_summary_line(rendered, ok))
    _log.info("check --watch: watching %s", roots)
    try:
        for _changes in watchfiles.watch(*roots, watch_filter=_relevant):
            ok, rendered = _run_check(files)
            click.clear()
            typer.echo(rendered)
            typer.echo(_summary_line(rendered, ok))
    except KeyboardInterrupt:
        _log.info("check --watch: interrupted, exiting clean")


@app.command()
def fmt(files: list[str] = typer.Argument(..., help="Source files to format.")) -> None:
    """Rewrite files in their canonical form (the WO-05 normalizer)."""
    for file in files:
        path = Path(file)
        try:
            text = path.read_text()
        except OSError as exc:
            _log.error("fmt: cannot read %s: %s", file, exc)
            typer.echo(f"cannot read {file}: {exc}", err=True)
            raise typer.Exit(EXIT_INTERNAL_ERROR) from exc
        formatted = compiler.format(text)
        try:
            path.write_text(formatted)
        except OSError as exc:
            _log.error("fmt: cannot write %s: %s", file, exc)
            typer.echo(f"cannot write {file}: {exc}", err=True)
            raise typer.Exit(EXIT_INTERNAL_ERROR) from exc
        _log.info("fmt: rewrote %s", file)
    raise typer.Exit(EXIT_CLEAN)


@app.command()
def debug(
    stage: str = typer.Argument(..., help="tokens | cst | ast | ir"),
    path: str = typer.Argument(..., help="Source file to dump."),
) -> None:
    """Dump an intermediate pipeline stage (AD-13 inspectability).

    ``ir`` runs the real ``check`` pipeline and additionally lists the
    realized-domain IRs supplied to the build (WO-42 deliverable 3,
    AD-25) -- always empty from this CLI entry point today (no flag
    yet resolves realized-IR digests against the WO-30 store; that is
    the staged-build-loop orchestrator's job, WO-42 deliverable 5).
    """
    if stage == "ir":
        result = compiler.debug_ir((path,))
    else:
        result = compiler.debug_dump(stage, path)
    if result.is_err:
        failure = result.danger_err
        _log.error("debug: internal error: %s", failure.message)
        typer.echo(failure.message, err=True)
        raise typer.Exit(EXIT_INTERNAL_ERROR)
    typer.echo(result.danger_ok)
    raise typer.Exit(EXIT_CLEAN)


_BUILD_REPORT_FILENAME = "build_report.json"
_LOCKFILE_FILENAME = "regolith.lock"


def _default_build_out(files: list[str]) -> str:
    """The default ``--out`` directory: ``<project_root>/.regolith/build``
    (regolith/09's build-dir convention -- the same project-local,
    gitignored ``.regolith/`` home the evidence cache, payload store,
    and native-artifact store already use, AD-10)."""
    project_root = discover_project_root(files[0] if files else ".")
    return str(Path(project_root) / ".regolith" / "build")


def _render_build_report(report: StagedBuildReport) -> str:
    """The human-default stdout form: the ONE renderer's text verbatim
    (AD-7, the ``check`` verb's own precedent) plus a one-line summary."""
    final = report.final
    lines = [final.rendered] if final.rendered else []
    lines.append(
        f"build: tier={final.tier.name.lower()} ok={final.ok} "
        f"release_ok={final.release_ok} obligations={len(final.results)} "
        f"discharged={final.obligations_discharged} "
        f"unresolved={len(final.unresolved)} iterations={report.iterations}"
    )
    return "\n".join(lines)


@app.command()
def build(
    files: list[str] = typer.Argument(..., help="Source files or project roots."),
    release: bool = typer.Option(
        False, "--release", help="Run the T3 release gate (INV-24)."
    ),
    tier: str = typer.Option(
        "build",
        "--tier",
        help=f"Build tier: one of {', '.join(sorted(TIER_BY_VERB))}.",
    ),
    out: str | None = typer.Option(
        None,
        "--out",
        help="Artifact directory (default <project_root>/.regolith/build).",
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Print the machine-readable build report to stdout."
    ),
    profile: str | None = typer.Option(
        None,
        "--profile",
        help="The cost profile this build estimates under "
        "([profiles.cost.<name>] in magnetite.toml; WO-54). Claims "
        "may still override per-claim with profile=; the manifest "
        "default applies when omitted.",
    ),
    spec: str | None = typer.Option(
        None,
        "--spec",
        help='JSON file whose "elec_boards" block '
        '("elec_boards": {"<subject>": {netlist_hash, '
        "board_outline_ref, request: {netlist_path, board_outline_path, "
        "output_pcb_path}}}) drives staged_build's elec leg (WO-42 "
        "deliverable 5); this is the SAME spec file format `ship --spec` "
        'takes, but `build` reads ONLY the "elec_boards" block from it '
        '-- any "mech"/"elec"/"drawings" block is ignored here.',
    ),
) -> None:
    """Run the staged build (lower -> realize -> re-lower to a fixed
    point, WO-42 deliverable 5) and write ``regolith.lock`` + a build
    report to ``--out DIR`` (WO-43).

    ``--release`` runs the WO-21/INV-24 release gate (T3); otherwise
    ``--tier`` picks the ladder rung directly (default ``build``, T1).
    ``regolith build --release && regolith ship --out DIR`` is the
    two-command corpus demo this verb exists to make possible (WO-25's
    first named blocker). ``--profile`` (WO-54) selects the build's
    cost profile; the profile pick and every consumed cost record land
    in the lockfile (INV-22).
    """
    tier_name = "release" if release else tier
    resolved_tier = TIER_BY_VERB.get(tier_name)
    if resolved_tier is None:
        _log.error("build: unknown tier %r", tier_name)
        typer.echo(
            f"unknown tier {tier_name!r} (want one of "
            f"{', '.join(sorted(TIER_BY_VERB))})",
            err=True,
        )
        raise typer.Exit(EXIT_INTERNAL_ERROR)

    elec_boards: dict[str, ElecBoardInputs] = {}
    if spec is not None:
        spec_data = json.loads(Path(spec).read_text())
        elec_boards = _elec_boards_from_spec(spec_data)

    _log.info(
        "build: %d file(s) tier=%s profile=%s elec_boards=%d",
        len(files),
        resolved_tier.name,
        profile,
        len(elec_boards),
    )
    result = staged_build(
        tuple(files), resolved_tier, cost_profile=profile, elec_boards=elec_boards
    )
    if result.is_err:
        failure = result.danger_err
        _log.error("build: internal error: %s", failure.message)
        typer.echo(failure.message, err=True)
        raise typer.Exit(EXIT_INTERNAL_ERROR)
    report = result.danger_ok

    out_dir = Path(out) if out is not None else Path(_default_build_out(files))
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        # WO-54: the profile pick is itself a lockfile row (charter sec.
        # 4's "--profile ... and the lockfile shows it"), and every
        # consumed cost record is a `pin` line (INV-22). WO-65 adds the
        # section-search winners' `cause: optimize(...)` rows and the
        # consumed std.civil frame-record pins, same grammar.
        lock_rows = (*report.lock_rows, *report.final.frame_lock_rows)
        if report.final.cost_profile is not None:
            cause = "cost_profile(cli)" if profile else "cost_profile(manifest_default)"
            lock_rows = (
                *lock_rows,
                LockRow(
                    slot="cost.profile",
                    value=report.final.cost_profile,
                    cause=cause,
                ),
            )
        lockfile = Lockfile(
            tool_version=core_version(),
            sections=(
                LockSection(
                    name="",
                    rows=lock_rows,
                    record_pins=tuple(
                        sorted(
                            (
                                *report.final.cost_record_pins,
                                *report.final.frame_record_pins,
                                *report.final.plan_record_pins,
                            )
                        )
                    ),
                ),
            )
            if lock_rows
            or report.final.cost_record_pins
            or report.final.frame_record_pins
            or report.final.plan_record_pins
            else (),
        )
        (out_dir / _LOCKFILE_FILENAME).write_text(render_lockfile(lockfile))
        (out_dir / _BUILD_REPORT_FILENAME).write_bytes(
            report.model_dump_json().encode("utf-8")
        )
    except OSError as exc:
        _log.error("build: cannot write artifacts to %s: %s", out_dir, exc)
        typer.echo(f"cannot write artifacts to {out_dir}: {exc}", err=True)
        raise typer.Exit(EXIT_INTERNAL_ERROR) from exc
    _log.info(
        "build: wrote %s + %s to %s",
        _LOCKFILE_FILENAME,
        _BUILD_REPORT_FILENAME,
        out_dir,
    )

    if json_output:
        typer.echo(report.model_dump_json())
    else:
        typer.echo(_render_build_report(report))

    if report.final.ok and report.final.release_ok:
        _log.info("build: clean")
        raise typer.Exit(EXIT_CLEAN)
    _log.info("build: refused/diagnostics reported")
    raise typer.Exit(EXIT_DIAGNOSTICS)


@app.command()
def optimize(
    project: str = typer.Argument(".", help="Project root (or a file inside it)."),
    spec: str = typer.Option(
        ...,
        "--spec",
        help="JSON file naming the discrete choice-point domains, closed-form "
        "costs, and any infeasible_prefixes -- see "
        "`regolith.orchestrator.optimize.discrete_domains_from_spec`'s "
        "docstring for the exact shape. A placeholder evaluator surface: "
        "WO-56 wires real objective extraction from lowered source without "
        "changing this command's flags.",
    ),
    budget_evals: int | None = typer.Option(
        None,
        "--budget-evals",
        help="MANDATORY evaluation budget (max evaluations). Charter sec. "
        "1.8: a budget is required at invocation; this refuses without one "
        "until a D164 config profile default lands.",
    ),
    budget_seconds: float | None = typer.Option(
        None,
        "--budget-seconds",
        help="An additional wall-clock budget (advisory alongside "
        "--budget-evals; not yet a hard stop -- WO-55 lands the "
        "evaluation-count budget only).",
    ),
    seed: int = typer.Option(0, "--seed", help="Deterministic search seed."),
    resume: str | None = typer.Option(
        None, "--resume", help="A prior trace's payload digest to resume from."
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Print the machine-readable OptimizationTrace to stdout."
    ),
) -> None:
    """Run the discrete conflict-driven search over a declared domain (T2
    tier; `check`/`build` never search, charter sec. 1.5).

    Prints the resulting trace's summary (or the full trace with
    `--json`), writes it to the project's payload store, and appends a
    `cause: optimize(...)` lockfile row for the winner (INV-21). Budget
    exhaustion is reported honestly (`budget_exhausted`), never an
    exception; an infeasible domain reports `infeasible` with no pin.
    """
    if budget_evals is None:
        _log.error("optimize: refused, no budget given (charter sec. 1.8)")
        typer.echo(
            "a budget is mandatory: pass --budget-evals (see D164 for the "
            "future config-profile default)",
            err=True,
        )
        raise typer.Exit(EXIT_INTERNAL_ERROR)
    if budget_seconds is not None:
        _log.info(
            "optimize: --budget-seconds=%s recorded (advisory, WO-55 v1)",
            budget_seconds,
        )

    project_root = discover_project_root(project)
    store = PayloadStore(project_root)

    resume_trace = None
    if resume is not None:
        loaded = load_trace(store, resume)
        if loaded.is_err:
            _log.error("optimize --resume: %s", loaded.danger_err.message)
            typer.echo(loaded.danger_err.message, err=True)
            raise typer.Exit(EXIT_INTERNAL_ERROR)
        resume_trace = loaded.danger_ok

    spec_data = json.loads(Path(spec).read_text())
    domains, evaluator, screen, objective = discrete_domains_from_spec(spec_data)

    nogood_loaded = NogoodCache.load(project_root)
    if nogood_loaded.is_err:
        _log.error("optimize: %s", nogood_loaded.danger_err.message)
        typer.echo(nogood_loaded.danger_err.message, err=True)
        raise typer.Exit(EXIT_INTERNAL_ERROR)
    nogood_cache = nogood_loaded.danger_ok

    _log.info(
        "optimize: %d domain(s), budget_evals=%d, seed=%d, resume=%s",
        len(domains),
        budget_evals,
        seed,
        resume,
    )
    trace = optimize_discrete(
        domains,
        evaluator,
        objective,
        seed=seed,
        budget_evals=budget_evals,
        screen=screen,
        nogood_cache=nogood_cache,
        resume_trace=resume_trace,
    )
    digest = store_trace(store, trace)
    saved = nogood_cache.save(project_root)
    if saved.is_err:
        _log.warning(
            "optimize: could not persist nogood cache: %s", saved.danger_err.message
        )

    if json_output:
        typer.echo(trace.model_dump_json())
    else:
        typer.echo(
            f"optimize: strategy={trace.strategy_id} "
            f"termination={trace.termination.value} "
            f"evaluations={trace.budget_spent}/{trace.budget_declared} trace={digest}"
        )

    row_result = winner_lock_row(trace, "optimize.winner", "declared_objective", digest)
    if row_result.is_ok:
        lockfile = Lockfile(
            tool_version=core_version(),
            sections=(LockSection(name="", rows=(row_result.danger_ok,)),),
        )
        (Path(project_root) / _LOCKFILE_FILENAME).write_text(render_lockfile(lockfile))
        _log.info(
            "optimize: wrote %s with the optimize(...) cause row", _LOCKFILE_FILENAME
        )

    if trace.termination.value == "infeasible":
        _log.info("optimize: infeasible domain, no winner")
        raise typer.Exit(EXIT_DIAGNOSTICS)
    raise typer.Exit(EXIT_CLEAN)


@rules_app.command("test")
def rules_test(
    packs: list[str] = typer.Argument(
        ..., help="Rule-pack source files (process modules)."
    ),
) -> None:
    """Run every rule's `expect:` fixtures (the authoring loop's gate).

    A rule missing a pass or a fail case is a lint WARNING (untested
    law); a fixture behaving against its verdict FAILS the run.
    """
    _log.info("rules test: %d pack file(s)", len(packs))
    result = compiler.rules_test(tuple(packs))
    if result.is_err:
        failure = result.danger_err
        _log.error("rules test: internal error: %s", failure.message)
        typer.echo(failure.message, err=True)
        raise typer.Exit(EXIT_INTERNAL_ERROR)
    reports = result.danger_ok
    all_ok = True
    for report in reports:
        for case in report.cases:
            marker = "ok" if case.outcome == "ok" else f"FAIL ({case.outcome})"
            detail = f" -- {case.detail}" if case.detail else ""
            typer.echo(
                f"{marker:18} {case.rule} {case.expected}: {case.fixture}{detail}"
            )
        for lint in report.lints:
            typer.echo(f"{'warning':18} {lint}")
        all_ok = all_ok and report.ok
    if not reports:
        typer.echo("no rule packs found in the given files", err=True)
        raise typer.Exit(EXIT_DIAGNOSTICS)
    raise typer.Exit(EXIT_CLEAN if all_ok else EXIT_DIAGNOSTICS)


@rules_app.command("try")
def rules_try(
    pack: str = typer.Argument(..., help="The rule-pack source file."),
    design: str = typer.Argument(..., help="The design file to try it against."),
) -> None:
    """Run ONE pack against one design: matches, verdicts, near misses.

    Attachment is forced and nothing is built -- the projector-friendly
    feedback loop for a working session.
    """
    _log.info("rules try: pack=%s design=%s", pack, design)
    result = compiler.rules_try(pack, design)
    if result.is_err:
        failure = result.danger_err
        _log.error("rules try: internal error: %s", failure.message)
        typer.echo(failure.message, err=True)
        raise typer.Exit(EXIT_INTERNAL_ERROR)
    report = result.danger_ok
    violated = False
    if not report.matches:
        typer.echo("no matches (the pack's domains matched no entities)")
    for m in report.matches:
        near = "  (near miss)" if m.near_miss else ""
        margin = f"  margin={m.margin:.1%}" if m.margin is not None else ""
        typer.echo(
            f"{m.verdict:10} {m.rule} on {m.subject}.{m.entity}: "
            f"{m.detail}{margin}{near}"
        )
        violated = violated or m.verdict == "violated"
    raise typer.Exit(EXIT_DIAGNOSTICS if violated else EXIT_CLEAN)


@app.command("test")
def test_cmd(
    paths: list[str] = typer.Argument(
        ..., help="Source files or project roots to discover `.test.<ext>` files under."
    ),
    keyword: str | None = typer.Option(
        None, "-k", help="Only run tests whose declared name contains this substring."
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Print a machine-readable JSON summary instead of text."
    ),
) -> None:
    """Run every `test <name>:` declaration under `paths` (charter
    toolchain/37, WO-83 slice B) plus every discovered rule-pack
    `expect:` fixture (WO-28 unification, one summary, one command).

    Each scenario runs through the ordinary build door (AD-22 -- no
    private pipeline) and is cached by content address (unchanged
    scenario + unchanged design = cache hit). Cargo-style one line per
    test; a failure's detail lines render expected-vs-actual.
    """
    root_paths = tuple(paths)
    _log.info("test: discovering under %d root(s)", len(root_paths))
    results = run_tests(root_paths, name_filter=keyword)

    rule_packs = discover_rule_pack_files(root_paths)
    rules_ok = True
    rule_lines: list[str] = []
    rule_json: list[dict[str, object]] = []
    if rule_packs:
        rules_result = compiler.rules_test(rule_packs)
        if rules_result.is_err:
            _log.error(
                "test: rule-pack unification internal error: %s",
                rules_result.danger_err.message,
            )
            typer.echo(rules_result.danger_err.message, err=True)
            raise typer.Exit(EXIT_INTERNAL_ERROR)
        for report in rules_result.danger_ok:
            for case in report.cases:
                case_ok = case.outcome == "ok"
                marker = "ok" if case_ok else f"FAIL ({case.outcome})"
                rule_lines.append(
                    f"test {report.pack}::{case.rule}:{case.fixture} ... {marker}"
                )
                rule_json.append(
                    {
                        "pack": report.pack,
                        "rule": case.rule,
                        "fixture": case.fixture,
                        "ok": case_ok,
                        "detail": case.detail,
                    }
                )
                rules_ok = rules_ok and case_ok
            rules_ok = rules_ok and report.ok

    if json_output:
        payload = {
            "tests": [
                {
                    "test_file": str(r.test_file),
                    "name": r.name,
                    "ok": r.ok,
                    "from_cache": r.from_cache,
                    "details": list(r.details),
                    "error": r.error,
                }
                for r in results
            ],
            "rule_packs": rule_json,
            "ok": all(r.ok for r in results) and rules_ok,
        }
        typer.echo(json.dumps(payload))
        raise typer.Exit(EXIT_CLEAN if bool(payload["ok"]) else EXIT_DIAGNOSTICS)

    text, tests_ok = render_summary(results)
    typer.echo(text)
    for line in rule_lines:
        typer.echo(line)
    if rule_lines:
        typer.echo(f"rule-pack fixtures: {'ok' if rules_ok else 'FAILED'}")
    _log.info(
        "test: %d test(s), %d rule-pack fixture(s)", len(results), len(rule_lines)
    )
    raise typer.Exit(EXIT_CLEAN if (tests_ok and rules_ok) else EXIT_DIAGNOSTICS)


@app.command()
def doc(
    paths: list[str] = typer.Argument(..., help="Source files or project roots."),
    out: str | None = typer.Option(
        None, "--out", help="Write markdown here instead of stdout."
    ),
) -> None:
    """Render a package's public surface to deterministic markdown (WO-41).

    Interfaces, parts/blocks/flownets/media, claims (with build status
    when ``.regolith/`` artifacts exist, else ``(unbuilt)`` -- never an
    error), and budgets. Doc text is each declaration's leading ``#``
    comment block (no new syntax, D115).
    """
    files = tuple(paths)
    _log.info("doc: %d root(s)", len(files))
    extracted = extract_package(files)
    if extracted.is_err:
        failure = extracted.danger_err
        _log.error("doc: extraction failed: %s", failure.message)
        typer.echo(failure.message, err=True)
        raise typer.Exit(EXIT_INTERNAL_ERROR)
    package = extracted.danger_ok

    # Claim status reads whichever root's `.regolith/` cache exists;
    # the first root is the project's own convention elsewhere (`check`,
    # `build`) so `doc` follows it too.
    project_root = files[0] if files else "."
    statuses = claim_statuses(project_root, files)

    rendered = render_markdown(package, statuses=statuses)
    if out is None:
        typer.echo(rendered)
        raise typer.Exit(EXIT_CLEAN)

    out_path = Path(out)
    try:
        out_path.mkdir(parents=True, exist_ok=True)
        (out_path / "index.md").write_text(rendered)
    except OSError as exc:
        _log.error("doc: cannot write %s: %s", out, exc)
        typer.echo(f"cannot write {out}: {exc}", err=True)
        raise typer.Exit(EXIT_INTERNAL_ERROR) from exc
    _log.info("doc: wrote %s/index.md", out)
    raise typer.Exit(EXIT_CLEAN)


def _rows(block: object, key: str) -> list[object]:
    """The list under ``block[key]``, or ``[]`` if ``block``/its value isn't shaped."""
    if not isinstance(block, dict):
        return []
    raw = cast("dict[object, object]", block).get(key, [])
    if not isinstance(raw, list):
        return []
    return cast("list[object]", raw)


def _mech_backend_from_spec(spec: dict[str, object]) -> Backend | None:
    """Build a :class:`MechBackend` from the ``"mech"`` block of a ship spec."""
    block = spec.get("mech")
    if not isinstance(block, dict):
        return None
    assembly = tuple(
        MechAssemblyLine.model_validate(row) for row in _rows(block, "assembly")
    )
    fab_notes = tuple(
        FabNoteSpec.model_validate(row) for row in _rows(block, "fab_notes")
    )
    return MechBackend(assembly, fab_notes)


def _elec_backend_from_spec(spec: dict[str, object]) -> Backend | None:
    """Build an :class:`ElecBackend` from the ``"elec"`` block of a ship spec."""
    block = spec.get("elec")
    if not isinstance(block, dict):
        return None
    subject = block.get("subject")
    if not isinstance(subject, str):
        return None
    assembly = tuple(
        ElecAssemblyLine.model_validate(row) for row in _rows(block, "assembly")
    )
    return ElecBackend(subject, assembly)


def _drawings_backend_from_spec(spec: dict[str, object]) -> Backend | None:
    """Build a :class:`DrawingsBackend` from the ``"drawings"`` block of a
    ship spec: a list of ``{"subject": str, "track":
    "mech"|"fluid"|"civil"|"elec_blocks"}`` rows, mirroring
    :func:`_mech_backend_from_spec`'s shape exactly."""
    raw = spec.get("drawings")
    if not isinstance(raw, list):
        return None
    specs = tuple(DrawingSpec.model_validate(row) for row in cast("list[object]", raw))
    return DrawingsBackend(specs)


def _elec_boards_from_spec(spec: dict[str, object]) -> dict[str, ElecBoardInputs]:
    """Parse the ``"elec_boards"`` block: ``{"<subject>": {netlist_hash,
    board_outline_ref, request: {netlist_path, board_outline_path,
    output_pcb_path}}}`` into :class:`ElecBoardInputs` this build's
    `staged_build(..., elec_boards=...)` needs (orchestrate.py); ``{}``
    when the block is absent (build behavior is unchanged)."""
    block = spec.get("elec_boards")
    if not isinstance(block, dict):
        return {}
    boards: dict[str, ElecBoardInputs] = {}
    for subject, row in cast("dict[str, object]", block).items():
        boards[subject] = ElecBoardInputs.model_validate(row)
    return boards


@app.command()
def ship(
    files: list[str] = typer.Argument(..., help="Source files or project roots."),
    out: str = typer.Option("ship", "--out", help="Package output directory."),
    spec: str | None = typer.Option(
        None,
        "--spec",
        help="JSON file naming the mech/elec BOM+fab-note assembly, the "
        'drawings set ("drawings": [{"subject":..., "track": '
        '"mech"|"fluid"|"civil"|"elec_blocks"}]), and elec_boards '
        '("elec_boards": {"<subject>": {netlist_hash, '
        "board_outline_ref, request: {netlist_path, board_outline_path, "
        "output_pcb_path}}}) -- already-decided data this backend only "
        'serializes, regolith/07 sec. 6; "elec_boards" only takes '
        "effect when --build is NOT given (it re-runs staged_build with "
        "those boards; --build consumes an already-realized report, so "
        "its elec_boards come from whatever `build --spec` realized). "
        "Omit to ship the manifest-only release attestation with no "
        "packages.",
    ),
    key: str | None = typer.Option(
        None, "--key", help="Local signing key id to sign the manifest with."
    ),
    verify: str | None = typer.Option(
        None,
        "--verify",
        help="Re-hash and verify an existing ship package directory instead "
        "of producing a new one (pass the package DIR here; FILES/--out "
        "are ignored).",
    ),
    trust_keys: str | None = typer.Option(
        None,
        "--trust-keys",
        help="JSON file holding a serialized TrustKeySet, required with --verify.",
    ),
    build_dir: str | None = typer.Option(
        None,
        "--build",
        help="Consume a prior `regolith build --release` output directory "
        "(regolith.lock + build_report.json) instead of re-running the "
        "staged build (WO-43 deliverable 3).",
    ),
    explain: bool = typer.Option(
        False,
        "--explain",
        help="Render the parity ledger (WO-63/AD-33) instead of shipping: "
        "per-subject provenance class counts, the decision/demand "
        "tables, assumed/waived entries, the attention-list caveat, "
        "and the `parity: clean|attention(n)|failing(n)` gate summary "
        "line. Reuses --build/lockfile resolution exactly like a "
        "normal ship; never writes a package.",
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="With --explain, emit the parity report as structured JSON "
        "instead of the ASCII tables.",
    ),
) -> None:
    """``build --release`` totality (INV-24) + a signed manufacturing package.

    Refuses (named diagnostic, nonzero exit) unless every obligation is
    discharged and every trust floor is met -- WO-25's own release gate,
    same machinery `regolith.orchestrator.orchestrate.release_gate`
    already enforces. Backends never decide (regolith/07 sec. 6): the
    mech/elec BOM and fab-note content comes from ``--spec`` verbatim.
    """
    if verify is not None:
        if trust_keys is None:
            typer.echo("--verify requires --trust-keys", err=True)
            raise typer.Exit(EXIT_INTERNAL_ERROR)
        keys = TrustKeySet.model_validate_json(Path(trust_keys).read_text())
        result = run_verify(verify, keys)
        if result.is_err:
            _log.error("ship --verify: %s", result.danger_err.message)
            typer.echo(result.danger_err.message, err=True)
            raise typer.Exit(EXIT_DIAGNOSTICS)
        typer.echo(f"{verify}: OK")
        raise typer.Exit(EXIT_CLEAN)

    prebuilt: StagedBuildReport | None = None
    if build_dir is not None:
        prebuilt_dir = Path(build_dir)
        try:
            lockfile_text = (prebuilt_dir / _LOCKFILE_FILENAME).read_text()
            report_text = (prebuilt_dir / _BUILD_REPORT_FILENAME).read_text()
        except OSError as exc:
            _log.error("ship --build: cannot read %s: %s", prebuilt_dir, exc)
            typer.echo(f"cannot read {prebuilt_dir}: {exc}", err=True)
            raise typer.Exit(EXIT_INTERNAL_ERROR) from exc
        lockfile_result = parse_lockfile(lockfile_text)
        if lockfile_result.is_err:
            _log.error(
                "ship --build: cannot parse lockfile: %s",
                lockfile_result.danger_err.message,
            )
            typer.echo(lockfile_result.danger_err.message, err=True)
            raise typer.Exit(EXIT_INTERNAL_ERROR)
        lockfile: Lockfile = lockfile_result.danger_ok
        prebuilt = StagedBuildReport.model_validate_json(report_text)
    else:
        project_root = files[0] if files else "."
        cwd_lockfile_path = Path(project_root) / "regolith.lock"
        if Path(project_root).is_file():
            cwd_lockfile_path = Path(project_root).parent / "regolith.lock"
        default_build_lockfile_path = (
            Path(_default_build_out(files)) / _LOCKFILE_FILENAME
        )

        # No explicit --build: try the plain CWD-relative path first
        # (back-compat with a lockfile the user placed by hand), then
        # fall back to `build`'s own default output directory (WO-43's
        # "regolith build --release && regolith ship" two-command demo
        # only works if ship finds what build actually wrote).
        if cwd_lockfile_path.is_file():
            lockfile_path = cwd_lockfile_path
        elif default_build_lockfile_path.is_file():
            lockfile_path = default_build_lockfile_path
        else:
            _log.error(
                "ship: no lockfile at %s or %s",
                cwd_lockfile_path,
                default_build_lockfile_path,
            )
            typer.echo(
                f"cannot find a lockfile at {cwd_lockfile_path} or "
                f"{default_build_lockfile_path}; run `regolith build --release` "
                "first (or pass --build DIR)",
                err=True,
            )
            raise typer.Exit(EXIT_DIAGNOSTICS)
        try:
            lockfile_text = lockfile_path.read_text()
        except OSError as exc:
            _log.error("ship: cannot read %s: %s", lockfile_path, exc)
            typer.echo(f"cannot read {lockfile_path}: {exc}", err=True)
            raise typer.Exit(EXIT_DIAGNOSTICS) from exc
        lockfile_result = parse_lockfile(lockfile_text)
        if lockfile_result.is_err:
            _log.error(
                "ship: cannot parse lockfile: %s", lockfile_result.danger_err.message
            )
            typer.echo(lockfile_result.danger_err.message, err=True)
            raise typer.Exit(EXIT_DIAGNOSTICS)
        lockfile = lockfile_result.danger_ok

    if explain:
        # WO-63/AD-33: `--explain` is a report-only mode, exactly like
        # `--verify` above short-circuits before any package is
        # written. `prebuilt` is already a `StagedBuildReport` when
        # `--build DIR` named a prior `regolith build --release` run;
        # otherwise run the SAME `staged_build` a normal ship would run
        # (RELEASE tier) purely to read its `.final.results`/`.ledger`
        # -- no package is produced either way.
        explain_report: StagedBuildReport
        if prebuilt is not None:
            explain_report = prebuilt
        else:
            gate = staged_build(tuple(files), BuildTier.RELEASE)
            if gate.is_err:
                _log.error("ship --explain: %s", gate.danger_err.message)
                typer.echo(gate.danger_err.message, err=True)
                raise typer.Exit(EXIT_DIAGNOSTICS)
            explain_report = gate.danger_ok
        final_payload = (
            json.loads(explain_report.final.payload_json)
            if explain_report.final.payload_json
            else {}
        )
        ledger_raw = final_payload.get("ledger", {"entries": []})
        ledger = WaiveLedger.model_validate(ledger_raw)
        results = tuple(explain_report.final.results) + tuple(
            explain_report.final.unresolved
        )
        parity = build_parity_report(lockfile, results, ledger)
        if as_json:
            typer.echo(parity.model_dump_json())
        else:
            typer.echo(render_parity_report(parity), nl=False)
        if gate_summary_line(parity).startswith("parity: failing"):
            raise typer.Exit(EXIT_DIAGNOSTICS)
        raise typer.Exit(EXIT_CLEAN)

    project_root = files[0] if files else "."
    artifact_root = (
        str(Path(project_root).parent) if Path(project_root).is_file() else project_root
    )

    builtin_backends: dict[str, Backend] = {}
    elec_boards: dict[str, ElecBoardInputs] = {}
    native: NativeArtifactStore | None = None
    if spec is not None:
        spec_data = json.loads(Path(spec).read_text())
        mech = _mech_backend_from_spec(spec_data)
        if mech is not None:
            builtin_backends["mech"] = mech
        elec = _elec_backend_from_spec(spec_data)
        if elec is not None:
            builtin_backends["elec"] = elec
        drawings = _drawings_backend_from_spec(spec_data)
        if drawings is not None:
            builtin_backends["drawings"] = drawings
        elec_boards = _elec_boards_from_spec(spec_data)

        # `staged_build` (whether run fresh below or already run and
        # read back via `--build`) pins a `layout.realized` row per
        # elec board, but never touches `NativeArtifactStore` (WO-24's
        # own close-out gap: the real-kicad wrapper writes the
        # `.kicad_pcb` to `request.output_pcb_path` on disk, it does not
        # content-address it). `ship`'s `ElecBackend` reads the pcb
        # bytes back through `BackendInputs.native` by content hash
        # (mirrors `RealizedGeometry.step_content_hash`'s own pattern),
        # so the CLI must prime the store from the request path -- same
        # round trip `tests/orchestrator/test_staged_build_elec_kicad.py`
        # does by hand -- before `ElecBackend.produce` runs. Only
        # possible with `--build` (a `prebuilt` report already carries
        # `realized_inputs`); the fresh-build path's layout is realized
        # INSIDE `run_ship`'s own `staged_build` call, after this point,
        # so there is nothing yet to prime here for it.
        if prebuilt is not None and elec_boards:
            layouts_by_subject = {
                ri.subject: RealizedLayout.model_validate_json(ri.payload_bytes)
                for ri in prebuilt.realized_inputs
                if ri.kind == "layout.realized"
            }
            store = NativeArtifactStore(artifact_root)
            for subject, board in elec_boards.items():
                layout = layouts_by_subject.get(subject)
                pcb_path = Path(board.request.output_pcb_path)
                if layout is None or not pcb_path.is_file():
                    _log.warning(
                        "ship: no realized layout/pcb file for elec board %s "
                        "(--build report or %s); NativeArtifactStore not primed",
                        subject,
                        pcb_path,
                    )
                    continue
                verify_result = store.put_verified(
                    layout.kicad_pcb_content_hash, pcb_path.read_bytes()
                )
                if verify_result.is_err:
                    typer.echo(verify_result.danger_err.message, err=True)
                    raise typer.Exit(EXIT_DIAGNOSTICS)
            native = store

    # WO-44/AD-26: third-party manufacturing backends compose alongside
    # the two built-ins through the one plugin seam (kind=backend). A
    # bad plugin is a named, logged warning -- never a crashed `ship`.
    backend_outcome = load_backend_plugins(builtin_backends)
    for error in backend_outcome.errors:
        _log.warning("ship: backend plugin skipped: %r", error)
    backends = backend_outcome.backends

    signer = None
    if key is not None:
        key_result = load_signing_key(project_root, key)
        if key_result.is_err:
            typer.echo(key_result.danger_err.message, err=True)
            raise typer.Exit(EXIT_INTERNAL_ERROR)
        signer = key_result.danger_ok

    shipped = run_ship(
        tuple(files),
        backends,
        out,
        lockfile=lockfile,
        signer=signer,
        prebuilt=prebuilt,
        elec_boards=elec_boards,
        native=native if native is not None else NativeArtifactStore(artifact_root),
    )
    if shipped.is_err:
        _log.error("ship: %s", shipped.danger_err.message)
        typer.echo(shipped.danger_err.message, err=True)
        raise typer.Exit(EXIT_DIAGNOSTICS)
    manifest = shipped.danger_ok
    typer.echo(f"shipped {len(manifest.files)} file(s) to {out}")
    raise typer.Exit(EXIT_CLEAN)


@plugin_app.command("list")
def plugin_list(
    as_json: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
) -> None:
    """List every discovered plugin: id, kind, version, source distribution.

    stdout is data (AD-26): one line per plugin (or a JSON array with
    ``--json``), sorted by kind then id. The ``rule_pack`` kind is
    RESERVED (WO-28) and always composes empty.
    """
    rows: list[dict[str, str | None]] = []
    for kind in PluginKind:
        outcome = discover_plugins(kind)
        for manifest in outcome.manifests:
            rows.append(
                {
                    "id": manifest.id,
                    "kind": kind.value,
                    "version": manifest.version,
                    "source": outcome.sources.get(manifest.id),
                }
            )
    if as_json:
        typer.echo(json.dumps(rows))
        raise typer.Exit(EXIT_CLEAN)
    if not rows:
        typer.echo("no plugins discovered")
        raise typer.Exit(EXIT_CLEAN)
    for row in rows:
        source = row["source"] or "unknown"
        typer.echo(f"{row['id']}\t{row['kind']}\t{row['version']}\t{source}")
    raise typer.Exit(EXIT_CLEAN)


def new(
    name: str = typer.Argument(..., help="Project (and directory) name."),
    template: str = typer.Option(
        "mech",
        "--template",
        help=f"Project template: one of {', '.join(VALID_TEMPLATES)}.",
    ),
) -> None:
    """Scaffold a working project that passes ``regolith check`` (WO-41).

    Emits ``magnetite.toml``, one source file per track (each with an
    honest example claim), a house ``.gitignore``, and a CI snippet.
    Refuses to overwrite a non-empty directory.
    """
    _log.info("magnetite new: %s (template=%s)", name, template)
    result = scaffold_project(name, template)
    if result.is_err:
        failure = result.danger_err
        _log.error("magnetite new: %s", failure.message)
        typer.echo(failure.message, err=True)
        raise typer.Exit(EXIT_INTERNAL_ERROR)
    typer.echo(f"scaffolded {result.danger_ok} from template '{template}'")
    raise typer.Exit(EXIT_CLEAN)


# One implementation, two typer bindings (`regolith new` is an alias for
# `regolith magnetite new`) -- never duplicate the scaffold-invocation
# logic between the two entry points.
magnetite_app.command("new")(new)
app.command("new", help="Alias for `regolith magnetite new` (same command).")(new)


@key_app.command("new")
def key_new(
    id: str = typer.Option(..., "--id", help="The signing key's id."),
    dir: str = typer.Option(
        ".", "--dir", help="Project root the key is stored under (.regolith/keys/)."
    ),
) -> None:
    """Generate a fresh local ed25519 signing key for `ship --key` to use.

    Writes an unencrypted PKCS8 PEM under ``<dir>/.regolith/keys/<id>.pem``
    (gitignored, never printed). NEVER prints private key material.
    """
    _log.info("key new: id=%s dir=%s", id, dir)
    result = generate_signing_key(dir, id)
    if result.is_err:
        failure = result.danger_err
        _log.error("key new: %s", failure.message)
        typer.echo(failure.message, err=True)
        raise typer.Exit(EXIT_INTERNAL_ERROR)
    typer.echo(f"generated signing key {id!r} at {keys_dir(dir) / f'{id}.pem'}")
    raise typer.Exit(EXIT_CLEAN)


@key_app.command("list")
def key_list(
    dir: str = typer.Option(
        ".", "--dir", help="Project root the keys are stored under (.regolith/keys/)."
    ),
) -> None:
    """List the local signing key ids under `<dir>/.regolith/keys/`."""
    directory = keys_dir(dir)
    if not directory.is_dir():
        _log.info("key list: no keys directory at %s", directory)
        typer.echo("no local signing keys")
        raise typer.Exit(EXIT_CLEAN)
    ids = sorted(p.stem for p in directory.glob("*.pem"))
    _log.info("key list: %d key(s) under %s", len(ids), directory)
    if not ids:
        typer.echo("no local signing keys")
        raise typer.Exit(EXIT_CLEAN)
    for key_id in ids:
        typer.echo(key_id)
    raise typer.Exit(EXIT_CLEAN)


@key_app.command("show")
def key_show(
    id: str = typer.Argument(..., help="The signing key's id."),
    dir: str = typer.Option(
        ".", "--dir", help="Project root the key is stored under (.regolith/keys/)."
    ),
) -> None:
    """Print a local signing key's PUBLIC half only (base64 ed25519 bytes).

    NEVER prints private key material -- only what `TrustKeySet`
    designations need.
    """
    _log.info("key show: id=%s dir=%s", id, dir)
    result = load_signing_key(dir, id)
    if result.is_err:
        failure = result.danger_err
        _log.error("key show: %s", failure.message)
        typer.echo(failure.message, err=True)
        raise typer.Exit(EXIT_INTERNAL_ERROR)
    key = result.danger_ok
    typer.echo(f"{key.key_id} {key.public_key_base64()}")
    raise typer.Exit(EXIT_CLEAN)


@index_app.command("show")
def index_show(
    path: str = typer.Argument(..., help="A local sparse-index NDJSON file."),
) -> None:
    """Parse and list every entry of a local sparse-index file.

    One line per entry: name, version, archive hash, yanked flag, and
    any advisory (regolith/11 sec. 10.1).
    """
    _log.info("index show: %s", path)
    try:
        text = Path(path).read_text()
    except OSError as exc:
        _log.error("index show: cannot read %s: %s", path, exc)
        typer.echo(f"cannot read {path}: {exc}", err=True)
        raise typer.Exit(EXIT_INTERNAL_ERROR) from exc
    result = parse_index(text)
    if result.is_err:
        failure = result.danger_err
        _log.error("index show: %s", failure.message)
        typer.echo(failure.message, err=True)
        raise typer.Exit(EXIT_INTERNAL_ERROR)
    entries = result.danger_ok
    if not entries:
        typer.echo("no entries")
        raise typer.Exit(EXIT_CLEAN)
    for entry in entries:
        yanked = " YANKED" if entry.yanked else ""
        advisory = f" advisory={entry.advisory}" if entry.advisory else ""
        typer.echo(
            f"{entry.name}\t{entry.version}\t{entry.archive_hash}{yanked}{advisory}"
        )
    raise typer.Exit(EXIT_CLEAN)


@index_app.command("select")
def index_select(
    path: str = typer.Argument(..., help="A local sparse-index NDJSON file."),
    version: str = typer.Argument(..., help="The exact version to select."),
) -> None:
    """Select one exact version from a local sparse-index file (sec. 10.5).

    Selecting a yanked version still succeeds (exact pins always
    resolve); the output flags it.
    """
    _log.info("index select: %s @ %s", path, version)
    try:
        text = Path(path).read_text()
    except OSError as exc:
        _log.error("index select: cannot read %s: %s", path, exc)
        typer.echo(f"cannot read {path}: {exc}", err=True)
        raise typer.Exit(EXIT_INTERNAL_ERROR) from exc
    parsed = parse_index(text)
    if parsed.is_err:
        typer.echo(parsed.danger_err.message, err=True)
        raise typer.Exit(EXIT_INTERNAL_ERROR)
    result = select_version(parsed.danger_ok, version)
    if result.is_err:
        failure = result.danger_err
        _log.error("index select: %s", failure.message)
        typer.echo(failure.message, err=True)
        raise typer.Exit(EXIT_DIAGNOSTICS)
    entry = result.danger_ok
    yanked = " YANKED" if entry.yanked else ""
    typer.echo(f"{entry.name}\t{entry.version}\t{entry.archive_hash}{yanked}")
    raise typer.Exit(EXIT_CLEAN)


@index_app.command("latest")
def index_latest(
    path: str = typer.Argument(..., help="A local sparse-index NDJSON file."),
) -> None:
    """Select the newest non-yanked version from a local sparse-index file."""
    _log.info("index latest: %s", path)
    try:
        text = Path(path).read_text()
    except OSError as exc:
        _log.error("index latest: cannot read %s: %s", path, exc)
        typer.echo(f"cannot read {path}: {exc}", err=True)
        raise typer.Exit(EXIT_INTERNAL_ERROR) from exc
    parsed = parse_index(text)
    if parsed.is_err:
        typer.echo(parsed.danger_err.message, err=True)
        raise typer.Exit(EXIT_INTERNAL_ERROR)
    result = latest_version(parsed.danger_ok)
    if result.is_err:
        failure = result.danger_err
        _log.error("index latest: %s", failure.message)
        typer.echo(failure.message, err=True)
        raise typer.Exit(EXIT_DIAGNOSTICS)
    entry = result.danger_ok
    typer.echo(f"{entry.name}\t{entry.version}\t{entry.archive_hash}")
    raise typer.Exit(EXIT_CLEAN)


@manifest_app.command("check")
def manifest_check(
    path: str = typer.Argument(".", help="A magnetite.toml file or its directory."),
) -> None:
    """Parse and validate a magnetite.toml manifest (wraps `load_manifest`).

    Prints the package identity and provides/depends counts on success;
    a malformed or missing manifest is a named diagnostic, nonzero exit.
    """
    _log.info("manifest check: %s", path)
    result = load_manifest(path)
    if result.is_err:
        failure = result.danger_err
        _log.error("manifest check: %s", failure.message)
        typer.echo(failure.message, err=True)
        raise typer.Exit(EXIT_DIAGNOSTICS)
    manifest = result.danger_ok
    typer.echo(
        f"{manifest.name} {manifest.version}: "
        f"kinds={list(manifest.kinds)} "
        f"provides={len(manifest.provides)} "
        f"depends={len(manifest.depends)}"
    )
    raise typer.Exit(EXIT_CLEAN)


def vendor(
    path: str = typer.Argument(".", help="A magnetite.toml file or its directory."),
) -> None:
    """Vendor every lockfile-pinned archive into `<root>/vendor/` (regolith/11
    sec. 10.3; wraps `regolith.magnetite.vendor.vendor`).

    Routes each `regolith.lock` pin through the manifest's `[sources]`
    (sec. 10.2) and fetches+verifies (INV-22) each archive with a real
    `RegistryClient`. A missing manifest/lockfile, an unroutable package,
    or any single fetch/verify failure fails the whole pass loudly --
    an offline build must not start from a partial store.
    """
    _log.info("magnetite vendor: %s", path)
    manifest_result = load_manifest(path)
    if manifest_result.is_err:
        failure = manifest_result.danger_err
        _log.error("magnetite vendor: %s", failure.message)
        typer.echo(failure.message, err=True)
        raise typer.Exit(EXIT_DIAGNOSTICS)
    manifest = manifest_result.danger_ok
    project_root = _project_root(path)

    pins_result = _lockfile_pins(project_root)
    if pins_result.is_err:
        _log.error("magnetite vendor: %s", pins_result.danger_err)
        typer.echo(pins_result.danger_err, err=True)
        raise typer.Exit(EXIT_DIAGNOSTICS)
    pins = pins_result.danger_ok
    if not pins:
        typer.echo("no pins to vendor")
        raise typer.Exit(EXIT_CLEAN)

    grouped_result = _route_pins(manifest, pins)
    if grouped_result.is_err:
        _log.error("magnetite vendor: %s", grouped_result.danger_err)
        typer.echo(grouped_result.danger_err, err=True)
        raise typer.Exit(EXIT_DIAGNOSTICS)

    vendored = 0
    for registry_name, group in grouped_result.danger_ok.items():
        registry = next(
            r for r in manifest.sources.registries if r.name == registry_name
        )
        client = _registry_client(registry)
        result = vendor_pins(
            tuple(group), client=client, project_root=str(project_root)
        )
        if result.is_err:
            failure = result.danger_err
            _log.error("magnetite vendor: %s", failure.message)
            typer.echo(failure.message, err=True)
            raise typer.Exit(EXIT_DIAGNOSTICS)
        vendored += len(group)

    typer.echo(f"vendored {vendored} archive(s) into {project_root / 'vendor'}")
    raise typer.Exit(EXIT_CLEAN)


magnetite_app.command("vendor")(vendor)
app.command("vendor", help="Alias for `regolith magnetite vendor` (same command).")(
    vendor
)


@magnetite_app.command("fetch")
def fetch(
    package: str = typer.Argument(..., help="Package name, routed via [sources]."),
    version: str = typer.Argument(..., help="Exact version to fetch."),
    path: str = typer.Option(
        ".", "--path", help="A magnetite.toml file or its directory."
    ),
) -> None:
    """Fetch and verify one pinned `(package, version)` archive (sec. 10.1;
    wraps `RegistryClient.fetch_pinned`).

    Prints the resolved manifest digest, archive hash, and byte count on
    success; does not write anything to disk (that is `vendor`'s job).
    A yanked version still fetches by exact pin (sec. 10.5) -- the output
    flags it.
    """
    _log.info("magnetite fetch: %s@%s (path=%s)", package, version, path)
    manifest_result = load_manifest(path)
    if manifest_result.is_err:
        failure = manifest_result.danger_err
        _log.error("magnetite fetch: %s", failure.message)
        typer.echo(failure.message, err=True)
        raise typer.Exit(EXIT_DIAGNOSTICS)
    manifest = manifest_result.danger_ok

    routed = manifest.sources.route(package)
    if routed.is_err:
        failure = routed.danger_err
        _log.error("magnetite fetch: %s", failure.message)
        typer.echo(failure.message, err=True)
        raise typer.Exit(EXIT_DIAGNOSTICS)

    client = _registry_client(routed.danger_ok)
    result = client.fetch_pinned(package, version)
    if result.is_err:
        failure = result.danger_err
        _log.error("magnetite fetch: %s", failure.message)
        typer.echo(failure.message, err=True)
        raise typer.Exit(EXIT_DIAGNOSTICS)
    entry, data = result.danger_ok
    yanked = " YANKED" if entry.yanked else ""
    typer.echo(
        f"{entry.name}\t{entry.version}\t{entry.archive_hash}\t{len(data)}B{yanked}"
    )
    raise typer.Exit(EXIT_CLEAN)


@config_app.command("get")
def config_get(
    key: str = typer.Argument(..., help="Dotted config key, e.g. ui.port."),
    project: str = typer.Option(".", "--project", help="Project root."),
) -> None:
    """Print one key's effective value (the winning source's coerced value)."""
    project_root = Path(discover_project_root(project))
    result = config.get_effective(key, project_root)
    if result.is_err:
        failure = result.danger_err
        _log.error("config get: %s", failure.message)
        typer.echo(failure.message, err=True)
        raise typer.Exit(EXIT_DIAGNOSTICS)
    typer.echo(str(result.danger_ok.value))
    raise typer.Exit(EXIT_CLEAN)


@config_app.command("where")
def config_where(
    key: str = typer.Argument(..., help="Dotted config key, e.g. ui.port."),
    project: str = typer.Option(".", "--project", help="Project root."),
) -> None:
    """Print one key's effective value AND which level won it (INV-21 for config)."""
    project_root = Path(discover_project_root(project))
    result = config.get_effective(key, project_root)
    if result.is_err:
        failure = result.danger_err
        _log.error("config where: %s", failure.message)
        typer.echo(failure.message, err=True)
        raise typer.Exit(EXIT_DIAGNOSTICS)
    effective = result.danger_ok
    typer.echo(f"{effective.key}={effective.value} (source={effective.source})")
    raise typer.Exit(EXIT_CLEAN)


@config_app.command("list")
def config_list(
    project: str = typer.Option(".", "--project", help="Project root."),
) -> None:
    """List every registered key's effective value and winning source."""
    project_root = Path(discover_project_root(project))
    result = config.list_effective(project_root)
    if result.is_err:
        failure = result.danger_err
        _log.error("config list: %s", failure.message)
        typer.echo(failure.message, err=True)
        raise typer.Exit(EXIT_DIAGNOSTICS)
    for effective in result.danger_ok:
        typer.echo(f"{effective.key}={effective.value} (source={effective.source})")
    raise typer.Exit(EXIT_CLEAN)


@config_app.command("set")
def config_set(
    key: str = typer.Argument(..., help="Dotted config key, e.g. ui.port."),
    value: str = typer.Argument(..., help="New value (coerced to the key's type)."),
    global_scope: bool = typer.Option(
        False, "--global", help="Write to the global user config file."
    ),
    local_scope: bool = typer.Option(
        False, "--local", help="Write to the project magnetite.toml [tool.regolith]."
    ),
    project: str = typer.Option(".", "--project", help="Project root."),
) -> None:
    """Write a value through the one config module (never a raw file poke).

    Exactly one of ``--global``/``--local`` is required.
    """
    if global_scope == local_scope:
        _log.error("config set: exactly one of --global/--local is required")
        typer.echo("pass exactly one of --global or --local", err=True)
        raise typer.Exit(EXIT_INTERNAL_ERROR)
    scope = "global" if global_scope else "local"
    project_root = Path(discover_project_root(project))
    result = config.set_value(key, value, scope=scope, project_root=project_root)
    if result.is_err:
        failure = result.danger_err
        _log.error("config set: %s", failure.message)
        typer.echo(failure.message, err=True)
        raise typer.Exit(EXIT_DIAGNOSTICS)
    typer.echo(f"wrote {key} to {result.danger_ok}")
    raise typer.Exit(EXIT_CLEAN)


if __name__ == "__main__":
    app()
