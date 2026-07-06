"""Elec structural realizer: bind -> netlist -> layout (WO-24).

Spec: cuprite/04 (step order is normative), cuprite/06 (lowering
table), regolith/08 sec. L4, regolith/07 sec. 7 (allocation search).
Submodules: :mod:`binding` (component binding / allocation search),
:mod:`netlist` (neutral netlist model + KiCad writer + arbitration
checks), :mod:`kicad` (the `realizer.elec.kicad` layout adapter,
subprocess-isolated per WO-20/AD-19), :mod:`extraction` (post-route
extraction surface for layout-dependent claims).
"""

from __future__ import annotations
