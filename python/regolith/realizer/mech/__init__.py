"""The mech geometry realizer (WO-22): feature IR -> build123d/OCCT -> STEP.

- :mod:`regolith.realizer.mech.schema` -- the serialized feature-program
  IR (AD-4 boundary; the realizer's only input).
- :mod:`regolith.realizer.mech.interpreter` -- the build123d/OCCT
  interpreter (AD-1) producing STEP bytes + a topology summary.
- :mod:`regolith.realizer.mech.model` / :mod:`regolith.realizer.mech.pack`
  -- the ``geometry_realizable`` post-geometry verification model,
  registered as a model pack (AD-19).
"""

from __future__ import annotations
