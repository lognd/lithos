"""One logging configuration point for the whole toolchain (AD-8).

All log records go to STDERR; stdout is reserved for command output
(results, JSON) so a caller can pipe it cleanly. This adapts the house
logging reference for a compiler CLI, where stdout is the data channel.
Rust ``tracing`` events arrive here through the pyo3-log bridge under the
``regolith._core``/``regolith_*`` logger hierarchy (and span-enter records
under the ``tracing.span`` logger), so they render identically to Python
records. Root level is read from ``REGOLITH_LOG`` (default ``INFO``).

WO-107 (D217) makes the default stream readable at a glance: severity-
colored level tags, a cyan subsystem prefix, dimmed ``key=`` keys,
abbreviated content hashes, escaped newlines, width-truncated records,
demoted span-enter noise, collapsed consecutive duplicates, and a LOUD
final verdict. None of that deletes a record -- ``-v`` restores the full
verbatim firehose (full hashes, no truncation, no dedup, span records
back). Colorization is the ONLY color-gated layer; the noise reductions
apply in plain mode too, so ``NO_COLOR``/non-TTY output stays plain and
byte-stable while still being readable. The color DECISION is the ONE
D191.2 policy (`regolith.cli.color.resolve_color`), handed in by the CLI
edge -- never re-decided here.

This is a single module (not a subpackage) so the dictConfig payload
travels with the code and cannot go missing in an installed wheel.
"""

from __future__ import annotations

import logging
import logging.config
import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

_configured = False

# The ONE structural classifier for span-enter/exit records: pyo3-log
# routes `tracing` span records to a logger of exactly this name (the span
# path lands in the message as `<path>;`). Classifying by this target --
# not by a hard-coded list of span names that would drift as spans are
# added -- keeps the demotion correct for free (WO-107).
# frob:doc docs/modules/py-regolith.md#logging_setup
SPAN_LOGGER = "tracing.span"

# Content-address abbreviation: a run of >= this many lowercase-hex chars
# is a hash (obligation/content addresses are 64); abbreviate to the first
# `_HASH_KEEP` at INFO so hashes stop dominating every obligation line.
_HASH_MIN_LEN = 16
_HASH_KEEP = 12
_HASH_RE = re.compile(rf"[0-9a-f]{{{_HASH_MIN_LEN},}}")

# Records wider than this (after newline-escaping) are truncated at INFO;
# `-v` shows them in full. Chosen to fit a wide terminal line while cutting
# the multi-line embedded-source bounds that dump raw today (WO-107 sin 4).
_MAX_WIDTH = 240

# `key=` dimming: a bareword key immediately before `=` (not `==`).
_KV_KEY_RE = re.compile(r"(\b[A-Za-z_][A-Za-z0-9_.]*)=(?!=)")

# ANSI SGR codes -- the ONE place log ANSI is constructed (ASCII only).
_RESET = "\x1b[0m"
_DIM = "\x1b[2m"
_BOLD = "\x1b[1m"
_CYAN = "\x1b[36m"
_YELLOW = "\x1b[33m"
_RED = "\x1b[31m"
_GREEN = "\x1b[32m"


@dataclass
class _Presentation:
    """Late-bound stderr presentation state (set by the CLI edge).

    ``color`` gates ANSI only; ``verbose`` restores the full firehose
    (span records, full hashes, no truncation, no dedup). Both default off
    so library/test use and pre-callback imports stay plain and stable.
    """

    color: bool = False
    verbose: bool = False


_presentation = _Presentation()

# Set while a staged-build iteration > 1 re-lowers: the whole lower
# pipeline re-logs every iteration (sin 2). Within this scope, INFO/DEBUG
# re-lower detail is suppressed (WARNING+ and verdicts always pass, `-v`/
# DEBUG restores everything); the loop emits ONE INFO iteration header
# outside the scope.
_restage_quiet = False


@contextmanager
# frob:doc docs/modules/py-regolith.md#logging_setup
def restage_quiet() -> Iterator[None]:
    """Suppress the re-lower INFO/DEBUG firehose for a staged-build
    iteration > 1 (WO-107). WARNING+/verdict records still pass; `-v`
    (root DEBUG) restores the full detail."""
    global _restage_quiet
    prev = _restage_quiet
    _restage_quiet = True
    try:
        yield
    finally:
        _restage_quiet = prev


# frob:doc docs/modules/py-regolith.md#logging_setup
def set_presentation(*, color: bool, verbose: bool) -> None:
    """Late-bind the stderr color/verbosity decision (called once by the
    CLI callback, after `--color`/`-v` are parsed at the edge). Read live
    by the formatter/filters at emit time, so ordering vs. `configure()`
    never matters."""
    _presentation.color = color
    _presentation.verbose = verbose


