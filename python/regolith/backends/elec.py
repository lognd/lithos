"""The elec manufacturing package: gerbers + drill + pick-and-place + BOM.

Drives `kicad-cli` against the pinned `.kicad_pcb` bytes resolved from
:class:`~regolith.backends.artifacts.NativeArtifactStore` by
``RealizedLayout.kicad_pcb_content_hash`` -- KiCad decides nothing new
here (placement/routing/DRC were pinned at WO-24 realize time); this
backend only re-exports the manufacturing file set from the ALREADY
routed board (regolith/07 sec. 6). Gated by
``regolith.realizer.elec.kicad.real_kicad_available()``, the same WO-35
gate the realizer itself uses -- unavailable in this sandbox
(``kicad-cli`` not on PATH, verified same way WO-24/35 verified it), so
this backend's real-tool tier is proven with a fake subprocess runner in
tests (mirroring `test_kestrel_fixture.py`'s discipline) and an
honest ``Err(ToolUnavailable)`` is what a caller sees today.

Panelization: a single-board pass-through :class:`PanelPlan` for v1
(regolith/07 sec. 6's planner-model slot exists and defers honestly;
multi-board panelization is a later planner, not invented here).
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field
from typani.result import Err, Ok, Result

from regolith.backends.framework import BackendInputs, OutputFile
from regolith.errors import BackendError
from regolith.logging_setup import get_logger
from regolith.realizer.elec.kicad import real_kicad_available
from regolith.toolenv import resolve as resolve_tool

_log = get_logger(__name__)

_EXPORT_KINDS = ("gerbers", "drill", "pos")


class AssemblyLine(BaseModel):
    """One elec BOM row: a placed reference's registry-pinned identity."""

    model_config = ConfigDict(frozen=True)

    reference: str
    part_number: str
    description: str
    vendor_ref: str
    quantity: int = Field(ge=1)


class PanelPlan(BaseModel):
    """The v1 panelization plan: single-board pass-through.

    ``boards`` names every board subject included (always exactly one
    in v1); the slot exists so a future multi-board planner has
    somewhere to land without a format change (regolith/07 sec. 6).
    """

    model_config = ConfigDict(frozen=True)

    boards: tuple[str, ...]


class ElecBackend:
    """Produces the elec manufacturing package for one routed board."""

    def __init__(
        self,
        subject: str,
        assembly: tuple[AssemblyLine, ...],
        *,
        runner: Callable[..., subprocess.CompletedProcess[bytes]] = subprocess.run,
        available: Callable[[], bool] = real_kicad_available,
    ) -> None:
        """Bind the board ``subject`` (keys ``BackendInputs.layouts``) and BOM.

        ``runner``/``available`` are injectable so tests exercise the
        real-tool tier with a fake subprocess, same discipline as
        `regolith.realizer.elec.kicad.run_layout`'s tests.
        """
        self._subject = subject
        self._assembly = tuple(sorted(assembly, key=lambda a: a.reference))
        self._runner = runner
        self._available = available

    def produce(
        self, inputs: BackendInputs
    ) -> Result[tuple[OutputFile, ...], BackendError]:
        """Emit gerbers/drill/pos + ``bom.csv`` + ``panel.json``."""
        layout = inputs.layouts.get(self._subject)
        if layout is None:
            return Err(
                BackendError(
                    kind="layout_ir_unavailable",
                    message=f"no RealizedLayout supplied for subject {self._subject!r}",
                )
            )
        if not self._available():
            _log.warning(
                "elec backend: kicad-cli/pcbnew unavailable; honest cut for %s",
                self._subject,
            )
            status = resolve_tool("kicad-cli", use_cache=False, probe_version=False)
            teaching = status.teaching_message(
                needed_for=f"the elec manufacturing package ({self._subject})"
            )
            return Err(
                BackendError(
                    kind="tool_unavailable",
                    message="kicad-cli not on PATH / pcbnew not importable "
                    "(regolith.realizer.elec.kicad.real_kicad_available() "
                    f"gate closed). {teaching}",
                )
            )
        resolved = inputs.native.resolve(layout.kicad_pcb_content_hash)
        if resolved.is_err:
            return Err(resolved.danger_err)
        pcb_bytes = resolved.danger_ok

        exported = self._run_kicad_cli(pcb_bytes)
        if exported.is_err:
            return exported
        files = list(exported.danger_ok)
        files.append(self._bom_csv())
        files.append(self._panel_json())
        _log.info("elec backend: emitted %d file(s)", len(files))
        return Ok(tuple(files))

    def _run_kicad_cli(
        self, pcb_bytes: bytes
    ) -> Result[tuple[OutputFile, ...], BackendError]:
        """Drive ``kicad-cli pcb export <kind>`` for each export kind."""
        files: list[OutputFile] = []
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pcb_path = tmp_path / "board.kicad_pcb"
            pcb_path.write_bytes(pcb_bytes)
            for kind in _EXPORT_KINDS:
                out_dir = tmp_path / kind
                out_dir.mkdir()
                if kind == "pos":
                    # `kicad-cli pcb export pos` wants a FILE path in
                    # `--output`, unlike `gerbers`/`drill` which want a
                    # directory (verified against real kicad-cli 10.0.4:
                    # a directory silently exits 4) -- CSV/mm chosen so the
                    # position file is directly machine-consumable
                    # alongside `bom.csv`.
                    argv = [
                        "kicad-cli",
                        "pcb",
                        "export",
                        kind,
                        "--output",
                        str(out_dir / "positions.csv"),
                        "--format",
                        "csv",
                        "--units",
                        "mm",
                        str(pcb_path),
                    ]
                else:
                    argv = [
                        "kicad-cli",
                        "pcb",
                        "export",
                        kind,
                        "--output",
                        str(out_dir),
                        str(pcb_path),
                    ]
                try:
                    completed = self._runner(
                        argv, capture_output=True, timeout=120.0, check=False
                    )
                except (OSError, subprocess.TimeoutExpired) as exc:
                    _log.warning("kicad-cli export %s failed to run: %s", kind, exc)
                    return Err(
                        BackendError(
                            kind="tool_unavailable",
                            message=f"kicad-cli export {kind} failed to run: {exc}",
                        )
                    )
                if completed.returncode != 0:
                    _log.warning(
                        "kicad-cli export %s exited %d", kind, completed.returncode
                    )
                    return Err(
                        BackendError(
                            kind="export_failed",
                            message=f"kicad-cli export {kind} exited "
                            f"{completed.returncode}",
                        )
                    )
                for out_file in sorted(out_dir.iterdir()):
                    files.append(
                        OutputFile.of(f"{kind}/{out_file.name}", out_file.read_bytes())
                    )
        return Ok(tuple(files))

    def _bom_csv(self) -> OutputFile:
        import csv
        import io

        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerow(
            ["reference", "part_number", "description", "vendor_ref", "quantity"]
        )
        for line in self._assembly:
            writer.writerow(
                [
                    line.reference,
                    line.part_number,
                    line.description,
                    line.vendor_ref,
                    str(line.quantity),
                ]
            )
        return OutputFile.of("bom.csv", buf.getvalue().encode("ascii"))

    def _panel_json(self) -> OutputFile:
        plan = PanelPlan(boards=(self._subject,))
        payload = json.dumps(
            plan.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        return OutputFile.of("panel.json", payload.encode("ascii"))
