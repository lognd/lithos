"""WO-107 (D217): the readable, colorized stderr log formatter.

Unit-level coverage of the ONE formatter and its filters -- color on/off,
hash abbreviation, newline escaping, width truncation, span demotion,
consecutive-duplicate collapse, and the loud verdict -- plus the invariant
that every noise reduction is reachable again under `-v`.
"""

from __future__ import annotations

import io
import logging
from collections.abc import Iterator

import pytest
from regolith import logging_setup as ls


@pytest.fixture(autouse=True)
def _reset_presentation() -> Iterator[None]:
    """Each test starts from plain, non-verbose, non-restage state."""
    ls.set_presentation(color=False, verbose=False)
    ls._restage_quiet = False
    yield
    ls.set_presentation(color=False, verbose=False)
    ls._restage_quiet = False


def _record(
    msg: str, *, level: int = logging.INFO, name: str = "regolith.orchestrator.x"
) -> logging.LogRecord:
    return logging.LogRecord(
        name=name,
        level=level,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=(),
        exc_info=None,
    )


def test_plain_info_is_message_only() -> None:
    out = ls._StderrLogFormatter().format(_record("hello world"))
    assert out == "hello world"
    assert "\x1b[" not in out


def test_plain_warning_is_level_prefixed() -> None:
    out = ls._StderrLogFormatter().format(_record("careful", level=logging.WARNING))
    assert out == "WARNING: careful"
    assert "\x1b[" not in out


def test_color_info_has_cyan_subsystem_prefix() -> None:
    ls.set_presentation(color=True, verbose=False)
    out = ls._StderrLogFormatter().format(
        _record("hi", name="regolith.harness.registry")
    )
    assert "\x1b[36m" in out  # cyan
    assert "harness.registry" in out


def test_color_error_and_warning_tags() -> None:
    ls.set_presentation(color=True, verbose=False)
    err = ls._StderrLogFormatter().format(_record("boom", level=logging.ERROR))
    warn = ls._StderrLogFormatter().format(_record("hmm", level=logging.WARNING))
    assert "\x1b[31m" in err and "error:" in err  # red
    assert "\x1b[33m" in warn and "warning:" in warn  # yellow


def test_hash_abbreviated_at_info_full_at_verbose() -> None:
    h = "463b13e3b94f0a97065f77219864aedbc209da0ee223e88bf7dae903c703e7a9"
    at_info = ls._StderrLogFormatter().format(_record(f"obligation {h} deferred"))
    assert h not in at_info
    assert h[:12] + ".." in at_info
    ls.set_presentation(color=False, verbose=True)
    at_v = ls._StderrLogFormatter().format(_record(f"obligation {h} deferred"))
    assert h in at_v


def test_newlines_escaped_to_single_line() -> None:
    out = ls._StderrLogFormatter().format(_record("bound line1\nline2\ttail"))
    assert "\n" not in out
    assert "line1\\nline2" in out


def test_wide_record_truncated_at_info_full_at_verbose() -> None:
    wide = "x" * (ls._MAX_WIDTH + 50)
    at_info = ls._StderrLogFormatter().format(_record(wide))
    assert len(at_info) == ls._MAX_WIDTH
    assert at_info.endswith("...")
    ls.set_presentation(color=False, verbose=True)
    at_v = ls._StderrLogFormatter().format(_record(wide))
    assert len(at_v) == len(wide)


def test_color_dims_kv_keys() -> None:
    ls.set_presentation(color=True, verbose=False)
    out = ls._StderrLogFormatter().format(_record("part=Foo binding=bar"))
    assert "\x1b[2m" in out  # dim
    assert "part" in out and "Foo" in out


def test_verdict_ok_is_bold_green() -> None:
    ls.set_presentation(color=True, verbose=False)
    rec = _record("build: clean", name="regolith.cli.app")
    rec.verdict = "ok"  # type: ignore[attr-defined]
    out = ls._StderrLogFormatter().format(rec)
    assert "\x1b[1m" in out and "\x1b[32m" in out  # bold + green
    assert "build: clean" in out


def test_verdict_bad_is_bold_red() -> None:
    ls.set_presentation(color=True, verbose=False)
    rec = _record("build: refused (3 unresolved)", name="regolith.cli.app")
    rec.verdict = "bad"  # type: ignore[attr-defined]
    out = ls._StderrLogFormatter().format(rec)
    assert "\x1b[1m" in out and "\x1b[31m" in out  # bold + red


def _run_handler(records: list[logging.LogRecord]) -> str:
    stream = io.StringIO()
    handler = ls._DedupStreamHandler(stream)
    handler.setFormatter(ls._StderrLogFormatter())
    for r in records:
        handler.emit(r)
    handler.flush()
    return stream.getvalue()


def test_consecutive_duplicates_collapse_with_count() -> None:
    recs = [_record("no model matched cost") for _ in range(3)]
    out = _run_handler(recs)
    assert out.count("no model matched cost") == 1
    assert "(x3)" in out


def test_verbose_disables_dedup() -> None:
    ls.set_presentation(color=False, verbose=True)
    recs = [_record("dup line") for _ in range(3)]
    out = _run_handler(recs)
    assert out.count("dup line") == 3
    assert "(x" not in out


def test_warning_bypasses_dedup_delay() -> None:
    """A WARNING is emitted immediately (never held pending), so it always
    reaches the stream even without an explicit later flush."""
    stream = io.StringIO()
    handler = ls._DedupStreamHandler(stream)
    handler.setFormatter(ls._StderrLogFormatter())
    handler.emit(_record("real problem", level=logging.WARNING))
    assert "real problem" in stream.getvalue()


def test_span_filter_hides_at_info_shows_at_debug() -> None:
    root = logging.getLogger()
    prev = root.level
    filt = ls._SpanDemoteFilter()
    span = _record("lower.lints;", name=ls.SPAN_LOGGER)
    try:
        root.setLevel(logging.INFO)
        assert filt.filter(span) is False
        root.setLevel(logging.DEBUG)
        assert filt.filter(span) is True
    finally:
        root.setLevel(prev)


def test_restage_filter_suppresses_info_but_keeps_warning() -> None:
    root = logging.getLogger()
    prev = root.level
    filt = ls._RestageQuietFilter()
    try:
        root.setLevel(logging.INFO)
        with ls.restage_quiet():
            assert filt.filter(_record("re-lower detail")) is False
            assert filt.filter(_record("bad", level=logging.WARNING)) is True
        # Outside the scope every record passes again.
        assert filt.filter(_record("normal")) is True
    finally:
        root.setLevel(prev)
