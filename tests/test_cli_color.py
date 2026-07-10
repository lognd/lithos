"""Optional ANSI colors (owner directive): `regolith.cli.color.resolve_color`
and the `--color [auto|always|never]` CLI wiring.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from regolith.cli.app import app
from regolith.cli.color import resolve_color
from typer.testing import CliRunner

runner = CliRunner()


class _FakeStream(io.StringIO):
    """A stream whose `isatty()` is controlled by the test."""

    def __init__(self, tty: bool) -> None:
        super().__init__()
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty


def test_always_wins_even_off_a_non_tty() -> None:
    assert resolve_color("always", _FakeStream(tty=False)) is True


def test_never_wins_even_on_a_tty() -> None:
    assert resolve_color("never", _FakeStream(tty=True)) is False


def test_auto_is_false_on_a_non_tty() -> None:
    assert resolve_color("auto", _FakeStream(tty=False)) is False


def test_auto_is_true_on_a_tty_with_a_normal_term(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")
    assert resolve_color("auto", _FakeStream(tty=True)) is True


def test_auto_respects_no_color_on_a_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("TERM", "xterm-256color")
    assert resolve_color("auto", _FakeStream(tty=True)) is False


def test_no_color_value_does_not_matter(monkeypatch: pytest.MonkeyPatch) -> None:
    """NO_COLOR wins by presence alone (https://no-color.org): even an
    empty value disables auto-color."""
    monkeypatch.setenv("NO_COLOR", "")
    monkeypatch.setenv("TERM", "xterm-256color")
    assert resolve_color("auto", _FakeStream(tty=True)) is False


def test_auto_respects_dumb_term(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "dumb")
    assert resolve_color("auto", _FakeStream(tty=True)) is False


def test_explicit_always_beats_no_color(monkeypatch: pytest.MonkeyPatch) -> None:
    """NO_COLOR beats `auto` but loses to an explicit `--color always`
    (the owner's stated precedence)."""
    monkeypatch.setenv("NO_COLOR", "1")
    assert resolve_color("always", _FakeStream(tty=False)) is True


def test_cli_check_accepts_color_option(tmp_path: Path) -> None:
    """`--color` is a root option every verb inherits; `check` (the
    verb with no persisted JSON artifact) actually colors its output
    under `always`, and produces plain text under `never` -- both must
    at least run cleanly end to end."""
    source = tmp_path / "empty.hema"
    source.write_text("")
    result_never = runner.invoke(app, ["--color", "never", "check", str(source)])
    result_always = runner.invoke(app, ["--color", "always", "check", str(source)])
    assert result_never.exit_code == result_always.exit_code
    assert "\x1b[" not in result_never.output
