"""Shared machinery for the WO-108 proof-pack demo scripts.

A demo is a small script that drives the REAL regolith pipeline and
records every physical artifact it emits into a per-demo output tree:

    demos/out/<demo>/
        <artifact files ...>   (gitignored -- bytes, not shape)
        manifest.json          (committed -- the content-hash ledger)
        PROOF.md               (committed -- the human-readable proof)

`manifest.json` and `PROOF.md` are the committed *evidence of shape*; the
raw artifact bytes stay gitignored (charter 38, WO-108 rules). Every
serialized file here is deterministic (sorted keys, no timestamps) so the
determinism test can assert two runs are byte-identical.

A surface whose machinery is not yet merged (section search, bounded
sketch slots) records an HONEST gap via :func:`gap_proof` and reports
itself not-live; `make demos-strict` turns any not-live demo into a
nonzero exit while `make demos` runs only the live set.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from regolith.logging_setup import get_logger

_log = get_logger(__name__)

# demos/ lives at the repo root; out/ is its sibling child.
# frob:doc docs/modules/demos.md#harness
DEMOS_ROOT = Path(__file__).resolve().parent
# frob:doc docs/modules/demos.md#harness
OUT_ROOT = DEMOS_ROOT / "out"
# The repo root, so demos can name corpus sources by a stable path
# regardless of the invoking CWD.
# frob:doc docs/modules/demos.md#harness
REPO_ROOT = DEMOS_ROOT.parent

# frob:doc docs/modules/demos.md#harness
MANIFEST_NAME = "manifest.json"
# frob:doc docs/modules/demos.md#harness
PROOF_NAME = "PROOF.md"


# frob:doc docs/modules/demos.md#harness
# frob:waive TEST001 reason="content hash helper; see test_wo108_demos.py"
def sha256_hex(data: bytes) -> str:
    """The content hash every manifest row and PROOF.md cites (sha256,
    the same digest `dist/index.md` uses -- one hash family repo-wide)."""
    return "sha256:" + hashlib.sha256(data).hexdigest()


# frob:doc docs/modules/demos.md#harness
class ArtifactRow(BaseModel):
    """One emitted file: its package-relative path, size, and content hash.

    ``deterministic`` marks formats the determinism test byte-compares
    across two runs (SVG, STEP, lockfile, JSON, HTML, Markdown). A format
    we cannot yet prove stable byte-for-byte is recorded with the flag
    False and excluded from the byte-equality assertion (never silently).
    """

    model_config = ConfigDict(frozen=True)

    path: str
    bytes: int
    sha256: str
    deterministic: bool = True


# frob:doc docs/modules/demos.md#harness
class Manifest(BaseModel):
    """The committed content-hash ledger for one demo's artifact set.

    Serialized with sorted keys and no timestamps so two runs of a
    deterministic demo produce byte-identical `manifest.json` -- the shape
    the fleet-gate-style completeness+determinism test asserts.
    """

    model_config = ConfigDict(frozen=True)

    demo: str
    surface: str
    live: bool
    optimized_quantity: str
    domain: str
    winner: str
    cause_row: str
    artifacts: tuple[ArtifactRow, ...]

    # frob:doc docs/modules/demos.md#harness
    # frob:waive TEST001 reason="manifest serialization; exercised end to end by
    # test_wo108_demos.py::test_demo_manifest_is_complete_and_deterministic"
    def to_json_bytes(self) -> bytes:
        """Deterministic UTF-8 JSON (sorted keys, trailing newline)."""
        payload = self.model_dump(mode="json")
        return (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode("ascii")


# frob:doc docs/modules/demos.md#harness
class DemoWriter:
    """Accumulates a demo's artifacts and writes its manifest + PROOF.md.

    Callers `emit(...)` each physical artifact (the bytes go to disk and a
    hashed `ArtifactRow` is recorded), then `finish(...)` with the proof
    narrative. One home for the output-tree layout so every demo lays out
    identically and the completeness test can trust the shape.
    """

    def __init__(self, demo: str, surface: str) -> None:
        self.demo = demo
        self.surface = surface
        self.out_dir = OUT_ROOT / demo
        self._rows: list[ArtifactRow] = []
        self.out_dir.mkdir(parents=True, exist_ok=True)
        _log.info("demo %s: output tree at %s", demo, self.out_dir)

    # frob:doc docs/modules/demos.md#harness
    @property
    def rows(self) -> tuple[ArtifactRow, ...]:
        """Every artifact emitted so far, sorted by path (PROOF.md table)."""
        return tuple(sorted(self._rows, key=lambda r: r.path))

    # frob:doc docs/modules/demos.md#harness
    def emit(self, relpath: str, data: bytes, *, deterministic: bool = True) -> str:
        """Write one artifact under the demo tree; record its hash row.

        Returns the content hash so the caller can cite it in PROOF.md.
        """
        target = self.out_dir / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        digest = sha256_hex(data)
        self._rows.append(
            ArtifactRow(
                path=relpath,
                bytes=len(data),
                sha256=digest,
                deterministic=deterministic,
            )
        )
        _log.info(
            "demo %s: emitted %s (%d bytes, %s)", self.demo, relpath, len(data), digest
        )
        return digest

    # frob:doc docs/modules/demos.md#harness
    # frob:waive TEST001 reason="proof-pack writer; exercised end to end by
    # test_wo108_demos.py::test_demo_manifest_is_complete_and_deterministic"
    def finish(
        self,
        *,
        live: bool,
        optimized_quantity: str,
        domain: str,
        winner: str,
        cause_row: str,
        proof_md: str,
    ) -> Manifest:
        """Write manifest.json + PROOF.md (both committed evidence)."""
        rows = tuple(sorted(self._rows, key=lambda r: r.path))
        manifest = Manifest(
            demo=self.demo,
            surface=self.surface,
            live=live,
            optimized_quantity=optimized_quantity,
            domain=domain,
            winner=winner,
            cause_row=cause_row,
            artifacts=rows,
        )
        (self.out_dir / MANIFEST_NAME).write_bytes(manifest.to_json_bytes())
        proof_text = proof_md if proof_md.endswith("\n") else proof_md + "\n"
        (self.out_dir / PROOF_NAME).write_bytes(proof_text.encode("ascii"))
        _log.info(
            "demo %s: wrote %s + %s (live=%s, %d artifact(s))",
            self.demo,
            MANIFEST_NAME,
            PROOF_NAME,
            live,
            len(rows),
        )
        return manifest


# frob:doc docs/modules/demos.md#harness
# frob:waive TEST001 reason="PROOF.md table renderer; see test_wo108_demos.py"
def artifact_table(rows: tuple[ArtifactRow, ...]) -> str:
    """A Markdown table of every artifact with its content hash for PROOF.md."""
    lines = [
        "| artifact | bytes | sha256 |",
        "|----------|-------|--------|",
    ]
    for row in rows:
        lines.append(f"| `{row.path}` | {row.bytes} | `{row.sha256}` |")
    return "\n".join(lines)


# frob:doc docs/modules/demos.md#harness
# frob:waive TEST001 reason="not-live gap recorder; see test_wo108_demos.py"
def gap_proof(
    writer: DemoWriter,
    *,
    surface: str,
    optimized_quantity: str,
    domain: str,
    blocked_on: str,
    detail: str,
) -> Manifest:
    """Record an HONEST not-live proof for an unmerged surface.

    Writes a PROOF.md gap note (never a fabricated artifact) and a manifest
    with `live=False`; the runner turns this into a nonzero `demos-strict`
    exit. The moment the named machinery merges, the demo's probe flips to
    live and the real artifacts land -- the script is already wired for it.
    """
    proof = "\n".join(
        [
            f"# PROOF (GAP): {surface}",
            "",
            f"- optimized quantity: {optimized_quantity}",
            f"- domain: {domain}",
            "- status: NOT LIVE -- the surface machinery is not yet merged",
            f"- blocked on: {blocked_on}",
            "",
            "## Why no artifact",
            "",
            detail,
            "",
            "No artifact is emitted rather than a fabricated one (WO-108 rule:",
            "an unmerged surface emits an honest gap note and exits nonzero",
            "from `make demos-strict`). This script is already wired behind an",
            "availability probe; it produces the real proof pack the moment",
            "the machinery lands, with no further edit.",
        ]
    )
    return writer.finish(
        live=False,
        optimized_quantity=optimized_quantity,
        domain=domain,
        winner="(pending: surface not live)",
        cause_row="(pending: surface not live)",
        proof_md=proof,
    )
