"""Realizer package: L3 -> L4 structural realizers, one submodule per domain.

`regolith.realizer.mech` (WO-22), `regolith.realizer.elec` (WO-24), and
`regolith.realizer.firmware` are siblings; this package holds no shared
logic of its own yet -- there is no formal domain registry, only
convention by analogy to `regolith.realizer.mech`.

Adding a new realizer domain (e.g. a future calcite/civil realizer)
means, by that convention:

- a new sibling subpackage `regolith.realizer.<domain>/` with its own
  `schema.py` (the serialized feature/program IR the realizer accepts,
  the AD-4 boundary -- the ONLY input a realizer takes) and
  `interpreter.py` (or equivalent) turning that IR into the domain's
  concrete output (STEP bytes for mech, board artifacts for elec, and
  so on);
- if the domain needs post-realization verification, a `model.py` +
  `pack.py` registering a model pack the harness can discharge against
  (AD-19), mirroring `regolith.realizer.mech.model`/`.pack`;
- wiring: unlike `regolith.backends`' producer/renderer registries
  (`regolith.backends.registry`, WO-99), there is no central realizer
  registry to add an entry to. Each caller that needs the new domain's
  realizer imports it directly (see how `regolith.backends.elec` and
  `regolith.backends.firmware` import `regolith.realizer.elec`/
  `.firmware`, and how `regolith.orchestrator.orchestrate` reaches
  `regolith.realizer.mech`) -- adding a domain means adding those
  direct imports at its call sites, not registering into a shared seam.
"""

from __future__ import annotations
