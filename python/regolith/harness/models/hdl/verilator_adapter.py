"""The verilator subprocess adapter (WO-82; AD-19 subprocess adapter law;
WO-153: the spawn itself now runs through `regolith.procio`).

ONE seam runs verilator: JSON-free but the same law applies verbatim --
argv is typed (`regolith.procio.VerilatorLintArgs`/`VerilatorBinaryArgs`),
stderr is logs (never parsed for a verdict), and any tool failure
(nonzero exit, missing binary, timeout) becomes an honest
:class:`ToolFailure` value the caller maps to ``Err(DomainError)`` --
INDETERMINATE evidence, never an exception, never a silent pass.
``ToolFailure`` here IS `regolith.procio.ToolFailure` (re-exported): the
seam's one generalized failure shape, not a bespoke restatement.
The verilator VERSION string is resolved once and folded into every
caller's ``Model.version`` (cache-key law: an upgraded tool invalidates
exactly its own cached evidence, mirroring AD-19's pack-version fold).
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from typani.result import Err, Ok, Result

from regolith import procio
from regolith.logging_setup import get_logger
from regolith.procio import ToolArgs, ToolFailure, ToolOutput

_log = get_logger(__name__)

# frob:doc docs/modules/py-harness.md#models-hdl
VERILATOR_BIN = "verilator"
_VERSION_RE = re.compile(r"Verilator\s+(\S+)")


@lru_cache(maxsize=1)
# frob:doc docs/modules/py-harness.md#models-hdl
# frob:waive TEST001 reason="subprocess solve path, tested via pack integration tests"
def verilator_version() -> str:
    """The installed verilator's version string, e.g. ``5.047``.

    Cached per-process (the binary does not change mid-run); returns
    ``"unknown"`` if the binary is missing or the output is unparsable
    -- callers still fold this into their cache key, so "unknown" simply
    collapses caching rather than crashing (never an exception here:
    version resolution is diagnostic, not a discharge decision).
    """
    result = procio.run_argv(
        (VERILATOR_BIN, "--version"), timeout_s=30.0, tool=VERILATOR_BIN
    )
    if result.is_err:
        _log.warning(
            "verilator --version failed to run: %s", result.danger_err.stderr_excerpt
        )
        return "unknown"
    output = result.danger_ok
    text = output.stdout.decode("ascii", errors="replace") or output.stderr.decode(
        "ascii", errors="replace"
    )
    match = _VERSION_RE.search(text)
    if match is None:
        _log.warning("verilator --version output unparsable: %r", text)
        return "unknown"
    version = match.group(1)
    _log.info("resolved verilator version=%s", version)
    return version


# frob:doc docs/modules/py-harness.md#models-hdl
def run_verilator(
    args: ToolArgs,
    *,
    cwd: Path,
    timeout_s: float = 120.0,
) -> Result[ToolOutput, ToolFailure]:
    """Run ``verilator`` with ``args``' emitted argv in ``cwd``, through
    `regolith.procio.run_tool`; ``Err(ToolFailure)`` on any nonzero exit,
    missing binary, or timeout (AD-19: never an exception escapes this
    seam). The failure's ``version`` field is always the cached
    `verilator_version()` -- not just what `toolenv` could resolve
    without spawning -- matching this module's pre-seam behavior."""
    result = procio.run_tool("verilator", args, cwd=cwd, timeout_s=timeout_s)
    if result.is_err:
        fail = result.danger_err
        return Err(fail.model_copy(update={"version": verilator_version()}))
    return Ok(result.danger_ok.model_copy(update={"version": verilator_version()}))


__all__ = ["ToolFailure", "run_verilator", "verilator_version"]