def _subsystem(name: str) -> str:
    """The short, stable subsystem tag for a logger name (cyan prefix).

    Strips the `regolith.`/`regolith_` package noise so the eye lands on
    the meaningful leaf (`orchestrator.discharge`, `harness.registry`,
    `lower.lints`, `span`). Underscore package roots (`regolith_lower`)
    read as their dotted equivalent."""
    if name == SPAN_LOGGER:
        return "span"
    short = name
    for prefix in ("regolith._core.", "regolith._core", "regolith.", "regolith_"):
        if short.startswith(prefix):
            short = short[len(prefix) :]
            break
    return short or name


def _abbreviate_hashes(msg: str) -> str:
    """Replace every long hex run with its first `_HASH_KEEP` chars + `..`."""
    return _HASH_RE.sub(lambda m: m.group(0)[:_HASH_KEEP] + "..", msg)


def _dim_keys(msg: str) -> str:
    """Dim every `key=` key so the eye lands on the values (color only)."""
    return _KV_KEY_RE.sub(lambda m: f"{_DIM}{m.group(1)}{_RESET}=", msg)


class _StderrLogFormatter(logging.Formatter):
    """The one stderr log formatter (Python + pyo3-log records alike).

    Noise reduction (newline-escape, hash-abbrev, width-truncate) is
    verbosity-driven and applies in plain mode too; colorization (level
    tag, cyan subsystem, dim keys, loud verdict) is the only color-gated
    layer. Records carrying a ``verdict`` attribute (``"ok"``/``"bad"``,
    set by :func:`log_verdict`) render LOUD."""

    # frob:doc docs/modules/py-regolith.md#logging_setup
    def format(self, record: logging.LogRecord) -> str:
        verbose = _presentation.verbose
        color = _presentation.color

        msg = record.getMessage()
        # Newline-escape ALWAYS: a multi-line bound must not fan a single
        # record across many terminal lines (sin 4). ASCII escapes only.
        msg = msg.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r")
        if not verbose:
            msg = _abbreviate_hashes(msg)
            if len(msg) > _MAX_WIDTH:
                msg = msg[: _MAX_WIDTH - 3] + "..."

        verdict = getattr(record, "verdict", None)

        if not color:
            # Plain mode: stable, close to today -- message only, WARNING+
            # prefixed with the level name (verdicts included, uncolored).
            if record.levelno >= logging.WARNING:
                return f"{record.levelname}: {msg}"
            return msg

        msg = _dim_keys(msg)
        prefix = f"{_CYAN}{_subsystem(record.name)}{_RESET} "

        if verdict == "ok":
            return f"{prefix}{_BOLD}{_GREEN}{msg}{_RESET}"
        if verdict == "bad":
            return f"{prefix}{_BOLD}{_RED}{msg}{_RESET}"
        if record.levelno >= logging.ERROR:
            return f"{prefix}{_RED}error:{_RESET} {msg}"
        if record.levelno >= logging.WARNING:
            return f"{prefix}{_YELLOW}warning:{_RESET} {msg}"
        if record.levelno <= logging.DEBUG:
            return f"{prefix}{_DIM}{msg}{_RESET}"
        return f"{prefix}{msg}"


class _SpanDemoteFilter(logging.Filter):
    """Demote span-enter/exit records (`tracing.span`) to DEBUG.

    House rule: never DELETE a log site. Span records arrive at INFO, so
    they pass the root level; this suppresses them UNLESS the effective
    root level is DEBUG -- so both ``-v`` and ``REGOLITH_LOG=DEBUG``
    restore every one, exactly as if they were emitted at DEBUG.
    Structural: keyed on the logger name, not a drift-prone span-name list
    (see `SPAN_LOGGER`)."""

    # frob:doc docs/modules/py-regolith.md#logging_setup
    def filter(self, record: logging.LogRecord) -> bool:
        if record.name != SPAN_LOGGER:
            return True
        return logging.getLogger().getEffectiveLevel() <= logging.DEBUG


class _RestageQuietFilter(logging.Filter):
    """Suppress the staged-build re-lower firehose for iteration > 1.

    Active only inside :func:`restage_quiet`. WARNING+ and verdict records
    always pass (a real problem must never be hidden); everything else is
    suppressed unless the effective root level is DEBUG (`-v` restores the
    full re-lower detail, house rule: never delete a record)."""

    # frob:doc docs/modules/py-regolith.md#logging_setup
    def filter(self, record: logging.LogRecord) -> bool:
        if not _restage_quiet:
            return True
        if record.levelno >= logging.WARNING:
            return True
        if getattr(record, "verdict", None) is not None:
            return True
        return logging.getLogger().getEffectiveLevel() <= logging.DEBUG


