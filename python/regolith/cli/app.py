"""The typer application object and its subcommands (AD-10).

Rich/terminal output lives only in this layer; libraries return data.
WO-15 adds ``check``/``build``/``debug``/``fmt``; WO-01 provides
``version`` so the installed console script is exercisable end to end.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import typer

from regolith import compiler, core_version
from regolith.backends.elec import AssemblyLine as ElecAssemblyLine
from regolith.backends.elec import ElecBackend
from regolith.backends.framework import Backend
from regolith.backends.mech import AssemblyLine as MechAssemblyLine
from regolith.backends.mech import FabNoteSpec, MechBackend
from regolith.backends.ship import ship as run_ship
from regolith.backends.ship import verify as run_verify
from regolith.docgen import claim_statuses, extract_package, render_markdown
from regolith.logging_setup import get_logger
from regolith.magnetite.scaffold import VALID_TEMPLATES, scaffold_project
from regolith.magnetite.trust import TrustKeySet, load_signing_key
from regolith.orchestrator.lockfile import Lockfile
from regolith.orchestrator.lockfile import parse as parse_lockfile

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


@app.callback()
def main() -> None:
    """Keep group behavior so subcommands work even when only one exists."""


@app.command()
def version() -> None:
    """Print the compiler core version (crosses the Rust boundary)."""
    typer.echo(core_version())


@app.command()
def check(
    files: list[str] = typer.Argument(..., help="Source files or project roots."),
    explain: str | None = typer.Option(
        None, "--explain", help="Explain a diagnostic code."
    ),
    waive: list[str] = typer.Option([], "--waive", help="Waive a Group.claim."),
    target: str | None = typer.Option(None, "--target", help="Build target."),
) -> None:
    """Run L0-L3 static checks (geometry-free, simulation-free).

    THE first shippable artifact (hematite/06 Phase B). Prints the one
    renderer's output verbatim and exits CLEAN / DIAGNOSTICS / INTERNAL.
    """
    _log.info("check: %d file(s)", len(files))
    result = compiler.check(tuple(files))
    if result.is_err:
        failure = result.danger_err
        _log.error("check: internal error: %s", failure.message)
        typer.echo(failure.message, err=True)
        raise typer.Exit(EXIT_INTERNAL_ERROR)
    outcome = result.danger_ok
    typer.echo(outcome.rendered)
    if outcome.ok:
        _log.info("check: clean")
        raise typer.Exit(EXIT_CLEAN)
    _log.info("check: diagnostics reported")
    raise typer.Exit(EXIT_DIAGNOSTICS)


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


@app.command()
def ship(
    files: list[str] = typer.Argument(..., help="Source files or project roots."),
    out: str = typer.Option("ship", "--out", help="Package output directory."),
    spec: str | None = typer.Option(
        None,
        "--spec",
        help="JSON file naming the mech/elec BOM+fab-note assembly "
        "(already-decided data this backend only serializes, "
        "regolith/07 sec. 6); omit to ship the manifest-only "
        "release attestation with no packages.",
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

    project_root = files[0] if files else "."
    lockfile_path = Path(project_root) / "regolith.lock"
    if Path(project_root).is_file():
        lockfile_path = Path(project_root).parent / "regolith.lock"
    try:
        lockfile_text = lockfile_path.read_text()
    except OSError as exc:
        _log.error("ship: cannot read %s: %s", lockfile_path, exc)
        typer.echo(f"cannot read {lockfile_path}: {exc}", err=True)
        raise typer.Exit(EXIT_INTERNAL_ERROR) from exc
    lockfile_result = parse_lockfile(lockfile_text)
    if lockfile_result.is_err:
        _log.error(
            "ship: cannot parse lockfile: %s", lockfile_result.danger_err.message
        )
        typer.echo(lockfile_result.danger_err.message, err=True)
        raise typer.Exit(EXIT_INTERNAL_ERROR)
    lockfile: Lockfile = lockfile_result.danger_ok

    backends: dict[str, Backend] = {}
    if spec is not None:
        spec_data = json.loads(Path(spec).read_text())
        mech = _mech_backend_from_spec(spec_data)
        if mech is not None:
            backends["mech"] = mech
        elec = _elec_backend_from_spec(spec_data)
        if elec is not None:
            backends["elec"] = elec

    signer = None
    if key is not None:
        key_result = load_signing_key(project_root, key)
        if key_result.is_err:
            typer.echo(key_result.danger_err.message, err=True)
            raise typer.Exit(EXIT_INTERNAL_ERROR)
        signer = key_result.danger_ok

    shipped = run_ship(tuple(files), backends, out, lockfile=lockfile, signer=signer)
    if shipped.is_err:
        _log.error("ship: %s", shipped.danger_err.message)
        typer.echo(shipped.danger_err.message, err=True)
        raise typer.Exit(EXIT_DIAGNOSTICS)
    manifest = shipped.danger_ok
    typer.echo(f"shipped {len(manifest.files)} file(s) to {out}")
    raise typer.Exit(EXIT_CLEAN)


@magnetite_app.command()
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


if __name__ == "__main__":
    app()
