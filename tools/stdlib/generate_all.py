"""`make stdlib-gen` entry point (WO-66): runs every generator script
and writes its output. Idempotent -- rerunning with no input-table
change produces byte-identical files (D174 sourcing law rule 2), so
this same collection of `generate()` functions also backs the
drift-check test (`tests/tools/test_stdlib_gen_drift.py`) without a
second Makefile target.
"""

from __future__ import annotations

from pathlib import Path

from tools.stdlib import (
    gen_civil_sections,
    gen_eseries,
    gen_fasteners,
    gen_iapws_water,
    gen_nasa_glenn_cp,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

GENERATORS = (
    gen_fasteners,
    gen_civil_sections,
    gen_eseries,
    gen_iapws_water,
    gen_nasa_glenn_cp,
)


def generate_all() -> dict[str, str]:
    """{absolute_output_path: rendered_content} across every generator."""
    out: dict[str, str] = {}
    for module in GENERATORS:
        out.update(module.generate())
    return out


def main() -> None:
    total = 0
    for path_str, content in generate_all().items():
        path = Path(path_str)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="ascii")
        total += 1
        print(f"wrote {path.relative_to(REPO_ROOT)}")
    print(f"stdlib-gen: {total} file(s) regenerated")


if __name__ == "__main__":
    main()
