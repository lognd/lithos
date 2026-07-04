"""The typer application object and its subcommands (AD-10).

Rich/terminal output lives only in this layer; libraries return data.
WO-15 adds ``check``/``build``/``debug``/``fmt``; WO-01 provides
``version`` so the installed console script is exercisable end to end.
"""

from __future__ import annotations

import typer

from rockhead import core_version

app = typer.Typer(
    name="rockhead",
    help="The rockhead engineering toolchain (hematite + cuprite).",
    no_args_is_help=True,
)

# Exit codes (WO-15): distinguish clean from diagnostics from internal
# error so CI and humans can branch on them.
EXIT_CLEAN = 0
EXIT_DIAGNOSTICS = 1
EXIT_INTERNAL_ERROR = 2


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
    waive: list[str] = typer.Option(
        [], "--waive", help="Waive a Group.claim."
    ),
    target: str | None = typer.Option(None, "--target", help="Build target."),
) -> None:
    """Run L0-L3 static checks (geometry-free, simulation-free).

    THE first shippable artifact (mech/06 Phase B). Prints the one
    renderer's output verbatim and exits CLEAN / DIAGNOSTICS / INTERNAL.
    """
    raise NotImplementedError(
        "STUB WO-15: facade.check(files); print rendered; exit by outcome"
    )


@app.command()
def fmt(files: list[str] = typer.Argument(..., help="Source files to format.")) -> None:
    """Rewrite files in their canonical form (the WO-05 normalizer)."""
    raise NotImplementedError(
        "STUB WO-15: call the core formatter over each file, write back"
    )


@app.command()
def debug(
    stage: str = typer.Argument(..., help="tokens | cst | ast | ir"),
    path: str = typer.Argument(..., help="Source file to dump."),
) -> None:
    """Dump an intermediate pipeline stage (AD-13 inspectability)."""
    raise NotImplementedError("STUB WO-15: facade.debug_dump(stage, path) -> stdout")


if __name__ == "__main__":
    app()
