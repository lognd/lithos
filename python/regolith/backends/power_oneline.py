"""The `power_oneline` manufacturing package: one-line diagram (WO-137,
F-WO137-1, T-0064).

Mirrors `regolith.backends.perfboard.PerfboardBackend`'s shape
(subject-bound, `produce(inputs) -> Result[tuple[OutputFile, ...],
BackendError]`) and its own family/provenance discipline: this backend
projects an already-elaborated `PowerNetPayload` (no solving, no
elaboration -- regolith/07 sec. 6, "backends never decide") so every
file it emits is `tier="deterministic"` (WO-160, AD-45) -- a
`real_tool` tier is never claimed here, there is no external tool in
this path at all.

The diagram is rendered through the SAME `DrawingModel` -> svg renderer
path every other track uses
(`regolith.backends.drawings.producers.power_oneline` +
`regolith.backends.drawings.renderer.render_svg`, AD-27) -- this module
never invents its own rendering, the same discipline
`regolith.backends.perfboard` already follows for the wiring map.
"""

from __future__ import annotations

from typani.result import Err, Ok, Result

from regolith.backends.drawings.producers import power_oneline as power_oneline_model
from regolith.backends.drawings.renderer import render_svg
from regolith.backends.framework import ArtifactProvenance, BackendInputs, OutputFile
from regolith.errors import BackendError
from regolith.logging_setup import get_logger

_log = get_logger(__name__)

# frob:doc docs/modules/py-backends.md#backends-power-oneline
_DETERMINISTIC = ArtifactProvenance(tier="deterministic")


# frob:doc docs/modules/py-backends.md#backends-power-oneline
class PowerOnelineBackend:
    """Produces the `power_oneline` one-line-diagram package (svg +
    the underlying `DrawingModel` json) for one `PowerNetPayload`
    subject."""

    def __init__(self, subject: str) -> None:
        """Bind the ``subject`` (a key of `BackendInputs.power_nets`)."""
        self._subject = subject

    # frob:doc docs/modules/py-backends.md#backends-power-oneline
    def produce(
        self, inputs: BackendInputs
    ) -> Result[tuple[OutputFile, ...], BackendError]:
        """Emit ``power_oneline/power_oneline.svg`` +
        ``power_oneline/power_oneline.json``."""
        power = inputs.power_nets.get(self._subject)
        if power is None:
            _log.warning(
                "power_oneline backend: no PowerNetPayload for %s", self._subject
            )
            return Err(
                BackendError(
                    kind="power_net_ir_unavailable",
                    message=(
                        f"no PowerNetPayload supplied for subject {self._subject!r}"
                    ),
                )
            )

        model = power_oneline_model(self._subject, power)
        svg_bytes = render_svg(model)
        json_bytes = model.model_dump_json(by_alias=True, indent=2).encode("utf-8")

        files = (
            OutputFile.of(
                "power_oneline/power_oneline.svg", svg_bytes, provenance=_DETERMINISTIC
            ),
            OutputFile.of(
                "power_oneline/power_oneline.json",
                json_bytes,
                provenance=_DETERMINISTIC,
            ),
        )
        _log.info(
            "power_oneline backend: emitted %d file(s) for %s",
            len(files),
            self._subject,
        )
        return Ok(files)
