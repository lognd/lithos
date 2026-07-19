"""WO-119 (D228/D234.3): the progress-event channel, producer half.

Covers both consumption modes over the SAME wire shape (module docstring
of :mod:`regolith.progress`):

* in-process subscription -- ``log_progress`` -> ``subscribe`` callback.
* subprocess stderr-stream parsing -- ``parse_line``/``parse_stream`` over
  a REAL captured stream (``tests/fixtures/progress/discharge_stream.txt``,
  a verbatim excerpt of ``regolith build --release`` stderr on the
  ``timber_pavilion`` fleet project with ``REGOLITH_LOG=DEBUG``).

Plus the determinism/behavior proof: emitting progress records never
touches stdout, and the color/plain formatter renders them exactly like
any other DEBUG record (WO-107) -- no new presentation layer.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

import pytest
from regolith import logging_setup as ls
from regolith import progress as pr

FIXTURE = Path(__file__).parent / "fixtures" / "progress" / "discharge_stream.txt"


@pytest.fixture(autouse=True)
def _reset_progress_logger() -> Iterator[None]:
    """Each test starts with the dedicated progress logger at NOTSET.

    Also flushes root's handlers on teardown: the WO-107 dedup handler
    holds a single un-duplicated record pending until the next record (or
    an explicit flush); left pending across a `capsys`-scoped test it
    would otherwise only flush at interpreter shutdown, against an
    already-restored stream (a pre-existing dedup-handler property, not a
    progress.py behavior) -- flush here so no test leaves that dangling.
    """
    logger = logging.getLogger(pr.PROGRESS_LOGGER_NAME)
    prev = logger.level
    logger.setLevel(logging.NOTSET)
    yield
    logger.setLevel(prev)
    for handler in logging.getLogger().handlers:
        handler.flush()


def test_log_progress_emits_parseable_line(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG, logger=pr.PROGRESS_LOGGER_NAME):
        started = pr.start()
        pr.log_progress(
            phase="discharge", subject="abc123", done=3, total=10, started=started
        )
    assert len(caplog.records) == 1
    record = caplog.records[0]
    event = record.progress_event  # ty: ignore[unresolved-attribute] -- progress_event is attached to LogRecord dynamically by the progress logging adapter, never declared on stdlib LogRecord
    assert isinstance(event, pr.ProgressEvent)
    assert event.v == pr.PROGRESS_WIRE_VERSION
    assert event.phase == "discharge"
    assert event.subject == "abc123"
    assert event.done == 3
    assert event.total == 10
    assert event.elapsed >= 0.0
    assert not event.indeterminate

    parsed = pr.parse_line(record.getMessage())
    assert parsed is not None
    assert parsed.v == pr.PROGRESS_WIRE_VERSION
    assert parsed.phase == "discharge"
    assert parsed.subject == "abc123"
    assert parsed.done == 3
    assert parsed.total == 10
    assert parsed.elapsed == pytest.approx(event.elapsed, abs=1e-3)


def test_log_progress_subject_whitespace_is_collapsed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.DEBUG, logger=pr.PROGRESS_LOGGER_NAME):
        pr.log_progress(
            phase="ship",
            subject="two words",
            done=1,
            total=1,
            started=pr.start(),
        )
    event = caplog.records[0].progress_event  # ty: ignore[unresolved-attribute] -- progress_event is attached to LogRecord dynamically by the progress logging adapter, never declared on stdlib LogRecord
    assert event.subject == "two_words"
    assert pr.parse_line(caplog.records[0].getMessage()) is not None


def test_indeterminate_event_round_trips(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG, logger=pr.PROGRESS_LOGGER_NAME):
        pr.log_progress(
            phase="scan", subject="x", done=None, total=None, started=pr.start()
        )
    event = caplog.records[0].progress_event  # ty: ignore[unresolved-attribute] -- progress_event is attached to LogRecord dynamically by the progress logging adapter, never declared on stdlib LogRecord
    assert event.indeterminate
    parsed = pr.parse_line(caplog.records[0].getMessage())
    assert parsed is not None
    assert parsed.done is None
    assert parsed.total is None
    assert parsed.indeterminate


def test_parse_line_ignores_ordinary_log_noise() -> None:
    assert pr.parse_line("build: 1 file(s) tier=RELEASE profile=None") is None
    assert pr.parse_line("registered model buck_output_ripple_ccm@1") is None


# frob:tests python/regolith/logging_setup.py::set_presentation
def test_parse_line_strips_ansi_color() -> None:
    ls.set_presentation(color=True, verbose=False)
    try:
        formatted = ls._StderrLogFormatter().format(
            logging.LogRecord(
                name=pr.PROGRESS_LOGGER_NAME,
                level=logging.DEBUG,
                pathname=__file__,
                lineno=1,
                msg=(
                    "progress v=1 phase=fleet subject=cnc_router_r1 "
                    "done=2 total=15 elapsed=1.250"
                ),
                args=(),
                exc_info=None,
            )
        )
        assert "\x1b[" in formatted  # color mode did wrap it
        parsed = pr.parse_line(formatted)
        assert parsed is not None
        assert parsed.phase == "fleet"
        assert parsed.subject == "cnc_router_r1"
        assert parsed.done == 2
        assert parsed.total == 15
        assert parsed.elapsed == pytest.approx(1.250)
    finally:
        ls.set_presentation(color=False, verbose=False)


def test_subscribe_in_process_receives_events() -> None:
    received: list[pr.ProgressEvent] = []
    with pr.subscribe(received.append):
        pr.log_progress(
            phase="discharge", subject="a", done=1, total=3, started=pr.start()
        )
        pr.log_progress(
            phase="discharge", subject="b", done=2, total=3, started=pr.start()
        )
    assert [e.subject for e in received] == ["a", "b"]

    # After the context exits, the logger's level is restored -- an event
    # emitted at default verbosity is no longer delivered to a dead handler
    # (nothing left listening; this just proves the context is scoped).
    received.clear()
    pr.log_progress(phase="discharge", subject="c", done=3, total=3, started=pr.start())
    assert received == []


def test_subscribe_does_not_touch_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    events: list[pr.ProgressEvent] = []
    with pr.subscribe(events.append):
        pr.log_progress(phase="ship", subject="x", done=1, total=1, started=pr.start())
    out, _err = capsys.readouterr()
    assert out == ""
    assert len(events) == 1


def test_parse_stream_over_real_captured_fleet_build() -> None:
    """Subprocess mode: a REAL stderr excerpt from `regolith build
    --release` on the timber_pavilion fleet project (REGOLITH_LOG=DEBUG),
    captured verbatim -- not synthesized."""
    lines = FIXTURE.read_text().splitlines()
    events = list(pr.parse_stream(lines))
    assert len(events) == 10
    assert [e.phase for e in events] == ["discharge"] * 10
    assert [e.done for e in events] == list(range(1, 11))
    assert all(e.total == 10 for e in events)
    assert all(e.v == pr.PROGRESS_WIRE_VERSION for e in events)
    # Monotonically non-decreasing elapsed within one phase run.
    elapsed = [e.elapsed for e in events]
    assert elapsed == sorted(elapsed)


def test_parse_stream_skips_non_progress_lines_in_real_stream() -> None:
    lines = FIXTURE.read_text().splitlines()
    non_progress = [line for line in lines if not line.startswith("progress ")]
    assert non_progress  # the fixture carries real surrounding context
    assert list(pr.parse_stream(non_progress)) == []
