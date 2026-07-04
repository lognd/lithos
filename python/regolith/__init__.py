"""The regolith engineering toolchain (hematite + cuprite).

Public Python surface. The compiled compiler core lives in the
``regolith._core`` extension and is reached only through
:mod:`regolith.compiler` (AD-4). Logging is configured on first import via
:func:`regolith.logging_setup.configure`.
"""

from __future__ import annotations

from regolith.compiler import core_version
from regolith.logging_setup import configure as _configure_logging

_configure_logging()

__all__ = ["core_version"]
