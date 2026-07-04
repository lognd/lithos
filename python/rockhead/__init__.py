"""The rockhead engineering toolchain (hematite + cuprite).

Public Python surface. The compiled compiler core lives in the
``rockhead._core`` extension and is reached only through
:mod:`rockhead.compiler` (AD-4). Logging is configured on first import via
:func:`rockhead.logging_setup.configure`.
"""

from __future__ import annotations

from rockhead.compiler import core_version
from rockhead.logging_setup import configure as _configure_logging

_configure_logging()

__all__ = ["core_version"]
