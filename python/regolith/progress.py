"""The D228/D234.3 progress-event channel, producer half (WO-119).

A typed progress event -- phase, subject, done/total (or indeterminate),
elapsed seconds -- derived from the SAME instrumentation the D217/WO-107
log stream already carries. This is NOT a second bookkeeping system: an
emit site is an ordinary DEBUG log record on the dedicated
``regolith.progress`` logger (a child of root, so it flows through the
ONE stderr formatter/handler exactly like every other record -- visible
under ``-v``/``REGOLITH_LOG=DEBUG``, invisible and behavior-neutral at
the default level, per D228.2: presentation only, stdout untouched,
goldens byte-identical).

Two consumption modes over the SAME wire shape:

* in-process subscription (:func:`subscribe`) -- a `logging.Handler`
  filtered to records carrying a `progress_event` attribute, for a
  caller running regolith in the same process (a test, a future
  in-process host).
* subprocess stderr-stream parsing (:func:`parse_line`/:func:`parse_stream`)
  -- the graphite/editor mode: a consumer runs `regolith build --release`
  (or any long verb) as a subprocess with `-v`/`REGOLITH_LOG=DEBUG`,
  reads stderr line by line, and recovers the same :class:`ProgressEvent`
  sequence a Python subscriber would see in-process.

## Wire shape (STABLE, cite verbatim -- graphite WO-G5/WO-G7 and lithos
## WO-120 read this)

Each progress record renders as one line (ANSI, if any, must be
stripped before parsing -- :func:`parse_line` does this; wrapped below
only for this docstring's line length, always emitted as ONE line)::

    progress v=1 phase=<phase> subject=<subject>
        done=<done|-> total=<total|-> elapsed=<elapsed>

- ``v`` -- wire format version (int). Bump ``PROGRESS_WIRE_VERSION`` and
  document the change here on any incompatible change to this line
  shape; consumers key off ``v`` and may refuse an unknown version.
- ``phase`` -- a short stable phase tag (``fleet``, ``discharge``,
  ``ship``, ...). New phases may be added freely; existing tags are
  never renamed or repurposed without a version bump.
- ``subject`` -- the unit of work's identifier (a project name, an
  obligation ref, a backend family name). Free text with no internal
  whitespace (callers must not pass a subject containing spaces).
- ``done``/``total`` -- 1-based progress counters, or literal ``-`` for
  both when the phase is indeterminate (unknown total).
- ``elapsed`` -- seconds since the phase's :func:`start` call, formatted
  to 3 decimal places.

Nothing here replaces the D217 formatter or adds a parallel logging
config: :func:`log_progress` is a thin, single-home wrapper around the
ordinary ``logging.Logger.debug`` call, kept in ONE module so every
emit site shares the exact same wire shape (house rule: no duplication).
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager

from pydantic import BaseModel, ConfigDict

#: Bump on any incompatible change to the wire line shape (see module
#: docstring). Consumers read this field and may refuse an unknown value.
PROGRESS_WIRE_VERSION = 1

#: The dedicated logger progress events are emitted on. A child of root
#: (propagates normally through the ONE D217/WO-107 stderr handler), kept
#: separate from per-module loggers so :func:`subscribe` can raise ITS
#: level to DEBUG without turning on the whole toolchain's debug firehose.
PROGRESS_LOGGER_NAME = "regolith.progress"

_logger = logging.getLogger(PROGRESS_LOGGER_NAME)

# ANSI SGR escapes (color mode) must be stripped before the line regex is
# applied -- the same escapes `logging_setup` may have wrapped the message
# in (WO-107); this is the only place progress.py touches color.
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

_LINE_RE = re.compile(
    r"progress v=(?P<v>\d+) phase=(?P<phase>\S+) subject=(?P<subject>\S+) "
    r"done=(?P<done>-|\d+) total=(?P<total>-|\d+) elapsed=(?P<elapsed>[0-9.]+)"
)


class ProgressEvent(BaseModel):
    """One parsed progress record (the D228 typed event, WIRE_VERSION v1).

    ``done``/``total`` are both ``None`` for an indeterminate phase
    (unknown total); otherwise both are set. See the module docstring for
    the stability contract graphite/WO-120 depend on.
    """

    model_config = ConfigDict(frozen=True)

    v: int
    phase: str
    subject: str
    done: int | None
    total: int | None
    elapsed: float

    @property
    def indeterminate(self) -> bool:
        """True iff this phase carries no known total (done/total both None)."""
        return self.total is None


def start() -> float:
    """A monotonic start marker for a phase's elapsed-time accounting.

    Call once before a loop begins; pass the result to every
    :func:`log_progress` call in that loop as ``started``."""
    return time.monotonic()


def log_progress(
    *,
    phase: str,
    subject: str,
    done: int | None,
    total: int | None,
    started: float,
) -> None:
    """Emit ONE progress DEBUG record for ``subject`` in ``phase``.

    An ordinary `logging` call (house rule: additions only, never a
    parallel bookkeeping system) on the dedicated
    :data:`PROGRESS_LOGGER_NAME` logger, shaped per the module docstring
    so both consumption modes parse it identically. ``done``/``total``
    both ``None`` marks an indeterminate phase (``-`` on the wire).
    ``subject`` must not carry internal whitespace on the wire (the
    ``\\S+`` field); any is collapsed to ``_`` so a stray space can never
    corrupt the line shape.
    """
    elapsed = time.monotonic() - started
    subject = "_".join(subject.split()) if subject else subject
    done_s = "-" if done is None else str(done)
    total_s = "-" if total is None else str(total)
    event = ProgressEvent(
        v=PROGRESS_WIRE_VERSION,
        phase=phase,
        subject=subject,
        done=done,
        total=total,
        elapsed=elapsed,
    )
    _logger.debug(
        "progress v=%d phase=%s subject=%s done=%s total=%s elapsed=%.3f",
        PROGRESS_WIRE_VERSION,
        phase,
        subject,
        done_s,
        total_s,
        elapsed,
        extra={"progress_event": event},
    )


def parse_line(line: str) -> ProgressEvent | None:
    """Parse one stderr line into a :class:`ProgressEvent`, or ``None``.

    Strips ANSI color escapes first (WO-107 may have colorized the line),
    so this parses identically whether the captured stream came from a
    `--color always` or plain/non-TTY run. Lines that are not progress
    records (the overwhelming majority of the log stream) return ``None``
    -- callers filter, never raise, on ordinary log noise.
    """
    plain = _ANSI_RE.sub("", line)
    m = _LINE_RE.search(plain)
    if m is None:
        return None
    done = None if m.group("done") == "-" else int(m.group("done"))
    total = None if m.group("total") == "-" else int(m.group("total"))
    return ProgressEvent(
        v=int(m.group("v")),
        phase=m.group("phase"),
        subject=m.group("subject"),
        done=done,
        total=total,
        elapsed=float(m.group("elapsed")),
    )


def parse_stream(lines: Iterable[str]) -> Iterator[ProgressEvent]:
    """Parse a stderr stream (e.g. a subprocess's captured stderr, split
    into lines) into the :class:`ProgressEvent` sequence it carries,
    silently skipping every non-progress line."""
    for line in lines:
        event = parse_line(line)
        if event is not None:
            yield event


class _ProgressHandler(logging.Handler):
    """Forward every record carrying a ``progress_event`` to a callback.

    Non-progress records (the vast majority reaching this logger's
    ancestors) are ignored -- this handler never touches presentation."""

    def __init__(self, callback: Callable[[ProgressEvent], None]) -> None:
        super().__init__(level=logging.DEBUG)
        self._callback = callback

    def emit(self, record: logging.LogRecord) -> None:
        event = getattr(record, "progress_event", None)
        if isinstance(event, ProgressEvent):
            self._callback(event)


@contextmanager
def subscribe(callback: Callable[[ProgressEvent], None]) -> Iterator[None]:
    """In-process subscription: call ``callback`` for every progress event
    emitted (by any thread/loop) while this context is active.

    Temporarily raises the DEDICATED ``regolith.progress`` logger's level
    to DEBUG so events reach this handler regardless of the process's
    configured root verbosity -- scoped to this logger only (never the
    root/other module loggers), so a subscriber does not turn on the
    whole toolchain's debug firehose. Because the progress logger still
    propagates normally, a subscriber running at default color/verbosity
    may also see these lines land on the real stderr stream during the
    subscription window -- expected (house rule: presentation only,
    never a hidden channel), not a bug.
    """
    handler = _ProgressHandler(callback)
    prev_level = _logger.level
    _logger.setLevel(logging.DEBUG)
    _logger.addHandler(handler)
    try:
        yield
    finally:
        _logger.removeHandler(handler)
        _logger.setLevel(prev_level)
