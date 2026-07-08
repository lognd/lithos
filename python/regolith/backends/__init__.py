"""Manufacturing backends + the ship pipeline (WO-25, L6).

A backend consumes ONLY (lockfile, evidence cache, realized artifacts) --
never the compiler/CST (enforced by construction: no ``Backend``
implementation -- ``regolith.backends.mech``/``regolith.backends.elec``
-- imports ``regolith.compiler`` or ``regolith._core``; only the driver,
``regolith.backends.ship``, calls the orchestrator to run the release
gate, same layer `regolith.orchestrator.orchestrate` already sits at) --
and serializes them into files a manufacturer can consume. Backends never
decide anything (regolith/07 sec. 6): every emitted byte traces to a
pinned lockfile row, a discharged obligation's evidence, or a realized-
domain IR (AD-25) already produced upstream. ``regolith.backends.ship``
is the top: it enforces the release gate (INV-24) and produces a signed
manifest over every emitted file.
"""

from __future__ import annotations

from regolith.backends.framework import Backend, BackendInputs, OutputFile
from regolith.backends.manifest import ShipManifest, sign_manifest, verify_manifest

__all__ = [
    "Backend",
    "BackendInputs",
    "OutputFile",
    "ShipManifest",
    "sign_manifest",
    "verify_manifest",
]
