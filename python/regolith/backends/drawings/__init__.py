"""Drawings + schedules backend: `DrawingModel` producers, an SVG
reference renderer, and the drafting quality audit (WO-50, AD-27/D140).

Per `docs/spec/toolchain/25-drawings-and-artifacts.md`: producers derive
(`regolith.backends.drawings.producers`), renderers render
(`regolith.backends.drawings.renderer`), and drawing quality is audited
by rules (`regolith.backends.drawings.audit`). The civil plan/section
sheet producer is DEFERRED (named residual) until WO-48's `frame`
payload lands; the mech part-drawing and fluid P&ID producers, plus the
elec BOM table producer, are in scope now.
"""

from __future__ import annotations

from regolith.backends.drawings.backend import DrawingsBackend

__all__ = ["DrawingsBackend"]
