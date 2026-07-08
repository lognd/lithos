"""The typer application object and its subcommands (AD-10).

Rich/terminal output lives only in this layer; libraries return data.
WO-15 adds ``check``/``build``/``debug``/``fmt``; WO-01 provides
``version`` so the installed console script is exercisable end to end.
"""

from __future__ import annotations

from pathlib import Path

import typer

from regolith import compiler, core_version
from regolith.docgen import claim_statuses, extract_package, render_markdown
from regolith.logging_setup import get_logger
from regolith.quarry.scaffold import VALID_TEMPLATES, scaffold_project

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


quarry_app = typer.Typer(
    name="quarry",
    help="The quarry package tool (manifests, registry, scaffolding).",
    no_args_is_help=True,
)
app.add_typer(quarry_app, name="quarry")


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
    """Dump an intermediate pipeline stage (AD-13 inspectability)."""
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


@quarry_app.command()
def new(
    name: str = typer.Argument(..., help="Project (and directory) name."),
    template: str = typer.Option(
        "mech",
        "--template",
        help=f"Project template: one of {', '.join(VALID_TEMPLATES)}.",
    ),
) -> None:
    """Scaffold a working project that passes ``regolith check`` (WO-41).

    Emits ``quarry.toml``, one source file per track (each with an
    honest example claim), a house ``.gitignore``, and a CI snippet.
    Refuses to overwrite a non-empty directory.
    """
    _log.info("quarry new: %s (template=%s)", name, template)
    result = scaffold_project(name, template)
    if result.is_err:
        failure = result.danger_err
        _log.error("quarry new: %s", failure.message)
        typer.echo(failure.message, err=True)
        raise typer.Exit(EXIT_INTERNAL_ERROR)
    typer.echo(f"scaffolded {result.danger_ok} from template '{template}'")
    raise typer.Exit(EXIT_CLEAN)


if __name__ == "__main__":
    app()
