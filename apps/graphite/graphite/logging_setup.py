"""One logging configuration point for graphite (house rule: stdout is
data, all logs to stderr). Mirrors `regolith.logging_setup`'s shape but
lives in graphite's own distribution -- this package never imports
`regolith` internals beyond its public artifact-only surface, and logging
setup is cheap enough to not be worth sharing across the wheel boundary.
"""

from __future__ import annotations

import logging
import logging.config
import os

_configured = False


class _LevelPrefixFormatter(logging.Formatter):
    """Plain message; WARNING+ prefixes the level name."""

    def format(self, record: logging.LogRecord) -> str:
        msg = record.getMessage()
        if record.levelno >= logging.WARNING:
            return f"{record.levelname}: {msg}"
        return msg


def _config() -> dict[str, object]:
    fmt = f"{__name__}._LevelPrefixFormatter"
    level = os.environ.get("GRAPHITE_LOG", "INFO").upper()
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
    """The one entry point every graphite module uses instead of `print`."""
    configure()
    return logging.getLogger(name)
