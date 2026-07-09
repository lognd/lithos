"""Typed stubs for the compiled ``regolith._core`` extension (AD-2).

Hand-maintained and drift-checked against the PyO3 surface (WO-18). A
failing build is a ``BuildOutput`` with error diagnostics, never an
exception; only ``CoreBug`` (a Rust panic) and ``CoreError`` (an
infrastructure failure) are raised.
"""

RealizedInputEntry = tuple[str, str, str, bytes]
"""One caller-resolved realized-domain IR (WO-42 deliverable 3, AD-25):
``(digest, kind, subject, bytes)``. The whole build's realized-input
channel crosses as ONE coarse ``list[RealizedInputEntry]`` (AD-4)."""

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
    def check(self, realized_inputs: list[RealizedInputEntry] = ...) -> BuildOutput:
        """Run the static ``check`` pipeline (GIL released).

        ``realized_inputs`` (WO-42 deliverable 3, AD-25/D128) is the
        caller-resolved realized-domain IR channel; empty by default (the
        pre-realization placeholder path).
        """
        ...

    def compile(
        self,
        registry_version: str,
        realized_inputs: list[RealizedInputEntry] = ...,
    ) -> BuildOutput:
        """Run the full ``compile`` pipeline (GIL released).

        ``registry_version`` is the harness model-registry version, folded
        into evidence-cache keys so a model upgrade forces re-verification
        (BE-1/INV-1). ``realized_inputs`` is the same channel ``check``
        takes.
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

def debug_ir(paths: list[str], realized_inputs: list[RealizedInputEntry] = ...) -> str:
    """Dump the ``regolith debug ir`` report (WO-42 deliverable 3).

    The compiler's own IR-stage summary plus a section listing every
    realized-domain IR supplied to the build (kind, digest, subject).
    """
    ...

def doc_extract(path: str) -> str:
    """Extract a source file's public-surface doc model as JSON (WO-41).

    One entry per top-level declaration: kind, name, leading ``#`` doc
    comment (verbatim, ``None`` when absent), fields, ``require`` claim
    groups, and ``budget`` statements.
    """
    ...

def extensions() -> list[tuple[str, str]]:
    """Every recognized ``(extension, language)`` pair (ground rule 6)."""
    ...

def check_elec_single_driver(nets_json: str) -> str:
    """Run the elec net discipline's single-driver check (AD-23 D4).

    ``nets_json`` is a JSON array of ``NetlistModel.nets``-shaped nets
    (``{"name","pins":[{"component","pin","is_driver"}]}``). Returns a
    JSON object: ``{"ok": true}`` when clean, or ``{"ok": false, "net",
    "drivers", "message"}`` naming the first offending net.
    """
    ...

def rules_test(paths: list[str]) -> str:
    """Run every pack's ``expect:`` fixtures in ``paths`` (WO-28).

    Returns the ``rules test`` JSON report (one entry per pack: case
    outcomes plus missing-case lint warnings). A failing fixture is
    data in the report, never an exception.
    """
    ...

def rules_try(pack: str, design: str) -> str:
    """Run ONE pack against one design file (WO-28), no build.

    Attachment is forced; returns the ``rules try`` JSON report (every
    match with verdict, detail, and near-miss margin).
    """
    ...

def init_logging() -> None:
    """Install the Rust->Python logging bridge (idempotent)."""
    ...
