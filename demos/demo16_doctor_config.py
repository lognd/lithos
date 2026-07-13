"""Demo 16 -- doctor / config / toolenv: the environment surface, proven.

WO-115 deliverable 10. Two text-artifact proofs through the REAL CLI:

1. `regolith doctor --json` -- one row per `regolith.toolenv` catalog
   entry (kicad-cli, verilator, ghdl, ngspice, ccx, gmsh): found or
   MISSING, resolved path, live version, the capability each unlocks,
   and install guidance for anything absent. The report is
   host-truthful by construction (a missing OPTIONAL tool is what
   doctor exists to show, exit 0 either way), so its artifact row is
   honestly marked deterministic=False: paths and versions are facts
   about THIS host, not about the repo.

2. Config precedence (default < global file < project
   `[tool.regolith]` < `REGOLITH_*` env < flag), demonstrated on
   `ui.port` against a DEMO-OWNED scratch project (never a fleet
   manifest, never the user's global file -- the global level is
   listed but exercised read-only for exactly that reason):

       level 0: fresh project        -> 8765  (source=default)
       level 1: `config set --local` -> 9100  (source=project; the
                write lands in the scratch magnetite.toml through the
                one config module, shown verbatim)
       level 2: REGOLITH_UI_PORT=9200 -> 9200 (source=env; the project
                value still in the file, outranked)

   Each step is the real `regolith config where` answer, captured
   verbatim -- the INV-21 "which level won and why" surface.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

from regolith.logging_setup import get_logger

from demos.harness import REPO_ROOT, DemoWriter, artifact_table

_log = get_logger(__name__)

DEMO = "demo16_doctor_config"
SURFACE = "doctor environment report + config precedence (INV-21 for config)"


def _cli(*args: str, env: dict[str, str] | None = None, cwd: str | None = None) -> str:
    cmd = [sys.executable, "-m", "regolith.cli", *args]
    _log.info("demo16: running %s", " ".join(cmd))
    merged = dict(os.environ)
    if env:
        merged.update(env)
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=cwd or str(REPO_ROOT),
        env=merged,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"regolith {args[0]} failed (exit {result.returncode}):\n{result.stderr}"
        )
    return result.stdout


def run() -> bool:
    """Emit the doctor/config proof pack; return True (live)."""
    writer = DemoWriter(DEMO, SURFACE)

    # -- 1. doctor: the host tool report --------------------------------
    doctor_json = _cli("doctor", "--json")
    rows = json.loads(doctor_json)
    if not rows:
        raise RuntimeError("doctor reported no catalog entries")
    for row in rows:
        for field in ("name", "found", "capability"):
            if field not in row:
                raise RuntimeError(f"doctor row missing {field}: {row}")
        if not row["found"] and not row["install_hint"]:
            raise RuntimeError(f"missing tool {row['name']} carries no install hint")
    writer.emit("doctor.json", doctor_json.encode("ascii"), deterministic=False)
    found = sorted(r["name"] for r in rows if r["found"])
    missing = sorted(r["name"] for r in rows if not r["found"])

    # -- 2. config precedence on a scratch project ----------------------
    scratch = writer.out_dir / "scratch_project"
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    (scratch / "magnetite.toml").write_text(
        '[package]\nname = "demo16-scratch"\nversion = "0.0.0"\n'
    )

    steps: list[tuple[str, str]] = []
    where0 = _cli("config", "where", "ui.port", "--project", str(scratch)).strip()
    steps.append(("fresh project (registered default)", where0))
    if "source=default" not in where0:
        raise RuntimeError(f"expected the default level to win: {where0}")

    set_out = _cli(
        "config", "set", "ui.port", "9100", "--local", "--project", str(scratch)
    ).strip()
    steps.append(("regolith config set ui.port 9100 --local", set_out))
    where1 = _cli("config", "where", "ui.port", "--project", str(scratch)).strip()
    steps.append(("after the local write", where1))
    if "ui.port=9100" not in where1 or "source=project" not in where1:
        raise RuntimeError(f"expected the project level to win: {where1}")

    where2 = _cli(
        "config",
        "where",
        "ui.port",
        "--project",
        str(scratch),
        env={"REGOLITH_UI_PORT": "9200"},
    ).strip()
    steps.append(("with REGOLITH_UI_PORT=9200 in the environment", where2))
    if "ui.port=9200" not in where2 or "source=env" not in where2:
        raise RuntimeError(f"expected the env level to outrank the file: {where2}")

    listing = _cli("config", "list", "--project", str(scratch))
    transcript = "\n".join(
        [
            "# config precedence transcript (real CLI output, verbatim)",
            "",
            *(f"$ {label}\n{output}\n" for label, output in steps),
            "# full registered-key listing at the final state (no env var):",
            "",
            listing,
        ]
    )
    writer.emit("config_precedence.txt", transcript.encode("ascii"))
    writer.emit(
        "scratch_project/magnetite.toml",
        (scratch / "magnetite.toml").read_bytes(),
    )

    proof = "\n".join(
        [
            f"# PROOF: {SURFACE}",
            "",
            "- pipeline path: the real `regolith doctor --json` and "
            "`regolith config get/set/where/list` CLI verbs -- every "
            "line below is captured verbatim from their stdout.",
            "",
            "## doctor",
            "",
            "- `regolith doctor --json` (real CLI): one row per toolenv "
            "catalog entry with found/path/version/capability and an "
            "install hint for anything missing (asserted per row).",
            f"- on this host: found {', '.join(found) or '(none)'}; "
            f"missing {', '.join(missing) or '(none)'}.",
            "- `doctor.json` is marked deterministic=False: it reports "
            "HOST facts (paths, versions), not repo facts -- honest "
            "churn across machines by design.",
            "",
            "## config precedence",
            "",
            "- exercised on a demo-owned scratch project (never a fleet "
            "manifest; the user's global file is never written).",
            "- the three `config where` answers, verbatim in "
            "`config_precedence.txt`: default (8765, source=default) -> "
            "project file after `config set --local` (9100, "
            "source=project; the write visible in the shipped scratch "
            "`magnetite.toml` `[tool.regolith]`) -> `REGOLITH_UI_PORT` "
            "env (9200, source=env, outranking the file that still "
            "carries 9100).",
            "- each level asserted programmatically; `config list` shows "
            "every registered key with its winning source.",
            "",
            "## Re-run",
            "",
            "```",
            "uv run python -m demos.demo16_doctor_config",
            "```",
            "",
            "## Artifacts",
            "",
            artifact_table(writer.rows),
        ]
    )
    writer.finish(
        live=True,
        optimized_quantity="n/a (environment surface, not an optimizer surface)",
        domain="host toolenv catalog + ui.port precedence ladder",
        winner="n/a",
        cause_row="n/a",
        proof_md=proof,
    )
    return True


if __name__ == "__main__":
    run()
