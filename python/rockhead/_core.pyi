"""Typed stubs for the compiled ``rockhead._core`` extension (AD-2).

Hand-maintained and drift-checked against the PyO3 surface. WO-01
exposes only the smoke-test functions; WO-18 grows this alongside the
real boundary and adds the generated schema types.
"""

def core_version() -> str:
    """Return the compiler core version string."""
    ...

def init_logging() -> None:
    """Install the Rust->Python logging bridge (idempotent)."""
    ...
