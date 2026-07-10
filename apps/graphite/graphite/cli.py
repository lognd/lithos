"""The `graphite` console script: `graphite tui` and `graphite serve`
(WO-59 deliverables 3/4)."""

from __future__ import annotations

from pathlib import Path

import typer

from graphite.logging_setup import get_logger

_log = get_logger(__name__)

app = typer.Typer(
    name="graphite",
    help="graphite: the regolith interaction surface (config TUI + local-web GUI).",
    no_args_is_help=True,
)


@app.command()
def tui(project: str = typer.Argument(".", help="Project root to open.")) -> None:
    """Launch the textual TUI (config editing, check/build/optimize driving,
    build-report browsing)."""
    from graphite.tui_app import GraphiteApp

    _log.info("graphite tui: starting, project=%s", project)
    GraphiteApp(project_root=Path(project)).run()


@app.command()
def serve(
    project: str = typer.Argument(".", help="Project root (workspace) to serve."),
    host: str = typer.Option("127.0.0.1", "--host", help="Bind host (localhost only)."),
    port: int = typer.Option(8765, "--port", help="Bind port."),
) -> None:
    """Start the localhost GUI server over `project`'s disk artifacts."""
    from graphite.server import make_server

    workspace_root = Path(project).resolve()
    server = make_server(host, port, workspace_root)
    typer.echo(f"graphite serve: http://{host}:{port}/")
    _log.info("graphite serve: serving %s forever", workspace_root)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        _log.info("graphite serve: interrupted, shutting down")
    finally:
        server.server_close()


if __name__ == "__main__":
    app()
