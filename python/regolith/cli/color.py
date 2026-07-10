"""The one CLI color-decision seam (owner directive: optional ANSI
colors when the terminal supports them).

Color is decided at the EDGE, never in the renderer (`regolith-diag`
stays the ONE renderer, AD-7; it only accepts a bool switch). This
module implements the `auto` policy -- isatty on the stream diagnostics
are actually printed to (stdout, per the house "stdout is data" rule:
rendered diagnostics are `check`/`build`'s command output, not a log
line) AND no `NO_COLOR` env var AND `TERM` is not `dumb` -- with
`always`/`never` as explicit overrides that win outright. NO_COLOR
(https://no-color.org) beats `auto` but loses to an explicit
`--color always`.
"""

from __future__ import annotations

import os
from typing import IO, Literal

from regolith.logging_setup import get_logger

_log = get_logger(__name__)

ColorChoice = Literal["auto", "always", "never"]


def resolve_color(choice: ColorChoice, stream: IO[str]) -> bool:
    """Resolve the `--color [auto|always|never]` choice to a bool.

    `always`/`never` are unconditional. `auto` colors only when `stream`
    is a real terminal, `NO_COLOR` is unset (any value counts per the
    spec), and `TERM` is not `dumb`. Logged at debug so a confused CI
    run is diagnosable without re-running.
    """
    if choice == "always":
        enabled = True
    elif choice == "never":
        enabled = False
    else:
        is_tty = stream.isatty()
        no_color = "NO_COLOR" in os.environ
        dumb_term = os.environ.get("TERM") == "dumb"
        enabled = is_tty and not no_color and not dumb_term
        _log.debug(
            "color: auto-detect isatty=%s no_color=%s term=%s -> %s",
            is_tty,
            no_color,
            os.environ.get("TERM"),
            enabled,
        )
    _log.debug("color: choice=%s resolved=%s", choice, enabled)
    return enabled
