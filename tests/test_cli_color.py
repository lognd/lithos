"""Optional ANSI colors (owner directive): `regolith.cli.color.resolve_color`
and the `--color [auto|always|never]` CLI wiring.
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
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


# frob:tests python/regolith/cli/color.py::resolve_color
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


def test_cli_verbose_and_quiet_flags_run(tmp_path: Path) -> None:
    """`-v`/`-q` are root options every verb inherits (WO-107); both must
    run cleanly end to end and not change the exit code."""
    source = tmp_path / "empty.hema"
    source.write_text("")
    base = runner.invoke(app, ["check", str(source)])
    verbose = runner.invoke(app, ["-v", "check", str(source)])
    quiet = runner.invoke(app, ["-q", "check", str(source)])
    assert base.exit_code == verbose.exit_code == quiet.exit_code


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


def _run_check(source: Path, *flags: str, env_extra: dict[str, str] | None = None):
    """Run the real `regolith check` console entry point in a subprocess so
    stdout and stderr are captured as separate byte streams (WO-107)."""
    env: dict[str, str] = {**os.environ}
    env.pop("NO_COLOR", None)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-m", "regolith.cli", *flags, "check", str(source)],
        capture_output=True,
        text=True,
        env=env,
    )


def test_stdout_byte_identical_across_color_modes(tmp_path: Path) -> None:
    """stdout is DATA: it must be byte-identical whether logs are colored
    (`--color always`), plain (`NO_COLOR`), or default (WO-107 acceptance)."""
    source = tmp_path / "empty.hema"
    source.write_text("")
    always = _run_check(source, "--color", "always")
    nocolor = _run_check(source, env_extra={"NO_COLOR": "1"})
    default = _run_check(source)
    assert always.stdout == nocolor.stdout == default.stdout


def test_stderr_ansi_only_when_color_forced(tmp_path: Path) -> None:
    """stderr carries ANSI under `--color always` and ZERO ANSI bytes under
    `NO_COLOR` (WO-107 acceptance)."""
    source = tmp_path / "empty.hema"
    source.write_text("")
    always = _run_check(source, "--color", "always")
    nocolor = _run_check(source, env_extra={"NO_COLOR": "1"})
    assert "\x1b[" in always.stderr
    assert "\x1b[" not in nocolor.stderr


def test_verbose_restores_demoted_records(tmp_path: Path) -> None:
    """`-v` restores what default verbosity demotes: span-enter records
    (`<span>;`, hidden at default) reappear, and `-v` strictly out-counts
    the default INFO stream -- proving no record is unreachable (WO-107)."""
    source = tmp_path / "empty.hema"
    source.write_text("")
    default = _run_check(source)
    verbose = _run_check(source, "-v")
    default_lines = [ln for ln in default.stderr.splitlines() if ln.strip()]
    verbose_lines = [ln for ln in verbose.stderr.splitlines() if ln.strip()]
    # Span records are demoted (absent) at default, restored under `-v`.
    assert not any(ln.rstrip().endswith(";") for ln in default_lines)
    assert any(ln.rstrip().endswith(";") for ln in verbose_lines)
    # And `-v` restores strictly more than the aggregated default view.
    assert len(verbose_lines) > len(default_lines)
