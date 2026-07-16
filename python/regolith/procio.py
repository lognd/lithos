"""The ONE process-invocation seam (WO-153, D264 ruling 1).

Design precedent: ``../lograder``'s process module (``TypedExecutable``/
``CLIArgs``) proved two ideas worth adopting -- typed-argv models instead
of hand-built flag lists, and invocation-as-data (every spawn logged as a
structured packet). This module adopts BOTH ideas fresh, in house idiom,
without depending on or vendoring lograder: typani ``Result`` everywhere
(lograder vendors its own), no auto-install (`regolith.toolenv`'s
honest-absence + teaching-message posture, never a host mutation), no
ambient global config (every parameter threaded explicitly).

The shape it generalizes is `regolith.harness.adapter.solve_via_subprocess`
(AD-19): JSON envelope in, one pydantic-validated document out, stderr as
logs, an explicit timeout, typed failure values, never a bare exception.
That contract stays untouched at its own call site (only its spawn moves
onto this seam) -- this module gives every OTHER tool invocation the same
discipline instead of three restatements of it.

Three layers:

- :func:`run_argv`: the raw spawn primitive. Any already-resolved argv,
  MANDATORY explicit timeout, captured stdout/stderr/returncode. A
  nonzero exit is NOT an error here -- callers with their own exit-code
  semantics (AD-19's adapter, the layout wrapper) need the raw
  :class:`ToolOutput` to decide. Only not-found/timeout are infrastructure
  failures at this layer.
- :func:`run_tool`: the toolenv-resolved wrapper. Resolves ``name``
  through `regolith.toolenv.resolve` (missing binary -> :class:`ToolFailure`
  carrying the EXISTING teaching message verbatim, never an auto-install
  attempt), spawns the typed :class:`ToolArgs`' emitted argv, and ALSO
  treats a nonzero exit as a :class:`ToolFailure` (the generalized
  one-shot-pass-fail shape most tool verbs -- verilator, kicad-cli --
  actually want).
- :func:`expect_json`: validates a :class:`ToolOutput`'s stdout as a given
  pydantic model, wrapping a ``ValidationError`` into :class:`ToolFailure`
  rather than letting it escape.

:func:`legacy_bytes_runner` is a compatibility shim for the two call
sites (`regolith.toolenv.resolve`'s version probe, `regolith.realizer.
elec.kicad.run_layout`'s default runner) that were built around an
injectable ``runner`` callable matching ``subprocess.run``'s own contract
(bytes-mode ``CompletedProcess``, ``check=False`` semantics: a nonzero
exit is returned, never raised) -- swapping ONLY this default value
routes their real (non-test, non-fake) spawn through this seam without
touching either function's own body or its test-injected fakes.
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError
from typani.result import Err, Ok, Result

from regolith.logging_setup import get_logger

_log = get_logger(__name__)

_STDERR_EXCERPT_LINES = 40


def _excerpt(text: str, *, lines: int = _STDERR_EXCERPT_LINES) -> str:
    """Bound a stderr/stdout blob to its last N lines (the useful end --
    the fatal diagnostic -- without an unbounded evidence payload)."""
    parts = text.splitlines()
    if len(parts) <= lines:
        return text
    return "\n".join(["...(truncated)...", *parts[-lines:]])


class ToolArgs(BaseModel):
    """Frozen base for one (tool, verb)'s typed argument model.

    Every subclass's :meth:`emit` returns the flag/positional argv for
    that verb -- no call site concatenates raw flag strings after this
    module lands (WO-153 deliverable 1)."""

    model_config = ConfigDict(frozen=True)

    def emit(self) -> tuple[str, ...]:
        """The argv this verb contributes (excluding the binary itself)."""
        raise NotImplementedError


class VerilatorLintArgs(ToolArgs):
    """``verilator --lint-only ...`` (the `hdl.build` verb, D202)."""

    filename: str
    is_sv: bool = False

    def emit(self) -> tuple[str, ...]:
        """`--lint-only -Wall -Wno-DECLFILENAME --timing [-sv] <filename>`."""
        argv = ["--lint-only", "-Wall", "-Wno-DECLFILENAME", "--timing"]
        if self.is_sv:
            argv.append("-sv")
        argv.append(self.filename)
        return tuple(argv)


class VerilatorBinaryArgs(ToolArgs):
    """``verilator --binary ...`` (the `hdl.sim_assert` testbench build)."""

    top_module: str
    tb_filename: str
    hdl_filename: str
    mdir: str = "obj_dir"

    def emit(self) -> tuple[str, ...]:
        """`--binary -Wno-fatal --timing -O2 --top-module <m> --Mdir <d> ...`."""
        return (
            "--binary",
            "-Wno-fatal",
            "--timing",
            "-O2",
            "--top-module",
            self.top_module,
            "--Mdir",
            self.mdir,
            self.tb_filename,
            self.hdl_filename,
        )


class KicadDrcArgs(ToolArgs):
    """``kicad-cli pcb drc ...`` (the layout-wrapper DRC verb)."""

    output_path: str
    pcb_path: str

    def emit(self) -> tuple[str, ...]:
        """`pcb drc --format json --severity-error --output <r> <pcb>`."""
        return (
            "pcb",
            "drc",
            "--format",
            "json",
            "--severity-error",
            "--output",
            self.output_path,
            self.pcb_path,
        )


class KicadLayoutArgs(ToolArgs):
    """``python -m regolith.realizer.elec.kicad_wrapper`` (the real
    layout wrapper's own argv, spawned under the CURRENT interpreter --
    not a toolenv-catalogued external tool, see `kicad.real_wrapper_argv`).
    """

    module: str = "regolith.realizer.elec.kicad_wrapper"

    def emit(self) -> tuple[str, ...]:
        """`-m <module>`."""
        return ("-m", self.module)


class ToolOutput(BaseModel):
    """One completed invocation's captured result (any returncode)."""

    model_config = ConfigDict(frozen=True)

    tool: str
    argv: tuple[str, ...]
    returncode: int
    stdout: bytes = b""
    stderr: bytes = b""
    version: str | None = None


