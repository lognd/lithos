"""The verilator subprocess adapter (WO-82; AD-19 subprocess adapter law).

ONE seam runs verilator: JSON-free but the same law applies verbatim --
stdin/args go over argv, stderr is logs (never parsed for a verdict),
and any tool failure (nonzero exit, missing binary, timeout) becomes an
honest :class:`ToolFailure` value the caller maps to ``Err(DomainError)``
-- INDETERMINATE evidence, never an exception, never a silent pass.
The verilator VERSION string is resolved once and folded into every
caller's ``Model.version`` (cache-key law: an upgraded tool invalidates
exactly its own cached evidence, mirroring AD-19's pack-version fold).
"""

from __future__ import annotations

import re
import subprocess
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from regolith.logging_setup import get_logger
from regolith.toolenv import resolve as resolve_tool

_log = get_logger(__name__)

VERILATOR_BIN = "verilator"
_VERSION_RE = re.compile(r"Verilator\s+(\S+)")
_STDERR_EXCERPT_LINES = 40


class ToolFailure(BaseModel):
    """Verilator could not be run to a verdict: version + argv + a
    bounded stderr excerpt (AD-19: adapter failure is data, cited)."""

    model_config = ConfigDict(frozen=True)

    tool: str = "verilator"
    version: str
    argv: tuple[str, ...]
    returncode: int | None
    stderr_excerpt: str


def _excerpt(text: str, *, lines: int = _STDERR_EXCERPT_LINES) -> str:
    """Bound a stderr blob to the last N lines (the useful end -- the
    fatal diagnostic -- without unbounded evidence payloads)."""
    parts = text.splitlines()
    if len(parts) <= lines:
        return text
    return "\n".join(["...(truncated)...", *parts[-lines:]])


@lru_cache(maxsize=1)
def verilator_version() -> str:
    """The installed verilator's version string, e.g. ``5.047``.

    Cached per-process (the binary does not change mid-run); returns
    ``"unknown"`` if the binary is missing or the output is unparsable
    -- callers still fold this into their cache key, so "unknown" simply
    collapses caching rather than crashing (never an exception here:
    version resolution is diagnostic, not a discharge decision).
    """
    try:
        proc = subprocess.run(
            [VERILATOR_BIN, "--version"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        _log.warning("verilator --version failed to run: %s", exc)
        return "unknown"
    match = _VERSION_RE.search(proc.stdout or proc.stderr or "")
    if match is None:
        _log.warning("verilator --version output unparsable: %r", proc.stdout)
        return "unknown"
    version = match.group(1)
    _log.info("resolved verilator version=%s", version)
    return version


def run_verilator(
    argv: list[str],
    *,
    cwd: Path,
    timeout_s: float = 120.0,
) -> Result[subprocess.CompletedProcess[str], ToolFailure]:
    """Run ``verilator <argv>`` in ``cwd``; ``Err(ToolFailure)`` on any
    nonzero exit, missing binary, or timeout (AD-19: never an exception
    escapes this seam)."""
    full_argv = [VERILATOR_BIN, *argv]
    _log.debug("running verilator: %s (cwd=%s)", full_argv, cwd)
    try:
        proc = subprocess.run(
            full_argv,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except FileNotFoundError:
        status = resolve_tool("verilator", use_cache=False, probe_version=False)
        teaching = status.teaching_message(needed_for="this HDL claim")
        return Err(
            ToolFailure(
                version=verilator_version(),
                argv=tuple(full_argv),
                returncode=None,
                stderr_excerpt=teaching,
            )
        )
    except subprocess.TimeoutExpired as exc:
        stderr = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
        return Err(
            ToolFailure(
                version=verilator_version(),
                argv=tuple(full_argv),
                returncode=None,
                stderr_excerpt=_excerpt(f"timed out after {timeout_s}s\n{stderr}"),
            )
        )
    if proc.returncode != 0:
        _log.info("verilator failed: argv=%s returncode=%d", full_argv, proc.returncode)
        return Err(
            ToolFailure(
                version=verilator_version(),
                argv=tuple(full_argv),
                returncode=proc.returncode,
                stderr_excerpt=_excerpt(proc.stderr or proc.stdout or ""),
            )
        )
    return Ok(proc)


__all__ = ["ToolFailure", "run_verilator", "verilator_version"]
