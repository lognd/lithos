"""`make stdlib-gen` entry point (WO-66): runs every generator script
and writes its output. Idempotent -- rerunning with no input-table
change produces byte-identical files (D174 sourcing law rule 2), so
this same collection of `generate()` functions also backs the
drift-check test (`tests/tools/test_stdlib_gen_drift.py`) without a
second Makefile target.

2026-07-16 owner rollback directive (D266): the committed input
tables for `gen_iapws_water`/`gen_nasa_glenn_cp`/`gen_processors`
were withdrawn pending counsel review, and their generated
`stdlib/` outputs withdrawn with them. The generators themselves are
untouched CODE (re-landing path: regenerate once sourcing clears) --
`generate_all` skips a generator whose input table is currently
absent (an honest "produces nothing today", not a hard crash), so
the drift check keeps covering every generator that DOES still have
its data.
"""

from __future__ import annotations

from pathlib import Path

from regolith.logging_setup import get_logger

from tools.stdlib import (
    gen_civil_sections,
    gen_eseries,
    gen_fasteners,
    gen_iapws_water,
    gen_nasa_glenn_cp,
    gen_processors,
)

_log = get_logger(__name__)

# frob:doc docs/modules/tools.md#stdlib-generate-all
REPO_ROOT = Path(__file__).resolve().parents[2]

# frob:doc docs/modules/tools.md#stdlib-generate-all
GENERATORS = (
    gen_fasteners,
    gen_civil_sections,
    gen_eseries,
    gen_iapws_water,
    gen_nasa_glenn_cp,
    gen_processors,
)


# frob:doc docs/modules/tools.md#stdlib-generate-all
def generate_all() -> dict[str, str]:
    """{absolute_output_path: rendered_content} across every generator.

    A generator whose committed input data table has been withdrawn
    (D266, 2026-07-16) raises `FileNotFoundError` reading it -- caught
    here and skipped (that generator contributes nothing this run)
    rather than failing every OTHER generator's output too."""
    out: dict[str, str] = {}
    for module in GENERATORS:
        try:
            out.update(module.generate())
        except FileNotFoundError as exc:
            _log.info(
                "stdlib-gen: %s input withdrawn, skipping (%s)",
                module.__name__,
                exc,
            )
    return out


# frob:doc docs/modules/tools.md#stdlib-generate-all
# frob:waive TEST001 reason="CLI entry point; see tests/tools/test_stdlib_gen_drift.py"
# frob:waive TEST005 reason="measured 11.1% branch on 2026-07-19; backfill T-0036"
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
