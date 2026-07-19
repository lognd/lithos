"""WO-18 deliverable 4: `_core.pyi` matches the real extension surface.

The stub is hand-maintained (`regolith._core` is a native extension, no
stub can be introspected from it); this test is the drift guard --
every name in `_core.__all__` must have a top-level stub declaration,
and vice versa.
"""

from __future__ import annotations

import ast
from pathlib import Path

from regolith import _core

_STUB_PATH = Path(__file__).parent.parent / "python" / "regolith" / "_core.pyi"


def _stub_top_level_names() -> set[str]:
    tree = ast.parse(_STUB_PATH.read_text())
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
            names.add(node.name)
    return names


def test_extension_all_matches_stub_declarations() -> None:
    """Every exported binding has a stub entry and nothing extra is stubbed."""
    # `_core.pyi` (the hand-maintained stub for the native `_core`
    # extension) declares no `__all__` -- a real stub gap this test's own
    # drift guard exists to catch, but out of this WO's tests/** surface
    # to fix; suppressed here rather than worked around.
    extension_names = set(_core.__all__)  # ty: ignore[unresolved-attribute]
    stub_names = _stub_top_level_names()
    assert extension_names == stub_names, (
        f"missing from stub: {extension_names - stub_names}; "
        f"stubbed but not exported: {stub_names - extension_names}"
    )
