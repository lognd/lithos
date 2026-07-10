"""WO-83 slice B: scenario application mechanics (charter toolchain/37
sec. 1.2/1.4, AD-22).

A `test <name>:` declaration's `scenario:` block is a list of raw
statement-line strings (`TestDeclPayload.scenario_entries`) the parser
already typed against the shared statement grammar but left
un-elaborated (slice A). Charter 37 sec. 1.2 is explicit: "no test-only
backdoor" -- a scenario entry must become either (a) an ORDINARY source
statement fed through the SAME `compiler.check`/`compiler.compile` door
`regolith check`/`regolith build` use, or (b) a scenario parameter the
ordinary CLI already exposes at invocation time (`--seed`,
`--budget-evals` on `regolith optimize`).

Decision (recorded here, not invented ad hoc per call site):

1. Entries of the form ``seed = <int>`` / ``budget_evals = <int>`` are
   OPTIMIZER SCENARIO PARAMETERS. They never touch source text -- they
   are threaded straight into :func:`regolith.orchestrator.optimize.
   optimize_discrete` exactly as `regolith optimize --seed --budget-
   evals` already does. This is not a new mechanism; it is the existing
   CLI parameter surface, invoked by the runner instead of a human.
2. Every other entry is a REAL SOURCE STATEMENT. hematite/04-vocabulary
   sec. "beyond budgets" names a free-standing `locked:` block ("free-
   standing lock-family block for planner decisions") as legal at
   assembly/system/board scope -- exactly the rung-2 pin form the
   fixture's `locked: material AL_6061_T6` entry uses. VERIFIED (not
   assumed) against the real parser: the block must be INDENTED as a
   member of the design's trailing top-level declaration body (`part`/
   `assembly`/`system`/`board`) -- a column-0 free-standing block is
   E0192 "expected a declaration or import" (the indentation-sensitive
   grammar has no bare file-scope statement position). The runner
   builds a SYNTHESIZED OVERLAY compile-input (AD-22: a copy of the
   subject's project, with one `locked:` block appended and indented
   one level under the file's last top-level declaration, whose body
   is every non-optimizer scenario entry's pin text) and hands that
   overlay to the ordinary `compiler.check`/`compiler.compile` --
   never a private read path into compiler internals, never a
   hand-rolled elaboration of the ladder. This assumes the subject's
   LAST top-level declaration is a container that accepts a `locked:`
   member (true for every corpus fixture this WO adds); a design whose
   last declaration cannot host one is a recorded v1 scope edge, not a
   silent miscompile (the overlay would surface the honest E0192).

This keeps the promise literally: scenario entries are real source
statements or real CLI parameters, evaluated by the real pipeline.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

_SEED_RE = re.compile(r"^seed\s*=\s*(-?\d+)\s*$")
_BUDGET_RE = re.compile(r"^budget_evals\s*=\s*(\d+)\s*$")
_LOCKED_RE = re.compile(r"^locked:\s*(.+)$")


@dataclass(frozen=True)
class OptimizerParams:
    """The scenario's optimizer knobs, if any (charter 37 sec. 1.2)."""

    seed: int = 0
    budget_evals: int = 50


@dataclass(frozen=True)
class ScenarioPlan:
    """The result of classifying one test's `scenario_entries`."""

    locked_lines: tuple[str, ...]
    other_lines: tuple[str, ...]
    optimizer: OptimizerParams


def classify_scenario(entries: list[str]) -> ScenarioPlan:
    """Split raw `scenario_entries` into locked-pin text, other source
    statements, and optimizer parameters (the decision above)."""
    locked: list[str] = []
    other: list[str] = []
    seed = 0
    budget = 50
    for entry in entries:
        stripped = entry.strip()
        if (m := _SEED_RE.match(stripped)) is not None:
            seed = int(m.group(1))
            continue
        if (m := _BUDGET_RE.match(stripped)) is not None:
            budget = int(m.group(1))
            continue
        if (m := _LOCKED_RE.match(stripped)) is not None:
            locked.append(m.group(1).strip())
            continue
        # An unrecognized-but-non-empty entry is still an ordinary
        # top-level statement candidate (config-axis selections,
        # realized-input refs) -- appended verbatim, honest fallback.
        if stripped:
            other.append(stripped)
    return ScenarioPlan(
        locked_lines=tuple(locked),
        other_lines=tuple(other),
        optimizer=OptimizerParams(seed=seed, budget_evals=budget),
    )


def design_path_for(test_file: Path) -> Path:
    """The sibling design file a `<name>.test.<ext>` file exercises: the
    discovery convention (charter 37 sec. 1.1) strips exactly the
    `.test` infix, e.g. `spar_bracket_wo83.test.hema` ->
    `spar_bracket_wo83.hema`."""
    name = test_file.name
    marker = ".test."
    idx = name.rfind(marker)
    if idx == -1:
        return test_file
    return test_file.with_name(name[:idx] + name[idx + len(".test") :])


def build_overlay_project(test_file: Path, plan: ScenarioPlan, dest: Path) -> Path:
    """Copy `test_file` and its sibling design file (plus a project
    manifest, if any) into `dest`, patch the design file's copy with an
    appended top-level `locked:` block (rung 2) plus any other scenario
    source lines, and return the design file's path inside the overlay
    -- the ordinary-build-path compile input (AD-22, no private
    pipeline).

    A `magnetite.toml` beside the test file marks a REAL multi-file
    project (e.g. a flagship): the whole directory is copied so
    cross-file references resolve exactly as `regolith build` sees
    them. Without one, only the test/design pair is copied -- most
    per-track corpus fixtures are single-file designs (the slice-A
    precedent), and copying every unrelated sibling example in a
    shared directory would pull the whole track's corpus into each
    scenario's build for no reason and slow every run down.
    """
    src_dir = test_file.parent
    dest.mkdir(parents=True, exist_ok=True)
    manifest = src_dir / "magnetite.toml"
    if manifest.is_file():
        for item in src_dir.rglob("*"):
            if item.is_file() and ".regolith" not in item.parts:
                rel = item.relative_to(src_dir)
                (dest / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dest / rel)
    else:
        shutil.copy2(test_file, dest / test_file.name)
    design = design_path_for(test_file)
    overlay_design = dest / design.name
    if not design.is_file():
        # The negative case (no sibling design file) -- leave the
        # overlay project as a bare copy; the build will honestly fail
        # to find the subject, surfaced through the ordinary renderer.
        return overlay_design
    shutil.copy2(design, overlay_design)
    text = overlay_design.read_text()
    lines: list[str] = []
    if plan.locked_lines:
        lines.append("")
        lines.append("    locked:")
        lines.extend(f"        {entry}" for entry in plan.locked_lines)
    lines.extend(f"\n{entry}" for entry in plan.other_lines)
    if lines:
        overlay_design.write_text(text + "\n" + "\n".join(lines) + "\n")
    return overlay_design
