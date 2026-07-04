"""The ``rockhead`` command-line surface (typer). WO-15 grows the real
subcommands over the facade; WO-01 ships a working entry point that
reports the core version."""

from __future__ import annotations

from rockhead.cli.app import app

__all__ = ["app"]