class ToolFailure(BaseModel):
    """One tool invocation that could not be run to a usable result.

    Generalizes the shape every restated failure type in this repo
    already carried (verilator_adapter's `ToolFailure`, kicad's
    `ToolUnavailable`/`LayoutFailed` where their semantics coincide):
    tool name, resolved version if known, argv, returncode (``None`` for
    not-found/timeout), a BOUNDED stderr excerpt, and the failure kind.
    """

    model_config = ConfigDict(frozen=True)

    tool: str
    version: str | None = None
    argv: tuple[str, ...]
    returncode: int | None
    stderr_excerpt: str
    kind: Literal["not_found", "timeout", "nonzero"]


def run_argv(
    argv: Sequence[str],
    *,
    cwd: Path | None = None,
    stdin: bytes = b"",
    timeout_s: float,
    tool: str = "",
    version: str | None = None,
) -> Result[ToolOutput, ToolFailure]:
    """Spawn an already-resolved ``argv`` (invocation-as-data): MANDATORY
    explicit ``timeout_s`` (no default-``None`` overload exists), every
    invocation DEBUG-logged (argv, cwd, resolved version, returncode).

    A nonzero exit is NOT a failure at this layer -- ``Ok(ToolOutput)``
    covers every returncode the process itself reported; only spawn
    failure (missing binary/OSError) and timeout are :class:`ToolFailure`
    here, so a caller with its own exit-code semantics (the AD-19
    adapter, the layout wrapper) can still inspect the raw result.
    """
    full_argv = tuple(argv)
    label = tool or (full_argv[0] if full_argv else "")
    _log.debug(
        "procio: spawning %s (cwd=%s, timeout=%gs, version=%s)",
        full_argv,
        cwd,
        timeout_s,
        version,
    )
    try:
        completed = subprocess.run(
            list(full_argv),
            cwd=str(cwd) if cwd is not None else None,
            input=stdin,
            capture_output=True,
            timeout=timeout_s,
            check=False,
        )
    except FileNotFoundError as exc:
        _log.warning("procio: %s not found: %s", label, exc)
        return Err(
            ToolFailure(
                tool=label,
                version=version,
                argv=full_argv,
                returncode=None,
                kind="not_found",
                stderr_excerpt=str(exc),
            )
        )
    except OSError as exc:
        _log.warning("procio: %s failed to spawn: %s", label, exc)
        return Err(
            ToolFailure(
                tool=label,
                version=version,
                argv=full_argv,
                returncode=None,
                kind="not_found",
                stderr_excerpt=str(exc),
            )
        )
    except subprocess.TimeoutExpired as exc:
        raw_stderr = exc.stderr
        if isinstance(raw_stderr, bytes):
            text = raw_stderr.decode("ascii", errors="replace")
        else:
            text = raw_stderr or ""
        _log.warning("procio: %s timed out after %gs", label, timeout_s)
        return Err(
            ToolFailure(
                tool=label,
                version=version,
                argv=full_argv,
                returncode=None,
                kind="timeout",
                stderr_excerpt=_excerpt(f"timed out after {timeout_s}s\n{text}"),
            )
        )
    _log.debug(
        "procio: %s -> returncode=%d (argv=%s)", label, completed.returncode, full_argv
    )
    return Ok(
        ToolOutput(
            tool=label,
            argv=full_argv,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            version=version,
        )
    )


