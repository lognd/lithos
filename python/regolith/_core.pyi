"""Typed stubs for the compiled ``regolith._core`` extension (AD-2).

Hand-maintained and drift-checked against the PyO3 surface (WO-18). A
failing build is a ``BuildOutput`` with error diagnostics, never an
exception; only ``CoreBug`` (a Rust panic) and ``CoreError`` (an
infrastructure failure) are raised.
"""

class CoreBug(Exception):
    """A Rust panic that crossed the boundary (unrecoverable programmer bug)."""

class CoreError(Exception):
    """An infrastructure failure at the core boundary (unreadable file, cache)."""

class BuildOutput:
    """An opaque handle to a completed build's diagnostics and payload."""

    def rendered(self, ansi: bool) -> str:
        """The diagnostics rendered to text (the one renderer)."""
        ...

    def payload_json(self) -> bytes:
        """The structured payload as JSON bytes (parses into pydantic)."""
        ...

    def ok(self) -> bool:
        """True when the build produced no error-severity diagnostics."""
        ...

    def diagnostic_count(self) -> int:
        """The number of diagnostics in the build."""
        ...

class CoreSession:
    """A compile session over a set of source paths."""

    def __init__(self, paths: list[str]) -> None: ...
    def check(self) -> BuildOutput:
        """Run the static ``check`` pipeline (GIL released)."""
        ...

    def compile(self, registry_version: str) -> BuildOutput:
        """Run the full ``compile`` pipeline (GIL released).

        ``registry_version`` is the harness model-registry version, folded
        into evidence-cache keys so a model upgrade forces re-verification
        (BE-1/INV-1).
        """
        ...

def core_version() -> str:
    """Return the compiler core version string."""
    ...

def schema_version() -> int:
    """Return the serialized-schema version the boundary speaks."""
    ...

def format(text: str) -> str:
    """Format source text into its canonical spelling."""
    ...

def debug_dump(stage: str, path: str) -> str:
    """Dump an intermediate pipeline stage of a source file as text."""
    ...

def check_elec_single_driver(nets_json: str) -> str:
    """Run the elec net discipline's single-driver check (AD-23 D4).

    ``nets_json`` is a JSON array of ``NetlistModel.nets``-shaped nets
    (``{"name","pins":[{"component","pin","is_driver"}]}``). Returns a
    JSON object: ``{"ok": true}`` when clean, or ``{"ok": false, "net",
    "drivers", "message"}`` naming the first offending net.
    """
    ...

def init_logging() -> None:
    """Install the Rust->Python logging bridge (idempotent)."""
    ...
