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


@app.callback()
def main() -> None:
    """Keep group behavior so subcommands work even when only one exists."""


@app.command()
def version() -> None:
    """Print the compiler core version (crosses the Rust boundary)."""
    typer.echo(core_version())


if __name__ == "__main__":
    app()
