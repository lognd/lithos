"""One configuration doctrine (AD-31, D163/D164; toolchain/29 sec. 1).

Precedence, weakest first: global user file (platformdirs user-config
``regolith/config.toml``) < project ``magnetite.toml`` ``[tool.regolith]``
tables < environment (``REGOLITH_*``) < explicit CLI flag. This module is
the ONLY reader/writer of either file; ``regolith config get|set|list|where``
(cli/app.py) is the surface, and ``get_effective``/``list_effective``
attribute every resolved value to the level that won.

Config is tool preference only (charter sec. 1.1): default optimize
budgets/seed, UI host/port, lint-level passthrough. Nothing here may reach
the margin math -- see ``tests/test_config_import_boundary.py`` for the
import-direction assertion (harness/discharge never import this module).
"""

from __future__ import annotations

import os
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import cast

import platformdirs
from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from regolith.logging_setup import get_logger

_log = get_logger(__name__)

_GLOBAL_APP_NAME = "regolith"
_GLOBAL_FILENAME = "config.toml"
_PROJECT_MANIFEST_FILENAME = "magnetite.toml"
_ENV_PREFIX = "REGOLITH_"


# frob:doc docs/modules/py-regolith.md#config
class ConfigKeySpec(BaseModel):
    """One registered config key: its dotted name, type, and default.

    The registered-key table (module-level ``REGISTERED_KEYS``) is the
    only source of valid keys; an unregistered key is a constructive
    error naming the near-miss set, never a silent passthrough.
    """

    model_config = ConfigDict(frozen=True)

    key: str
    kind: str  # "str" | "int" | "float" | "bool"
    default: str | int | float | bool
    doc: str


# Config keys v1 (WO-59 deliverable 1): default optimize budgets/seed, UI
# prefs (host/port), lint level passthrough. Adding a key means adding a
# row HERE -- the one registry -- plus wiring its env var name below.
# frob:doc docs/modules/py-regolith.md#config
REGISTERED_KEYS: tuple[ConfigKeySpec, ...] = (
    ConfigKeySpec(
        key="optimize.budget_evals",
        kind="int",
        default=1000,
        doc="Default --budget-evals for `regolith optimize` when unset.",
    ),
    ConfigKeySpec(
        key="optimize.seed",
        kind="int",
        default=0,
        doc="Default --seed for `regolith optimize` when unset.",
    ),
    ConfigKeySpec(
        key="ui.host",
        kind="str",
        default="127.0.0.1",
        doc="Bind host for `graphite serve` (must stay localhost, AD-31).",
    ),
    ConfigKeySpec(
        key="ui.port",
        kind="int",
        default=8765,
        doc="Bind port for `graphite serve`.",
    ),
    ConfigKeySpec(
        key="lint.level",
        kind="str",
        default="warn",
        doc="Default lint action passthrough (allow|warn|deny) absent a "
        "[lints] entry for a given code.",
    ),
    ConfigKeySpec(
        key="records.stdlib_root",
        kind="str",
        default="",
        doc="Explicit stdlib root directory (containing std.civil/, "
        "std.cost/, etc) for CLI record resolution; empty defers to the "
        "vendored-copy then dev-walk fallback (regolith.magnetite.stdlib_resolve).",
    ),
)

_KEYS_BY_NAME: dict[str, ConfigKeySpec] = {spec.key: spec for spec in REGISTERED_KEYS}


# frob:doc docs/modules/py-regolith.md#config
def registered_keys() -> tuple[ConfigKeySpec, ...]:
    """The name-sorted registered-key table (for `regolith config list`)."""
    return tuple(sorted(REGISTERED_KEYS, key=lambda s: s.key))


# frob:doc docs/modules/py-regolith.md#config
class ConfigError(BaseModel):
    """A config resolution/parse/write failure (unknown key, bad TOML)."""

    model_config = ConfigDict(frozen=True)

    kind: str
    message: str


# frob:doc docs/modules/py-regolith.md#config
class EffectiveValue(BaseModel):
    """One resolved config value plus the source level that won (INV-21
    applied to configuration, D164)."""

    model_config = ConfigDict(frozen=True)

    key: str
    value: str | int | float | bool
    source: str  # "default" | "global" | "project" | "env" | "flag"


def _env_var_name(key: str) -> str:
    """`optimize.budget_evals` -> `REGOLITH_OPTIMIZE_BUDGET_EVALS`."""
    return _ENV_PREFIX + key.upper().replace(".", "_")


# frob:doc docs/modules/py-regolith.md#config
def global_config_path() -> Path:
    """The platformdirs user-config path: `<user config dir>/regolith/config.toml`."""
    return Path(platformdirs.user_config_dir(_GLOBAL_APP_NAME)) / _GLOBAL_FILENAME


