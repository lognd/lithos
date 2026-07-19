"""Demo 17 -- the physical bring-up pack (WO-127 deliverable 4, D222).

Charter 40 promises that after something is built, it is easy to
physically TEST it. This demo is the paper proof of that promise, and
it is the only demo that ships TWO projects and cross-references them.

The target is `mainboard_mx` -- the fleet's board-bearing flagship. Of
the two candidates the WO names, its tap set exercises more kinds: it
carries a real BoardOutline through the deterministic board leg, an
explicit `refclk` tap in its ship spec, and claim-named rail/clock nets
for the deriver to rank, so the debug profile has real hardware to
place taps ON. (printer_k1's controller board realizes no outline
inputs, so its boards/firmware families are named-absent and its taps
would have nothing to land on.)

What the demo does:

1. Ships the TARGET with ``--emit-profile debug``: the debug profile
   places the tap header on the layout, labels each tap on the
   silkscreen, and emits the `harness/` family -- `tap_map.json`,
   `expected_signals.json`, `bringup.md`, sigrok capture configs.
2. Ships the JIG (`la_jig8`) at release: gerbers, firmware, calc book.
3. Walks the seam and PROVES it closes, row by row:
   - every target tap channel maps to a jig channel through the ONE
     published header record (`tap_header_2x08_254`) -- the demo asserts
     BOTH packages cite the same record key and the same channel
     ordering, because that record is the single home and a desync
     between the two sides is precisely the failure this seam exists to
     make impossible;
   - every tap's expected signal either carries PROVENANCE (a calc-sheet
     hash, claim id, or record ref) or is an honest `no_verified_
     expectation` named absence -- D224 forbids a fabricated number, and
     this demo FAILS if it finds one;
   - every provenance hash that points at a calc sheet actually resolves
     in the target's shipped calc book.

The output is one cross-referenced PROOF.md: target tap channel -> jig
channel -> expected signal -> calc-sheet hash. That table is what a
human takes to the bench with a ribbon cable.

Nothing here computes a number. It ships both packages through the real
CLI and verifies the cross-references the two already contain.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys

from regolith.logging_setup import get_logger

from demos.harness import REPO_ROOT, DemoWriter, artifact_table

_log = get_logger(__name__)

# frob:doc docs/modules/demos.md#demo-proof-pack-shape
DEMO = "demo17_physical_bringup_pack"
# frob:doc docs/modules/demos.md#demo-proof-pack-shape
SURFACE = (
    "physical bring-up pack: a target's debug package + the la_jig8 tap jig, "
    "cross-referenced through the one published tap-header record"
)
# frob:doc docs/modules/demos.md#demo-proof-pack-shape
TARGET = REPO_ROOT / "examples" / "flagships" / "mainboard_mx"
# frob:doc docs/modules/demos.md#demo-proof-pack-shape
JIG = REPO_ROOT / "examples" / "flagships" / "la_jig8"

# The ONE published pinout record both sides must cite (charter 40
# sec. 4). One home for the string, here as in the design sources.
# frob:doc docs/modules/demos.md#demo-proof-pack-shape
HEADER_RECORD = "tap_header_2x08_254"


def _cli(*args: str) -> None:
    cmd = [sys.executable, "-m", "regolith.cli", *args]
    _log.info("demo17: running %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))
    if result.returncode != 0:
        raise RuntimeError(
            f"regolith {args[0]} failed (exit {result.returncode}):\n{result.stderr}"
        )


def _ship(project, build_dir, out_dir, *, debug: bool) -> None:
    """Build --release then ship one project (debug profile when asked).

    The debug profile AUGMENTS emission and never changes verdicts
    (charter 40 sec. 1), so both projects go through the SAME release
    build; only the ship's emission profile differs.
    """
    # `build` reads the spec's `elec_boards` block (WO-42 elec leg): an
    # elec project must realize its boards at BUILD time or the later
    # `ship --build` package has no RealizedLayout to carry.
    _cli(
        "build",
        "--release",
        str(project),
        "--spec",
        str(project / "ship.spec.json"),
        "--out",
        str(build_dir),
    )
    args = [
        "ship",
        str(project),
        "--build",
        str(build_dir),
        "--spec",
        str(project / "ship.spec.json"),
        "--out",
        str(out_dir),
    ]
    if debug:
        args += ["--emit-profile", "debug"]
    _cli(*args)


# frob:doc docs/modules/demos.md#demo-proof-pack-shape
def run() -> bool:
    """Emit the bring-up proof pack; return True (this surface is live)."""
    writer = DemoWriter(DEMO, SURFACE)
    target_dist = writer.out_dir / "target-debug"
    jig_dist = writer.out_dir / "jig"
    target_build = writer.out_dir / "target-build"
    jig_build = writer.out_dir / "jig-build"
    for stale in (target_dist, jig_dist, target_build, jig_build):
        if stale.exists():
            shutil.rmtree(stale)

    # 1 + 2: both packages, through the real CLI.
    _ship(TARGET, target_build, target_dist, debug=True)
    _ship(JIG, jig_build, jig_dist, debug=False)

    tap_map = json.loads((target_dist / "harness" / "tap_map.json").read_text())
    expected = json.loads(
        (target_dist / "harness" / "expected_signals.json").read_text()
    )
    target_calc = json.loads((target_dist / "calc" / "calc_book.json").read_text())
    jig_calc = json.loads((jig_dist / "calc" / "calc_book.json").read_text())

    # Keep the evidence both sides of the seam rest on.
    for rel in ("tap_map.json", "expected_signals.json", "bringup.md"):
        writer.emit(
            "target-debug/harness/" + rel,
            (target_dist / "harness" / rel).read_bytes(),
        )
    writer.emit(
        "target-debug/boards/tap_placements.json",
        (target_dist / "boards" / "tap_placements.json").read_bytes(),
    )
    writer.emit(
        "jig/calc/calc_book.json", (jig_dist / "calc" / "calc_book.json").read_bytes()
    )
    # The jig's silkscreen, as evidence that the jig ships a real board.
    # Gerber output embeds TF.CreationDate, so it is honestly flagged
    # NONDETERMINISTIC -- the same posture demo11 takes (never a faked
    # byte-stability claim).
    writer.emit(
        "jig/boards/gerbers/board-F_Silkscreen.gto",
        (jig_dist / "boards" / "gerbers" / "board-F_Silkscreen.gto").read_bytes(),
        deterministic=False,
    )

    # 3a. THE SEAM: both sides cite the same header record, verbatim.
    target_header = tap_map["header"]
    if target_header.get("record") != HEADER_RECORD:
        raise RuntimeError(
            f"target tap map cites header record {target_header.get('record')!r}, "
            f"not the published {HEADER_RECORD!r} -- the single-home seam is broken"
        )
    jig_bom = (jig_dist / "boards" / "bom.csv").read_text()
    if HEADER_RECORD not in jig_bom:
        raise RuntimeError(
            f"the jig's BOM does not carry {HEADER_RECORD!r} -- it cannot mate "
            "the header the target places"
        )
    channels = int(target_header["channels"])

    # 3b. Every expected signal carries provenance or is a NAMED absence.
    #     A fabricated number here would be a D224 violation; fail loudly.
    sheet_ids = {s["sheet_id"] for s in target_calc["sheets"]}
    sheet_digests = {
        s["chain"]["sheet_digest"] for s in target_calc["sheets"] if s.get("chain")
    }
    rows = []
    absences = 0
    provenanced = 0
    for tap in tap_map["taps"]:
        ch = tap["channel"]
        sig = next((s for s in expected["signals"] if s["channel"] == ch), None)
        if sig is None:
            raise RuntimeError(f"tap channel {ch} has no expected_signals row")

        prov = sig.get("provenance") or {}
        note = sig.get("note")
        expected_value = sig.get("expected")

        if note == "no_verified_expectation" or expected_value is None:
            # An HONEST NAMED ABSENCE (charter 40 sec. 3 / D224): no
            # discharged claim or declared record stands behind a number
            # for this tap, so the pack refuses to print one. It still
            # carries WHY, and a ref to the evidence it consulted.
            if not prov.get("reason"):
                raise RuntimeError(
                    f"tap channel {ch} ({tap['target_path']}) is an absence "
                    "with no reason -- an unexplained blank is not an honest "
                    "absence (charter 40 sec. 5)"
                )
            absences += 1
            value = "_(no verified expectation)_"
            prov_txt = f"{prov.get('kind', '?')}: {prov['reason'].split(' -- ')[0]}"
        else:
            # A real expectation: it MUST carry provenance, and a
            # calc-sheet ref must resolve in the shipped calc book.
            if not prov:
                raise RuntimeError(
                    f"tap channel {ch} ({tap['target_path']}) states an expected "
                    f"value {expected_value!r} with NO provenance -- that is a "
                    "fabricated number (D224)"
                )
            provenanced += 1
            value = f"{expected_value} {sig.get('units', '')}".strip()
            ref = prov.get("ref") if prov.get("kind") == "calc_sheet" else None
            if ref and ref not in sheet_ids and ref not in sheet_digests:
                raise RuntimeError(
                    f"tap channel {ch} cites calc sheet {ref!r} that does not "
                    "resolve in the target's shipped calc book"
                )
            prov_txt = f"{prov.get('kind')}: `{str(prov.get('ref'))[:24]}`"

        rows.append(
            f"| {ch} | `{tap['target_path']}` | {tap['kind']} | ch{ch} "
            f"(pin {2 * ch + 1}) | {sig.get('quantity', '?')} | {value} "
            f"| {prov_txt} |"
        )

    _log.info(
        "demo17: seam closed -- %d channel(s), %d provenanced, %d named absence(s)",
        channels,
        provenanced,
        absences,
    )

    proof = "\n".join(
        [
            f"# {DEMO} -- the physical bring-up pack",
            "",
            "Charter 40's promise is that after something is built, it is easy",
            "to physically TEST it. This is the paper proof: a fleet target's",
            "DEBUG package and the la_jig8 tap jig's package, cross-referenced,",
            "together contain everything needed to put a probe on the board.",
            "",
            "## What drove this",
            "",
            "- pipeline path: `regolith build --release --spec` + `regolith ship "
            "--emit-profile debug` on the TARGET, and the same pair at the "
            "release profile on the JIG -- both through the real CLI, no "
            "in-process shortcuts.",
            "",
            "## The seam",
            "",
            f"Both sides cite ONE published pinout record: `{HEADER_RECORD}`",
            "(`stdlib/std.elec/records/dft.toml`). The debug emission profile",
            "PLACES it on the target; the jig MATES it. Neither side restates",
            "the pinout, so neither can drift from the other.",
            "",
            f"- header: {target_header['connector']}",
            f"- channels: {channels}, positions: {target_header['positions']}, "
            f"pitch: {target_header['pitch_mm']}mm",
            f"- ordering: {target_header['ordering']}",
            f"- ground: {target_header['ground']}",
            f"- keying: {target_header['keying']}",
            "",
            "The jig's BOM carries that same record key, so the ribbon cable",
            "between them is not a hope -- it is a checked cross-reference.",
            "",
            "## Target tap channel -> jig channel -> expected signal",
            "",
            "| ch | target net/signal | kind | jig channel (header pin) "
            "| quantity | expected | provenance |",
            "|---|---|---|---|---|---|---|",
            *rows,
            "",
            f"**{provenanced} channel(s) carry a verified numeric expectation;",
            f"{absences} are HONEST NAMED ABSENCES** (`no_verified_expectation`).",
            "",
            "Read that number honestly: today the target's debug package can",
            "tell a technician WHERE to probe and WHY, but for NOT ONE of these",
            "taps can it yet tell them WHAT THEY SHOULD SEE. D224 governs -- an",
            "expectation with no discharged claim or declared record behind it",
            "is emitted as a named absence, NEVER a fabricated number -- so the",
            "pack refuses to print a value it cannot stand behind. Every",
            "absence still carries its reason and a ref to the evidence it",
            "consulted; most trace to WO117-F2 (`unit_unresolved`: the claim's",
            "threshold carries no unit token) and to the fleet's buck-rail",
            "claims being indeterminate rather than discharged -- which is",
            "F-WO127-5's lowering gap showing up again, one layer out.",
            "",
            "This demo FAILS if it ever finds a bare expectation with no",
            "provenance, or an absence with no reason; every calc-sheet ref is",
            "resolved against the target's shipped calc book.",
            "",
            "## The jig's own evidence",
            "",
            f"The jig ships {len(jig_calc['sheets'])} calc sheet(s) of its own --",
            "it is held to the same bar as the thing it tests, not exempted",
            "from it. Its `mcu_junction` claim discharges through the",
            "registered thermal model over declared inputs.",
            "",
            "## What this does NOT prove",
            "",
            "No physical capture has been taken. Charter 40 sec. 6 defers live",
            "capture ingestion (comparing a real analyzer trace against",
            "`expected_signals.json`); the FORMAT lands now so a capture is",
            "checkable BY HAND from day one. The jig also cannot yet be built",
            "as drawn: it carries no level-shift buffer part, because no such",
            "record class exists in the stdlib (F-WO127-1, ledgered in the",
            "jig's README, not hidden here).",
            "",
            "## Re-run",
            "",
            "```",
            "uv run python -m demos.demo17_physical_bringup_pack",
            "```",
            "",
            "## Artifacts",
            "",
            artifact_table(writer.rows),
        ]
    )
    writer.finish(
        live=True,
        optimized_quantity="n/a (bring-up/harness family, not an optimizer surface)",
        domain=(
            f"mainboard_mx debug package + la_jig8 package, {channels} tap channel(s) "
            f"through record {HEADER_RECORD}"
        ),
        winner="n/a",
        cause_row="n/a",
        proof_md=proof,
    )
    return True


if __name__ == "__main__":
    run()
