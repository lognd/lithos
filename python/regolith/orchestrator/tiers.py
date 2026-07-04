"""Build tiers: the T0..T3 progression (substrate/09 sec. 1).

Every regolith build runs at one tier, and each tier is a strict superset
of the work of the tier below it -- ``check`` (T0) is pure static analysis,
``build`` (T1) adds realization + harness discharge, ``optimize`` (T2)
adds the orchestrator loop, and ``release`` (T3) adds the totality gate
(INV-24). The tiers form a total order so a caller can ask "does this tier
include that work?" without re-encoding the ladder anywhere else.
"""

from __future__ import annotations

from enum import IntEnum


class BuildTier(IntEnum):
    """The build ladder, ordered by how much work the tier performs.

    The integer value IS the order (``IntEnum``): higher tiers include the
    lower tiers' work, so ``BuildTier.RELEASE > BuildTier.CHECK`` and
    :meth:`includes` are the same fact.
    """

    CHECK = 0  # T0: L0-L3 static + closed-form-dischargeable L5 (ms-s)
    BUILD = 1  # T1: + L4 realization, harness discharge, conformance (s-min)
    OPTIMIZE = 2  # T2: + the orchestrator lazy loop
    RELEASE = 3  # T3: + release-gate totality (INV-24)

    def includes(self, other: BuildTier) -> bool:
        """True iff this tier performs all of ``other``'s work (>= in order)."""
        return self >= other

    @property
    def runs_discharge(self) -> bool:
        """True iff this tier routes obligations to the harness (T1+)."""
        return self >= BuildTier.BUILD

    @property
    def runs_loop(self) -> bool:
        """True iff this tier runs the lazy optimization loop (T2+)."""
        return self >= BuildTier.OPTIMIZE

    @property
    def is_release(self) -> bool:
        """True iff this tier enforces release-gate totality (T3, INV-24)."""
        return self >= BuildTier.RELEASE


# The CLI-verb spelling of each tier (substrate/09 sec. 1); `--release`
# is the flag form of `build`, hence it shares the `build` verb.
TIER_BY_VERB: dict[str, BuildTier] = {
    "check": BuildTier.CHECK,
    "build": BuildTier.BUILD,
    "optimize": BuildTier.OPTIMIZE,
    "release": BuildTier.RELEASE,
}
