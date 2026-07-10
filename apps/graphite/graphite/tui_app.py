"""The `graphite tui` textual application (WO-59 deliverable 3).

Three panes, one screen: config editing (global + project, through
`regolith.config`'s public API -- never a raw file poke), driving
`check`/`build`/`optimize` as a subprocess with diagnostics displayed
VERBATIM (AD-7: no re-rendering, no re-coloring -- the subprocess's own
stdout/stderr bytes, unmodified), and browsing the last build report JSON
(`graphite.artifacts`/plain file read, artifact-only channel).

Never imports `regolith.orchestrator`/`regolith.harness` -- config edits go
through `regolith.config` (the one doctrine module, not orchestrator
state) and everything else is a subprocess or a disk read.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Select,
    Static,
    TabbedContent,
    TabPane,
)

from graphite.artifacts import read_json
from graphite.logging_setup import get_logger

_log = get_logger(__name__)

_BUILD_REPORT_RELPATH = Path(".regolith") / "build" / "build_report.json"


class ConfigPane(Vertical):
    """Edit one config key in either scope through `regolith.config`."""

    def __init__(self, project_root: Path) -> None:
        super().__init__()
        self._project_root = project_root

    def compose(self) -> ComposeResult:
        yield Static("Config key (dotted), e.g. ui.port:")
        yield Input(placeholder="ui.port", id="config-key")
        yield Static("Value (for Set):")
        yield Input(placeholder="8765", id="config-value")
        yield Select(
            [("global", "global"), ("local", "local")],
            value="local",
            id="config-scope",
        )
        with Vertical(id="config-buttons"):
            yield Button("Get", id="config-get")
            yield Button("Set", id="config-set")
        yield Static("", id="config-output")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        from regolith import config as regolith_config

        key = self.query_one("#config-key", Input).value.strip()
        output = self.query_one("#config-output", Static)
        if not key:
            output.update("enter a key first")
            return
        if event.button.id == "config-get":
            result = regolith_config.get_effective(key, self._project_root)
            if result.is_err:
                output.update(result.danger_err.message)
            else:
                effective = result.danger_ok
                output.update(
                    f"{effective.key}={effective.value} (source={effective.source})"
                )
        elif event.button.id == "config-set":
            value = self.query_one("#config-value", Input).value.strip()
            scope = self.query_one("#config-scope", Select).value
            result = regolith_config.set_value(
                key, value, scope=str(scope), project_root=self._project_root
            )
            if result.is_err:
                output.update(result.danger_err.message)
            else:
                output.update(f"wrote {key} to {result.danger_ok}")


class DriverPane(Vertical):
    """Run `check`/`build`/`optimize` as a subprocess; VERBATIM stdout+stderr
    (AD-7 -- the CLI's own rendered diagnostics, never re-colored)."""

    def __init__(self, project_root: Path) -> None:
        super().__init__()
        self._project_root = project_root

    def compose(self) -> ComposeResult:
        yield Select(
            [("check", "check"), ("build", "build"), ("optimize", "optimize")],
            value="check",
            id="run-verb",
        )
        yield Input(placeholder="extra args (space-separated)", id="run-args")
        yield Button("Run", id="run-button")
        yield Static("", id="run-output")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "run-button":
            return
        verb = str(self.query_one("#run-verb", Select).value)
        extra = self.query_one("#run-args", Input).value.split()
        argv = [sys.executable, "-m", "regolith.cli", verb, *extra]
        _log.info("graphite tui: running %s", argv)
        completed = subprocess.run(
            argv, cwd=self._project_root, capture_output=True, text=True
        )
        # VERBATIM: concatenate exactly what the CLI itself wrote, no
        # reformatting -- the ONE diagnostic renderer rule (AD-7) applied
        # to the TUI pane exactly as to a terminal.
        verbatim = completed.stdout + completed.stderr
        self.query_one("#run-output", Static).update(verbatim or "(no output)")


class ReportPane(Vertical):
    """Browse the last `build_report.json` under `.regolith/build/`."""

    def __init__(self, project_root: Path) -> None:
        super().__init__()
        self._project_root = project_root

    def compose(self) -> ComposeResult:
        yield Button("Load last build report", id="report-load")
        yield Static("", id="report-output")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "report-load":
            return
        path = self._project_root / _BUILD_REPORT_RELPATH
        output = self.query_one("#report-output", Static)
        if not path.is_file():
            output.update(f"no build report at {path}")
            return
        output.update(read_json(path))


class GraphiteApp(App[None]):
    """The graphite TUI root: config / driver / report tabs."""

    CSS = """
    Vertical { padding: 1; }
    """

    def __init__(self, project_root: Path) -> None:
        super().__init__()
        self._project_root = project_root

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent():
            with TabPane("Config", id="tab-config"):
                yield ConfigPane(self._project_root)
            with TabPane("Driver", id="tab-driver"):
                yield DriverPane(self._project_root)
            with TabPane("Report", id="tab-report"):
                yield ReportPane(self._project_root)
        yield Footer()
