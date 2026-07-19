"""Enable ``python -m regolith.cli`` to run the typer app."""

# frob:waive TEST005 reason="measured 0.0% line on 2026-07-19; backfill T-0036"

from __future__ import annotations

from regolith.cli import app

app()