def run_tool(
    name: str,
    args: ToolArgs,
    *,
    cwd: Path,
    stdin: bytes = b"",
    timeout_s: float,
) -> Result[ToolOutput, ToolFailure]:
    """Resolve ``name`` through `regolith.toolenv`, spawn ``args.emit()``,
    and treat a nonzero exit as a :class:`ToolFailure` too (the
    generalized "one shot, pass or fail" shape verilator/kicad-cli verbs
    want -- unlike :func:`run_argv`, which leaves exit-code
    interpretation to callers with a richer protocol, e.g. AD-19's
    adapter or the layout wrapper).

    A missing binary is resolved BEFORE any spawn attempt (toolenv's own
    cache) and produces a :class:`ToolFailure` carrying the tool's
    EXISTING teaching message verbatim -- never an auto-install attempt.
    """
    # Lazy import: `regolith.toolenv` calls back into this module for its
    # own version-probe internals (`legacy_bytes_runner`), so a top-level
    # import here would be circular.
    from regolith.toolenv import resolve as resolve_tool

    status = resolve_tool(name, probe_version=False)
    if status.path is None:
        message = status.teaching_message(needed_for=f"the {name} invocation")
        _log.warning("procio: %s unavailable: %s", name, message)
        return Err(
            ToolFailure(
                tool=name,
                version=None,
                argv=(),
                returncode=None,
                kind="not_found",
                stderr_excerpt=message,
            )
        )
    full_argv = (status.path, *args.emit())
    spawned = run_argv(
        full_argv,
        cwd=cwd,
        stdin=stdin,
        timeout_s=timeout_s,
        tool=name,
        version=status.version,
    )
    if spawned.is_err:
        return spawned
    output = spawned.danger_ok
    if output.returncode != 0:
        _log.info(
            "procio: %s failed: argv=%s returncode=%d",
            name,
            full_argv,
            output.returncode,
        )
        text = output.stderr.decode("ascii", errors="replace") or output.stdout.decode(
            "ascii", errors="replace"
        )
        return Err(
            ToolFailure(
                tool=name,
                version=output.version,
                argv=output.argv,
                returncode=output.returncode,
                kind="nonzero",
                stderr_excerpt=_excerpt(text),
            )
        )
    return Ok(output)


def expect_json[M: BaseModel](
    output: ToolOutput, model: type[M]
) -> Result[M, ToolFailure]:
    """Validate ``output.stdout`` as ``model``; a malformed document is a
    :class:`ToolFailure` (kind ``"nonzero"`` -- the process itself may
    have exited 0 while still speaking garbage), never a raised
    ``ValidationError``."""
    try:
        parsed = model.model_validate_json(output.stdout)
    except ValidationError as exc:
        _log.warning(
            "procio: %s stdout is not a valid %s: %s", output.tool, model.__name__, exc
        )
        return Err(
            ToolFailure(
                tool=output.tool,
                version=output.version,
                argv=output.argv,
                returncode=output.returncode,
                kind="nonzero",
                stderr_excerpt=_excerpt(str(exc)),
            )
        )
    return Ok(parsed)


def legacy_bytes_runner(
    argv: Sequence[str],
    *,
    input: bytes = b"",  # noqa: A002 -- matches subprocess.run's own kwarg name
    capture_output: bool = True,
    timeout: float,
    check: bool = False,
) -> subprocess.CompletedProcess[bytes]:
    """Default-value shim matching `subprocess.run`'s own call contract
    (bytes-mode, ``check=False`` never raises on a nonzero exit) --
    swapping ONLY a caller's default ``runner=`` parameter to this
    function routes its REAL (non-injected, non-test, non-fake) spawn
    through :func:`run_argv` without touching the caller's own body or
    any test/fake ``runner`` it still accepts (`regolith.toolenv.resolve`'s
    version probe, `regolith.realizer.elec.kicad.run_layout`'s default)."""
    del capture_output, check
    result = run_argv(argv, stdin=input, timeout_s=timeout)
    if result.is_ok:
        out = result.danger_ok
        return subprocess.CompletedProcess(
            args=list(argv),
            returncode=out.returncode,
            stdout=out.stdout,
            stderr=out.stderr,
        )
    fail = result.danger_err
    if fail.kind == "timeout":
        raise subprocess.TimeoutExpired(cmd=list(argv), timeout=timeout)
    raise FileNotFoundError(fail.stderr_excerpt)


__all__ = [
    "KicadDrcArgs",
    "KicadLayoutArgs",
    "ToolArgs",
    "ToolFailure",
    "ToolOutput",
    "VerilatorBinaryArgs",
    "VerilatorLintArgs",
    "expect_json",
    "legacy_bytes_runner",
    "run_argv",
    "run_tool",
]