class _DedupStreamHandler(logging.StreamHandler):  # type: ignore[type-arg]
    """Collapse consecutive exact-duplicate records to one `(xN)` line.

    The same deferral/no-model record prints 2-4x per obligation today
    (sin 2); identical adjacent records fold into a single line with an
    `(xN)` suffix. Disabled under `-v` (every record restored) and
    bypassed for WARNING+ / verdict records so an important line -- above
    all the final verdict -- is emitted immediately, never held pending."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self._pending: logging.LogRecord | None = None
        self._pending_key: tuple[str, int, str] | None = None
        self._count = 0

    def _emit_pending(self) -> None:
        if self._pending is None:
            return
        record, count = self._pending, self._count
        self._pending = self._pending_key = None
        self._count = 0
        if count > 1:
            record.msg = f"{record.getMessage()} (x{count})"
            record.args = None
        super().emit(record)

    # frob:doc docs/modules/py-regolith.md#logging_setup
    def emit(self, record: logging.LogRecord) -> None:
        # Loud/important records and `-v` bypass dedup entirely: flush any
        # pending run first, then emit immediately (no delay).
        if (
            _presentation.verbose
            or record.levelno >= logging.WARNING
            or getattr(record, "verdict", None) is not None
        ):
            self._emit_pending()
            super().emit(record)
            return
        key = (record.name, record.levelno, record.getMessage())
        if key == self._pending_key:
            self._count += 1
            return
        self._emit_pending()
        self._pending = record
        self._pending_key = key
        self._count = 1

    # frob:doc docs/modules/py-regolith.md#logging_setup
    def flush(self) -> None:
        self._emit_pending()
        super().flush()

    # frob:doc docs/modules/py-regolith.md#logging_setup
    def close(self) -> None:
        self._emit_pending()
        super().close()


# frob:doc docs/modules/py-regolith.md#logging_setup
# frob:waive TEST001 reason="logging bootstrap wrapper, tested via dictConfig"
def log_verdict(logger: logging.Logger, ok: bool, message: str) -> None:
    """Emit a build/check verdict LOUD (green when ok, red otherwise).

    The final verdict must not render at the same weight as every phase
    line (sin 5). Tagged (`verdict=ok|bad`) so the ONE formatter colors it
    and the dedup handler emits it immediately; plain mode still shows the
    message verbatim."""
    logger.info(message, extra={"verdict": "ok" if ok else "bad"})


def _config() -> dict[str, object]:
    fmt = f"{__name__}._StderrLogFormatter"
    handler_cls = f"{__name__}._DedupStreamHandler"
    span_filter = f"{__name__}._SpanDemoteFilter"
    restage_filter = f"{__name__}._RestageQuietFilter"
    level = os.environ.get("REGOLITH_LOG", "INFO").upper()
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {"stderr_fmt": {"()": fmt}},
        "filters": {
            "span_demote": {"()": span_filter},
            "restage_quiet": {"()": restage_filter},
        },
        "handlers": {
            "stderr": {
                "class": handler_cls,
                "formatter": "stderr_fmt",
                "filters": ["span_demote", "restage_quiet"],
                "stream": "ext://sys.stderr",
                "level": "DEBUG",
            },
        },
        "root": {"level": level, "handlers": ["stderr"]},
    }


# frob:doc docs/modules/py-regolith.md#logging_setup
# frob:waive TEST001 reason="logging bootstrap wrapper, tested via dictConfig"
def configure() -> None:
    """Apply the dictConfig exactly once (idempotent across imports)."""
    global _configured
    if _configured:
        return
    logging.config.dictConfig(_config())
    _configured = True


# frob:doc docs/modules/py-regolith.md#logging_setup
# frob:waive TEST001 reason="logging bootstrap wrapper, tested via dictConfig"
def set_level(level: int) -> None:
    """Override the root log level at the CLI edge (`-v`/`-q`).

    Explicit flags win over ``REGOLITH_LOG`` and the default (D163
    precedence: CLI flag strongest). Configures logging first so the root
    handler exists."""
    configure()
    logging.getLogger().setLevel(level)


# frob:doc docs/modules/py-regolith.md#logging_setup
# frob:waive TEST001 reason="logging bootstrap wrapper, tested via dictConfig"
def get_logger(name: str) -> logging.Logger:
    """Return a module logger, configuring logging on first use."""
    configure()
    return logging.getLogger(name)
