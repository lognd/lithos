"""`regolith.config` (WO-59 D164): the four-level precedence matrix, the
registered-key table's constructive unknown-key error, and the
`set_value` round-trip through both stores.
"""

from __future__ import annotations

import pytest
from regolith import config


@pytest.fixture(autouse=True)
def _isolated_global_config(tmp_path, monkeypatch):
    """Point platformdirs' user-config dir at a scratch directory so tests
    never touch the real developer's `~/.config/regolith/config.toml`."""
    fake_home = tmp_path / "fakehome"
    fake_home.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(fake_home / ".config"))
    monkeypatch.delenv("REGOLITH_UI_PORT", raising=False)
    monkeypatch.delenv("REGOLITH_OPTIMIZE_SEED", raising=False)
    yield


# frob:tests python/regolith/config.py::get_effective
# frob:tests python/regolith/config.py kind="integration"
def test_unknown_key_is_constructive_error(tmp_path):
    result = config.get_effective("nope.nope", tmp_path)
    assert result.is_err
    assert result.danger_err.kind == "unknown_key"
    assert "ui.port" in result.danger_err.message


def test_default_wins_absent_everything(tmp_path):
    result = config.get_effective("ui.port", tmp_path)
    assert result.is_ok
    assert result.danger_ok.source == "default"
    assert result.danger_ok.value == 8765


# frob:tests python/regolith/config.py::set_value
def test_global_beats_default(tmp_path):
    written = config.set_value("ui.port", "1111", scope="global", project_root=tmp_path)
    assert written.is_ok
    result = config.get_effective("ui.port", tmp_path)
    assert result.danger_ok.source == "global"
    assert result.danger_ok.value == 1111


def test_project_beats_global(tmp_path):
    config.set_value("ui.port", "1111", scope="global", project_root=tmp_path)
    (tmp_path / "magnetite.toml").write_text(
        'name = "x"\nversion = "0.1.0"\n\n[tool.regolith]\n"ui.port" = 2222\n'
    )
    result = config.get_effective("ui.port", tmp_path)
    assert result.danger_ok.source == "project"
    assert result.danger_ok.value == 2222


def test_env_beats_project(tmp_path, monkeypatch):
    config.set_value("ui.port", "1111", scope="global", project_root=tmp_path)
    (tmp_path / "magnetite.toml").write_text(
        'name = "x"\nversion = "0.1.0"\n\n[tool.regolith]\n"ui.port" = 2222\n'
    )
    monkeypatch.setenv("REGOLITH_UI_PORT", "3333")
    result = config.get_effective("ui.port", tmp_path)
    assert result.danger_ok.source == "env"
    assert result.danger_ok.value == 3333


def test_flag_beats_env(tmp_path, monkeypatch):
    config.set_value("ui.port", "1111", scope="global", project_root=tmp_path)
    (tmp_path / "magnetite.toml").write_text(
        'name = "x"\nversion = "0.1.0"\n\n[tool.regolith]\n"ui.port" = 2222\n'
    )
    monkeypatch.setenv("REGOLITH_UI_PORT", "3333")
    result = config.get_effective("ui.port", tmp_path, flag_value=4444)
    assert result.danger_ok.source == "flag"
    assert result.danger_ok.value == 4444


def test_set_local_round_trips_and_preserves_other_tables(tmp_path):
    (tmp_path / "magnetite.toml").write_text(
        'name = "x"\nversion = "0.1.0"\n\n[lints]\nE001 = "deny"\n'
    )
    written = config.set_value(
        "optimize.seed", "7", scope="local", project_root=tmp_path
    )
    assert written.is_ok
    text = (tmp_path / "magnetite.toml").read_text()
    assert "[tool.regolith]" in text
    assert '"optimize.seed" = 7' in text
    assert "[lints]" in text
    assert 'E001 = "deny"' in text
    result = config.get_effective("optimize.seed", tmp_path)
    assert result.danger_ok.value == 7
    assert result.danger_ok.source == "project"


def test_list_effective_covers_every_registered_key(tmp_path):
    result = config.list_effective(tmp_path)
    assert result.is_ok
    keys = {v.key for v in result.danger_ok}
    assert keys == {spec.key for spec in config.registered_keys()}


def test_bad_int_value_is_constructive_error(tmp_path):
    result = config.set_value(
        "ui.port", "not-an-int", scope="global", project_root=tmp_path
    )
    assert result.is_err
    assert result.danger_err.kind == "bad_value"
