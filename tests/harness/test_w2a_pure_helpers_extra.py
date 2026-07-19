"""Direct unit coverage for a handful of small, pure harness/config helpers
flagged by `frob check` (TEST001) with no existing test naming them
directly, even though nearby wiring tests exercise the surrounding module
(W2a frob-adoption sweep).
"""

from __future__ import annotations

from pathlib import Path

from regolith._schema.models import ScalarInterval
from regolith.config import global_config_path
from regolith.harness.models.cam.records import Aabb
from regolith.harness.models.cost_common import length_interval_to_m


# frob:tests python/regolith/config.py::global_config_path
def test_global_config_path_is_under_platformdirs_user_config() -> None:
    """The global config path is `regolith/config.toml` under the user config dir."""
    path = global_config_path()
    assert isinstance(path, Path)
    assert path.name == "config.toml"
    assert path.parent.name == "regolith"


# frob:tests python/regolith/harness/models/cost_common.py::length_interval_to_m
def test_length_interval_to_m_converts_mm_and_rejects_unknown_unit() -> None:
    """mm scales by 1e-3 to metres; an unrecognized unit is `None`, never a
    silent misconversion."""
    mm = ScalarInterval(lo=1000.0, hi=2000.0, unit="mm")
    converted = length_interval_to_m(mm)
    assert converted is not None
    assert converted.unit == "m"
    assert converted.lo == 1.0
    assert converted.hi == 2.0

    unknown = ScalarInterval(lo=1.0, hi=2.0, unit="furlong")
    assert length_interval_to_m(unknown) is None


# frob:tests python/regolith/harness/models/cam/records.py::Aabb.contains_point
def test_aabb_contains_point_is_inclusive_of_bounds() -> None:
    """A point exactly on a box face counts as contained (inclusive bounds)."""
    box = Aabb(x_min=0.0, x_max=1.0, y_min=0.0, y_max=1.0, z_min=0.0, z_max=1.0)
    assert box.contains_point(0.0, 0.0, 0.0) is True
    assert box.contains_point(1.0, 1.0, 1.0) is True
    assert box.contains_point(1.5, 0.5, 0.5) is False
