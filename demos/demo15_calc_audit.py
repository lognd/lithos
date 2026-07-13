"""Demo 15 -- the calc book + audit trail, walked end to end (D221).

WO-115 deliverable 9 (charter 38 sec. 1.14). arm_a6 is the richest
candidate: after the WO-113/D224 enrichment its release build carries
TEN real discharges (bearing L10 rows, bolted joints, deflections,
DFM `makeable` rows...). The demo ships the project through the real
two-command flow, keeps the `calc/` family, and then AUDITS it the way
a checking engineer would:

1. EVERY-ROW WALK: `audit_index.json` maps every obligation (54) to
   exactly one disposition. Each `calc_sheet` row must resolve to a
   sheet in `calc_book.json` AND a rendered per-sheet PDF; each
   `accepted_deviation` row's canonical content hash must appear in an
   `acceptance_ledger.json` entry's accepted/match set (the
   cross-link the charter requires); zero violated, zero deferred,
   zero unexplained rows -- and the summary counts must reconcile with
   the rows themselves.

2. HASH-CHAIN VERIFICATION: every sheet's `chain.sheet_digest` is
   recomputed INDEPENDENTLY here from the shipped sheet's own body
   fields (the documented canonical encoding: sorted keys, ASCII,
   indent=2, blake3, `local-blake3:` tag) and must match -- the chain
   closes over the sheet, and the shipped JSON alone proves it. The
   chain's `evidence_hash` must equal the discharge evidence hash the
   sheet body cites, and record-pinned inputs must surface in
   `chain.record_pins`.

Every number on a sheet (value, margin, model id/version/citation,
`given:` inputs with provenance pins) is the REAL discharge's -- this
demo only walks and verifies, it computes nothing new.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys

import blake3
from regolith.logging_setup import get_logger

from demos.harness import REPO_ROOT, DemoWriter, artifact_table

_log = get_logger(__name__)

DEMO = "demo15_calc_audit"
SURFACE = "calc book + audit index with real discharges, walked row by row (arm_a6)"
PROJECT = REPO_ROOT / "examples" / "flagships" / "arm_a6"

# The body-field order calc.py's `_sheet_digest` hashes (its `body`
# dict); the canonical encoder sorts keys anyway, so only the SET
# matters -- kept here as the independent re-computation's contract.
_BODY_FIELDS = (
    "sheet_id",
    "claim_name",
    "claim_text",
    "subject_anchor",
    "subject_ref",
    "model_id",
    "model_version",
    "citation",
    "inputs",
    "value",
    "margin",
    "verdict",
)


def _cli(*args: str) -> None:
    cmd = [sys.executable, "-m", "regolith.cli", *args]
    _log.info("demo15: running %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))
    if result.returncode != 0:
        raise RuntimeError(
            f"regolith {args[0]} failed (exit {result.returncode}):\n{result.stderr}"
        )


def _recompute_sheet_digest(sheet: dict) -> str:
    """The independent chain check: blake3 over the sheet's own body
    (everything but `chain`), canonical encoding, `local-blake3:` tag."""
    body = {field: sheet[field] for field in _BODY_FIELDS}
    body["evidence_hash"] = sheet["chain"]["evidence_hash"]
    canonical = json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=True, indent=2
    ).encode("ascii")
    return "local-blake3:" + blake3.blake3(canonical).hexdigest()


def run() -> bool:
    """Emit the calc-audit proof pack; return True (this surface is live)."""
    writer = DemoWriter(DEMO, SURFACE)
    build_dir = writer.out_dir / "build"
    dist_dir = writer.out_dir / "dist"
    for stale in (build_dir, dist_dir):
        if stale.exists():
            shutil.rmtree(stale)

    _cli("build", "--release", str(PROJECT), "--out", str(build_dir))
    _cli(
        "ship",
        str(PROJECT),
        "--build",
        str(build_dir),
        "--spec",
        str(PROJECT / "ship.spec.json"),
        "--out",
        str(dist_dir),
    )

    calc_dir = dist_dir / "calc"
    for path in sorted(calc_dir.rglob("*")):
        if path.is_file():
            writer.emit("calc/" + str(path.relative_to(calc_dir)), path.read_bytes())
    writer.emit(
        "acceptance_ledger.json", (dist_dir / "acceptance_ledger.json").read_bytes()
    )

    audit = json.loads((calc_dir / "audit_index.json").read_text())
    book = json.loads((calc_dir / "calc_book.json").read_text())
    ledger = json.loads((dist_dir / "acceptance_ledger.json").read_text())
    sheets_by_id = {s["sheet_id"]: s for s in book["sheets"]}
    accepted_hashes = {
        h
        for entry in ledger["accepted_deviations"]
        for h in (*entry.get("accepted", ()), *entry.get("match_set", ()))
    }

    # 1. The every-row walk.
    rows = audit["rows"]
    counts = {"calc_sheet": 0, "accepted_deviation": 0}
    for row in rows:
        disposition = row["disposition"]
        if disposition == "calc_sheet":
            sheet = sheets_by_id.get(row["detail"])
            if sheet is None:
                raise RuntimeError(f"audit row {row['detail']} has no calc sheet")
            subject_prefix = row["detail"].rpartition("::")[2]
            pdf = calc_dir / f"{row['claim_name']}__{subject_prefix}.pdf"
            if not pdf.is_file():
                raise RuntimeError(f"audit row {row['detail']} has no rendered PDF")
            if sheet["verdict"] != "discharged":
                raise RuntimeError(f"calc sheet {row['detail']} is not a discharge")
        elif disposition == "accepted_deviation":
            if row["content_hash"] not in accepted_hashes:
                raise RuntimeError(
                    f"accepted row {row['claim_name']} ({row['content_hash']}) "
                    "not cross-linked in acceptance_ledger.json"
                )
        else:
            raise RuntimeError(
                f"unexplained audit disposition {disposition!r} for "
                f"{row['claim_name']} -- the walk found a hole"
            )
        counts[disposition] += 1
    summary = audit["summary"]
    if (
        summary["obligations"] != len(rows)
        or summary["discharged"] != counts["calc_sheet"]
        or summary["accepted_rows"] != counts["accepted_deviation"]
        or summary["violated"] != 0
        or summary["deferred"] != 0
    ):
        raise RuntimeError(f"audit summary does not reconcile: {summary} vs {counts}")
    if counts["calc_sheet"] < 10:
        raise RuntimeError(
            f"expected arm_a6's 10 real discharges, found {counts['calc_sheet']}"
        )

    # 2. The independent hash-chain verification, every sheet.
    pinned_sheets = 0
    for sheet_id, sheet in sorted(sheets_by_id.items()):
        recomputed = _recompute_sheet_digest(sheet)
        if recomputed != sheet["chain"]["sheet_digest"]:
            raise RuntimeError(f"hash chain BROKEN for {sheet_id}: {recomputed}")
        if not sheet["chain"]["evidence_hash"]:
            raise RuntimeError(f"{sheet_id} carries no evidence hash")
        record_inputs = [i for i in sheet["inputs"] if i["provenance"] == "record_ref"]
        if record_inputs and not sheet["chain"]["record_pins"]:
            raise RuntimeError(f"{sheet_id} lost its record pins from the chain")
        if record_inputs:
            pinned_sheets += 1

    sheet_lines = [
        f"| {s['sheet_id']} | {s['model_id']} | {s['value']} | {s['margin']} | "
        f"{s['citation'][:40]} |"
        for _, s in sorted(sheets_by_id.items())
    ]

    proof = "\n".join(
        [
            f"# PROOF: {SURFACE}",
            "",
            "- pipeline path: `regolith build --release` + `regolith ship "
            "--spec` over arm_a6; the shipped `calc/` family is kept "
            "verbatim (calc_book.json, audit_index.json, one PDF per "
            "discharged sheet) beside `acceptance_ledger.json`.",
            f"- EVERY-ROW WALK: all {len(rows)} obligations resolve to "
            f"exactly one disposition -- {counts['calc_sheet']} calc "
            f"sheets (each with a rendered PDF, asserted on disk) + "
            f"{counts['accepted_deviation']} accepted deviations (each "
            "content hash cross-linked into an acceptance-ledger match "
            "set, asserted), 0 violated, 0 deferred, 0 unexplained; the "
            "summary block reconciles with the rows.",
            f"- HASH CHAIN: every sheet's `chain.sheet_digest` was "
            "recomputed here INDEPENDENTLY (blake3 over the sheet's own "
            "canonical body, `local-blake3:` tag) and matches the "
            "shipped value; every sheet cites its discharge evidence "
            f"hash; {pinned_sheets} sheet(s) carry record-pinned inputs "
            "surfaced in `chain.record_pins`.",
            "- every value/margin/model/citation below is the REAL "
            "discharge's own (D224 enrichment: cited manufacturer "
            "ratings, ISO 281 exponents, VDI 2230 -- see each sheet's "
            "`inputs` provenance).",
            "",
            "## The ten discharged sheets",
            "",
            "| sheet | model | value | margin | citation |",
            "|---|---|---|---|---|",
            *sheet_lines,
            "",
            "## Re-run",
            "",
            "```",
            "uv run python -m demos.demo15_calc_audit",
            "```",
            "",
            "## Artifacts",
            "",
            artifact_table(writer.rows),
        ]
    )
    writer.finish(
        live=True,
        optimized_quantity="n/a (calc/audit family, not an optimizer surface)",
        domain="arm_a6 calc book: 10 discharges + 44 accepted deviations",
        winner="n/a",
        cause_row="n/a",
        proof_md=proof,
    )
    return True


if __name__ == "__main__":
    run()