def _coerce(
    spec: ConfigKeySpec, raw: object
) -> Result[str | int | float | bool, ConfigError]:
    """Coerce a raw TOML/env/flag value to the key's declared kind."""
    if spec.kind == "bool":
        if isinstance(raw, bool):
            return Ok(raw)
        if isinstance(raw, str):
            lowered = raw.strip().lower()
            if lowered in ("1", "true", "yes", "on"):
                return Ok(True)
            if lowered in ("0", "false", "no", "off"):
                return Ok(False)
        return Err(
            ConfigError(kind="bad_value", message=f"{spec.key}: not a bool: {raw!r}")
        )
    if spec.kind == "int":
        try:
            return Ok(int(cast("str", raw)))
        except (TypeError, ValueError):
            return Err(
                ConfigError(
                    kind="bad_value", message=f"{spec.key}: not an int: {raw!r}"
                )
            )
    if spec.kind == "float":
        try:
            return Ok(float(cast("str", raw)))
        except (TypeError, ValueError):
            return Err(
                ConfigError(
                    kind="bad_value", message=f"{spec.key}: not a float: {raw!r}"
                )
            )
    return Ok(str(raw))


def _read_toml_table(path: Path) -> Result[dict[str, object], ConfigError]:
    """Parse a whole TOML file to a dict; an absent file is an empty table."""
    if not path.exists():
        return Ok({})
    try:
        with path.open("rb") as fh:
            return Ok(tomllib.load(fh))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        _log.error("config: cannot parse %s: %s", path, exc)
        return Err(ConfigError(kind="parse_error", message=f"{path}: {exc}"))


def _flatten_dotted(table: Mapping[str, object], prefix: str = "") -> dict[str, object]:
    """Flatten a nested TOML table into dotted keys (`[x] y=1` -> `x.y`)."""
    flat: dict[str, object] = {}
    for name, value in table.items():
        dotted = f"{prefix}{name}" if not prefix else f"{prefix}.{name}"
        if isinstance(value, dict):
            flat.update(_flatten_dotted(cast("Mapping[str, object]", value), dotted))
        else:
            flat[dotted] = value
    return flat


def _project_table(
    project_root: Path,
) -> Result[dict[str, object], ConfigError]:
    """`[tool.regolith]` from the project's manifest (the `[lints]` precedent)."""
    manifest_path = project_root / _PROJECT_MANIFEST_FILENAME
    parsed = _read_toml_table(manifest_path)
    if parsed.is_err:
        return parsed
    data = parsed.danger_ok
    tool_table = data.get("tool", {})
    if not isinstance(tool_table, dict):
        return Ok({})
    regolith_table = tool_table.get("regolith", {})
    if not isinstance(regolith_table, dict):
        return Ok({})
    return Ok(_flatten_dotted(cast("Mapping[str, object]", regolith_table)))


def _global_table() -> Result[dict[str, object], ConfigError]:
    """The flattened global user config file."""
    parsed = _read_toml_table(global_config_path())
    if parsed.is_err:
        return parsed
    return Ok(_flatten_dotted(parsed.danger_ok))


# frob:doc docs/modules/py-regolith.md#config
def get_effective(
    key: str,
    project_root: Path,
    flag_value: str | int | float | bool | None = None,
) -> Result[EffectiveValue, ConfigError]:
    """Resolve one key across all four levels, weakest first, and name the winner.

    Order: default < global file < project `[tool.regolith]` < `REGOLITH_*`
    env < ``flag_value`` (explicit CLI flag, when the caller passed one).
    """
    spec = _KEYS_BY_NAME.get(key)
    if spec is None:
        near = ", ".join(s.key for s in registered_keys())
        _log.error("config: unknown key %r (registered: %s)", key, near)
        return Err(
            ConfigError(
                kind="unknown_key",
                message=f"unknown config key {key!r}; registered keys: {near}",
            )
        )

    value: str | int | float | bool = spec.default
    source = "default"

    global_table = _global_table()
    if global_table.is_err:
        return Err(global_table.danger_err)
    if key in global_table.danger_ok:
        coerced = _coerce(spec, global_table.danger_ok[key])
        if coerced.is_err:
            return Err(coerced.danger_err)
        value, source = coerced.danger_ok, "global"

    project_table = _project_table(project_root)
    if project_table.is_err:
        return Err(project_table.danger_err)
    if key in project_table.danger_ok:
        coerced = _coerce(spec, project_table.danger_ok[key])
        if coerced.is_err:
            return Err(coerced.danger_err)
        value, source = coerced.danger_ok, "project"

    env_name = _env_var_name(key)
    if env_name in os.environ:
        coerced_env = _coerce(spec, os.environ[env_name])
        if coerced_env.is_err:
            return Err(coerced_env.danger_err)
        value, source = coerced_env.danger_ok, "env"

    if flag_value is not None:
        coerced = _coerce(spec, flag_value)
        if coerced.is_err:
            return Err(coerced.danger_err)
        value, source = coerced.danger_ok, "flag"

    _log.debug("config: %s=%r (source=%s)", key, value, source)
    return Ok(EffectiveValue(key=key, value=value, source=source))


