"""One logging configuration point for the whole toolchain (AD-8).

All log records go to STDERR; stdout is reserved for command output
(results, JSON) so a caller can pipe it cleanly. This adapts the house
logging reference for a compiler CLI, where stdout is the data channel.
Messages render plain, WARNING+ prefixed with the level name. Rust
``tracing`` events arrive here through the pyo3-log bridge under the
``regolith._core`` logger hierarchy, so they render identically to Python
records. Root level is read from ``REGOLITH_LOG`` (default ``INFO``).

This is a single module (not a subpackage) so the dictConfig payload
travels with the code and cannot go missing in an installed wheel.
"""

from __future__ import annotations

import logging
import logging.config
import os

_configured = False


class _LevelPrefixFormatter(logging.Formatter):
    """Plain message; WARNING+ prefixes the level name."""

    def __init__(self, show_level: bool = False) -> None:
        super().__init__()
        self._show_level = show_level

    def format(self, record: logging.LogRecord) -> str:
        msg = record.getMessage()
        if self._show_level or record.levelno >= logging.WARNING:
            return f"{record.levelname}: {msg}"
        return msg


def _config() -> dict[str, object]:
    fmt = f"{__name__}._LevelPrefixFormatter"
    level = os.environ.get("REGOLITH_LOG", "INFO").upper()
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {"stderr_fmt": {"()": fmt}},
        "handlers": {
            "stderr": {
                "class": "logging.StreamHandler",
                "formatter": "stderr_fmt",
                "stream": "ext://sys.stderr",
                "level": "DEBUG",
            },
        },
        "root": {"level": level, "handlers": ["stderr"]},
    }


def configure() -> None:
    """Apply the dictConfig exactly once (idempotent across imports)."""
    global _configured
    if _configured:
        return
    logging.config.dictConfig(_config())
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a module logger, configuring logging on first use."""
    configure()
    return logging.getLogger(name)
