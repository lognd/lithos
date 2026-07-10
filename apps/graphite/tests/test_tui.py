"""textual pilot tests for `graphite tui` (WO-59 deliverable 3 acceptance):
config edit (both scopes) and a driven `check` whose diagnostics bytes
equal the CLI's own stderr/stdout rendering (verbatim assertion).
"""

from __future__ import annotations

import subprocess
import sys

import pytest
from graphite.tui_app import GraphiteApp
from textual.widgets import Input, Select, Static, TabbedContent


def _static_text(app: GraphiteApp, widget_id: str) -> str:
    """The plain text currently shown by one `Static` widget."""
    return str(app.query_one(widget_id, Static).render())


@pytest.fixture
def scaffolded_project(tmp_path):
    (tmp_path / "magnetite.toml").write_text('name = "x"\nversion = "0.1.0"\n')
    return tmp_path


@pytest.mark.asyncio
async def test_config_edit_global_scope(scaffolded_project, monkeypatch):
    fake_home = scaffolded_project / "fakehome"
    fake_home.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(fake_home / ".config"))
    app = GraphiteApp(project_root=scaffolded_project)
    async with app.run_test(size=(120, 60)) as pilot:
        app.query_one("#config-key", Input).value = "ui.port"
        app.query_one("#config-value", Input).value = "9090"
        app.query_one("#config-scope", Select).value = "global"
        await pilot.pause()
        await pilot.click("#config-set")
        await pilot.pause()
        assert "wrote ui.port" in _static_text(app, "#config-output")

        await pilot.click("#config-get")
        await pilot.pause()
        output2 = _static_text(app, "#config-output")
        assert "ui.port=9090" in output2
        assert "source=global" in output2


@pytest.mark.asyncio
async def test_config_edit_local_scope(scaffolded_project, monkeypatch):
    fake_home = scaffolded_project / "fakehome"
    fake_home.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(fake_home / ".config"))
    app = GraphiteApp(project_root=scaffolded_project)
    async with app.run_test(size=(120, 60)) as pilot:
        app.query_one("#config-key", Input).value = "optimize.seed"
        app.query_one("#config-value", Input).value = "5"
        app.query_one("#config-scope", Select).value = "local"
        await pilot.pause()
        await pilot.click("#config-set")
        await pilot.pause()
        assert "wrote optimize.seed" in _static_text(app, "#config-output")
        text = (scaffolded_project / "magnetite.toml").read_text()
        assert "[tool.regolith]" in text


@pytest.mark.asyncio
async def test_driven_check_is_verbatim(scaffolded_project):
    """The TUI's driver pane runs the exact subprocess `regolith check`
    would, so its displayed text is byte-identical to the CLI's own
    stdout+stderr for the same invocation."""
    source = scaffolded_project / "empty.hema"
    source.write_text("")

    direct = subprocess.run(
        [sys.executable, "-m", "regolith.cli", "check", str(source)],
        cwd=scaffolded_project,
        capture_output=True,
        text=True,
    )
    expected = direct.stdout + direct.stderr

    app = GraphiteApp(project_root=scaffolded_project)
    async with app.run_test(size=(120, 60)) as pilot:
        app.query_one(TabbedContent).active = "tab-driver"
        await pilot.pause()
        app.query_one("#run-verb", Select).value = "check"
        app.query_one("#run-args", Input).value = "empty.hema"
        await pilot.pause()
        await pilot.click("#run-button")
        await pilot.pause()
        rendered = _static_text(app, "#run-output")
        assert rendered == (expected or "(no output)")