# frob:doc docs/modules/py-regolith.md#config
def list_effective(
    project_root: Path,
) -> Result[tuple[EffectiveValue, ...], ConfigError]:
    """Every registered key's effective value (no flag level -- `list`/`where`
    only see file/env levels; a flag is a single-command-invocation override)."""
    results: list[EffectiveValue] = []
    for spec in registered_keys():
        resolved = get_effective(spec.key, project_root)
        if resolved.is_err:
            return Err(resolved.danger_err)
        results.append(resolved.danger_ok)
    return Ok(tuple(results))


# frob:doc docs/modules/py-regolith.md#config
def set_value(
    key: str,
    value: str,
    *,
    scope: str,
    project_root: Path,
) -> Result[Path, ConfigError]:
    """Write ``key = value`` into the global file or the project manifest's
    `[tool.regolith]` table (`scope` is `"global"` or `"local"`). Round-trips
    through the SAME module that reads it -- never a raw file poke elsewhere.
    """
    spec = _KEYS_BY_NAME.get(key)
    if spec is None:
        near = ", ".join(s.key for s in registered_keys())
        _log.error("config set: unknown key %r", key)
        return Err(
            ConfigError(
                kind="unknown_key",
                message=f"unknown config key {key!r}; registered keys: {near}",
            )
        )
    coerced = _coerce(spec, value)
    if coerced.is_err:
        return Err(coerced.danger_err)

    if scope == "global":
        path = global_config_path()
        existing = _read_toml_table(path)
        if existing.is_err:
            return Err(existing.danger_err)
        table = _flatten_dotted(existing.danger_ok)
        table[key] = coerced.danger_ok
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_render_flat_toml(table))
        _log.info("config set: wrote %s to global %s", key, path)
        return Ok(path)
    if scope == "local":
        path = project_root / _PROJECT_MANIFEST_FILENAME
        existing = _read_toml_table(path)
        if existing.is_err:
            return Err(existing.danger_err)
        data = existing.danger_ok
        tool_table_raw = data.get("tool")
        tool_table: dict[str, object] = (
            cast("dict[str, object]", tool_table_raw)
            if isinstance(tool_table_raw, dict)
            else {}
        )
        regolith_table_raw = tool_table.get("regolith")
        regolith_table: dict[str, object] = (
            cast("dict[str, object]", regolith_table_raw)
            if isinstance(regolith_table_raw, dict)
            else {}
        )
        regolith_table[key] = coerced.danger_ok
        tool_table["regolith"] = regolith_table
        data["tool"] = tool_table
        path.write_text(_render_project_toml(data))
        _log.info("config set: wrote %s to project %s", key, path)
        return Ok(path)
    _log.error("config set: bad scope %r", scope)
    return Err(
        ConfigError(
            kind="bad_scope", message=f"scope must be global|local, got {scope!r}"
        )
    )


def _toml_scalar(value: object) -> str:
    """Render one scalar value as a TOML literal (bool before int: bool is
    an int subclass in Python)."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _render_flat_toml(table: dict[str, object]) -> str:
    """Render a dotted-key table back to TOML (dotted keys are valid TOML keys)."""
    lines = [f'"{key}" = {_toml_scalar(value)}' for key, value in sorted(table.items())]
    return "\n".join(lines) + "\n" if lines else ""


def _render_project_toml(data: dict[str, object]) -> str:
    """Round-trip the whole `magnetite.toml` back out, preserving other
    top-level tables verbatim (only `[tool.regolith]` is touched by `set`)."""
    lines: list[str] = []
    tool_table = data.pop("tool", None)
    for key, value in data.items():
        if not isinstance(value, dict):
            lines.append(f"{key} = {_toml_scalar(value)}")
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append("")
            lines.append(f"[{key}]")
            for subkey, subvalue in value.items():
                lines.append(f"{subkey} = {_toml_scalar(subvalue)}")
    if isinstance(tool_table, dict):
        regolith_table = tool_table.get("regolith", {})
        if not isinstance(regolith_table, dict):
            regolith_table = {}
        lines.append("")
        lines.append("[tool.regolith]")
        for key, value in sorted(regolith_table.items()):
            lines.append(f'"{key}" = {_toml_scalar(value)}')
        for tool_name, tool_value in tool_table.items():
            if tool_name == "regolith" or not isinstance(tool_value, dict):
                continue
            lines.append("")
            lines.append(f"[tool.{tool_name}]")
            for subkey, subvalue in tool_value.items():
                lines.append(f"{subkey} = {_toml_scalar(subvalue)}")
        data["tool"] = tool_table
    return "\n".join(lines) + "\n"
