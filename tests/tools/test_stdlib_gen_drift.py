"""WO-66 (D174): `make stdlib-gen` drift check -- regenerating from
the committed input tables must produce byte-identical output to what
is committed under `stdlib/` (the schema-check pattern, applied to
generated records instead of generated schemas). A real diff here
means either a generator script changed behavior without regenerating,
or a committed record file was hand-edited out from under its
generator -- both are bugs this test catches before `make check` ever
reaches the golden corpus.
"""

from __future__ import annotations

from pathlib import Path

from tools.stdlib.generate_all import generate_all


# frob:tests tools/stdlib/generate_all.py::generate_all kind="unit"
# frob:tests tools/stdlib/generate_all.py kind="integration"
# frob:tests tools/stdlib/gen_civil_sections.py::generate kind="unit"
# frob:tests tools/stdlib/gen_civil_sections.py kind="integration"
# frob:tests tools/stdlib/gen_eseries.py::generate kind="unit"
# frob:tests tools/stdlib/gen_eseries.py kind="integration"
# frob:tests tools/stdlib/gen_fasteners.py::generate kind="unit"
# frob:tests tools/stdlib/gen_fasteners.py kind="integration"
# frob:tests tools/stdlib/gen_iapws_water.py::generate kind="unit"
# frob:tests tools/stdlib/gen_iapws_water.py kind="integration"
# frob:tests tools/stdlib/gen_nasa_glenn_cp.py::generate kind="unit"
# frob:tests tools/stdlib/gen_nasa_glenn_cp.py kind="integration"
# frob:tests tools/stdlib/gen_processors.py::generate kind="unit"
# frob:tests tools/stdlib/gen_processors.py kind="integration"
# frob:tests tools/stdlib/render.py::render_row kind="unit"
# frob:tests tools/stdlib/render.py::render_records_file kind="unit"
# frob:tests tools/stdlib/render.py kind="integration"
def test_stdlib_generators_are_drift_free() -> None:
    mismatches: list[str] = []
    for path_str, expected in generate_all().items():
        path = Path(path_str)
        if not path.is_file():
            mismatches.append(f"{path}: missing (never generated to disk)")
            continue
        actual = path.read_text(encoding="utf-8")
        if actual != expected:
            mismatches.append(
                f"{path}: committed content differs from generator output"
            )
    assert not mismatches, (
        "stdlib-gen drift detected (run `make stdlib-gen` and commit the "
        "result):\n" + "\n".join(mismatches)
    )


def test_stdlib_generators_are_idempotent() -> None:
    """Calling generate_all() twice produces identical output (no
    wall-clock/randomness leaking into any generator)."""
    first = generate_all()
    second = generate_all()
    assert first == second
