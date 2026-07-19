"""WO-131/D247: `tools.codegen.generate_codes` regen driver.

`generate()` is the pure rendering half of the `make codes` driver
(the impure half shells to `cargo run -p regolith-api --bin
regolith-export-codes`, exercised by `make codes` itself, not here).
This is a real end-to-end test of the module's only pure-Python
surface: export rows in, a syntactically valid generated module out.
"""

from __future__ import annotations

import ast

from tools.codegen.generate_codes import generate


# frob:tests tools/codegen/generate_codes.py::generate kind="unit"
# frob:tests tools/codegen/generate_codes.py kind="integration"
def test_generate_renders_valid_module() -> None:
    rows = [
        {
            "code": "E0001",
            "symbol": "SOME_CODE",
            "family": "sem",
            "meaning": "a thing happened",
            "why": "because",
            "fix": "do the other thing",
            "example": None,
            "authored": True,
        },
    ]
    body = generate(rows)
    # The generated module must parse as valid Python (it is committed
    # and imported directly, never re-checked at import time).
    ast.parse(body)
    assert "SOME_CODE = 'E0001'" in body
    assert "BY_CODE: dict[str, CodeEntry] = {e.code: e for e in ALL}" in body


def test_generate_is_deterministic() -> None:
    rows = [
        {
            "code": "E0002",
            "symbol": "OTHER_CODE",
            "family": "diag",
            "meaning": "m",
            "why": "w",
            "fix": "f",
            "example": "ex",
            "authored": False,
        },
    ]
    assert generate(rows) == generate(rows)
