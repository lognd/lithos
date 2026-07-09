"""`regolith doc` -- public-surface markdown docs (WO-41).

Spec: `docs/spec/toolchain/24-developer-tooling.md` sec. 6.
Extraction walks the typed CST through the ``regolith.compiler``
facade (``doc_extract``, backed by the new ``regolith_api::docextract``
accessor -- escalated as D127); rendering is Python-only, the ONE
markdown renderer for this WO.
"""

from __future__ import annotations

from regolith.docgen.extract import discover_sources, extract_package
from regolith.docgen.models import (
    ClaimGroupDoc,
    DeclDoc,
    FieldDoc,
    PackageDoc,
    SourceDoc,
)
from regolith.docgen.render import render_markdown
from regolith.docgen.status import claim_statuses

__all__ = [
    "ClaimGroupDoc",
    "DeclDoc",
    "FieldDoc",
    "PackageDoc",
    "SourceDoc",
    "claim_statuses",
    "discover_sources",
    "extract_package",
    "render_markdown",
]
