"""The elec manufacturing package: gerbers + drill + pick-and-place + BOM.

Drives `kicad-cli` against the pinned `.kicad_pcb` bytes resolved from
:class:`~regolith.backends.artifacts.NativeArtifactStore` by
``RealizedLayout.kicad_pcb_content_hash`` -- KiCad decides nothing new
here (placement/routing/DRC were pinned at WO-24 realize time); this
backend only re-exports the manufacturing file set from the ALREADY
routed board (regolith/07 sec. 6). Gated by
``regolith.realizer.elec.kicad.real_kicad_available()``, the same WO-35
gate the realizer itself uses; when closed, WO-124's fake-KiCad fab-set
exporter (`regolith.backends.elec_fabset`) emits the SAME file manifest
by hand (deterministic, honestly tier-labeled) instead of an honest
cut -- both legs' output is run through the charter 41 sec. 3
completeness checker before shipping.

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

from regolith._schema.models import RealizedLayout
from regolith.backends import elec_fabset
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
        resolved = inputs.native.resolve(layout.kicad_pcb_content_hash)
        if resolved.is_err:
            return Err(resolved.danger_err)
        pcb_bytes = resolved.danger_ok

        if self._available():
            exported = self._run_kicad_cli(pcb_bytes)
        else:
            # WO-124 (charter 41 sec. 3, D238.2): kicad-cli/pcbnew being
            # unavailable is NOT a fab-set failure -- the fake-KiCad
            # tier emits the SAME file manifest by hand, deterministic,
            # honestly tier-labeled. `resolve_tool`'s teaching message
            # stays available via `board_status.json`'s log line for a
            # caller who wants to install the real tool.
            _log.info(
                "elec backend: kicad-cli/pcbnew unavailable; using the "
                "fake-KiCad fab-set exporter for %s",
                self._subject,
            )
            status = resolve_tool("kicad-cli", use_cache=False, probe_version=False)
            _log.info(
                "elec backend: %s",
                status.teaching_message(
                    needed_for=f"the REAL kicad-cli leg ({self._subject})"
                ),
            )
            exported = Ok(
                elec_fabset.build_fake_fab_set(
                    self._subject, layout, pcb_bytes.decode("ascii", errors="replace")
                )
            )
        if exported.is_err:
            return exported
        files = list(exported.danger_ok)

        completeness = elec_fabset.check_fab_set_completeness(tuple(files))
        if completeness.is_err:
            return Err(completeness.danger_err)

        # WO-103 (charter 38 sec. 1.10): the pinned board file ships in
        # the package BESIDE its exports, with an honest status label
        # (unrouted gerbers are legitimate fab-shape evidence, and the
        # index labels them as such -- never a fabricated "routed").
        files.append(OutputFile.of("board.kicad_pcb", pcb_bytes))
        files.append(self._board_status_json(layout))
        files.append(self._bom_csv())
        files.append(self._panel_json())
        # WO-125 (charter 40 sec. 1): the debug profile's board
        # augmentation DATA -- the placed tap header + labeled test
        # points the realizer seam already derived. Serialization only
        # (regolith/07 sec. 6); absent in a release ship by construction
        # (the ship path never populates `tap_placements` then).
        plan = inputs.tap_placements.get(self._subject)
        if plan is not None:
            payload = json.dumps(
                {
                    **plan.model_dump(mode="json"),
                    "silkscreen_rendering": {
                        "handoff": "WO-124",
                        "note": (
                            "channel-label DATA only (silkscreen_labels); "
                            "the silkscreen renderer lands in WO-124 (in "
                            "flight in parallel) -- named cross-WO handoff, "
                            "ledgered in the WO-125 close-out"
                        ),
                    },
                },
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                indent=2,
            )
            files.append(OutputFile.of("tap_placements.json", payload.encode("ascii")))
            _log.info(
                "elec backend: debug tap placements for %s (%d test point(s))",
                self._subject,
                len(plan.test_points),
            )
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
                elif kind == "gerbers":
                    # WO-124 (charter 41 sec. 3): the full fab-set layer
                    # list -- copper, mask, paste, silk, fab, courtyard,
                    # edge cuts, margin (both sides where applicable).
                    # ONE list, shared with the fake-tier exporter and
                    # the completeness checker via `elec_fabset`.
                    argv = [
                        "kicad-cli",
                        "pcb",
                        "export",
                        kind,
                        "--layers",
                        elec_fabset.kicad_layers_arg(),
                        "--output",
                        str(out_dir),
                        str(pcb_path),
                    ]
                elif kind == "drill":
                    # WO-124: PTH/NPTH split + a drill map (gerberx2:
                    # plain text, no wall-clock-embedded rendering --
                    # AD-6 leans this way even though the real leg's
                    # gerbers already carry `TF.CreationDate` and are
                    # labeled nondeterministic regardless).
                    argv = [
                        "kicad-cli",
                        "pcb",
                        "export",
                        kind,
                        "--excellon-separate-th",
                        "--generate-map",
                        "--map-format",
                        "gerberx2",
                        "--output",
                        str(out_dir),
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

    def _board_status_json(self, layout: RealizedLayout) -> OutputFile:
        """The honest board-status label (WO-103 deliverable 3).

        Status is DERIVED from the `RealizedLayout` itself (routed
        segments present or not), never asserted: an outline-only board
        is honestly "unrouted", and its gerbers are labeled fab-shape
        evidence -- `regolith.backends.package.build_index` surfaces
        this label on the package index's boards-family line.
        """
        routed = bool(layout.routed_segments)
        status = "routed" if routed else "unrouted"
        label = (
            "routed board"
            if routed
            else "unrouted -- fab-shape evidence: real board outline, "
            "no routing performed"
        )
        payload = json.dumps(
            {"status": status, "label": label},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        _log.info("elec backend: board status for %s: %s", self._subject, status)
        return OutputFile.of("board_status.json", payload.encode("ascii"))

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
