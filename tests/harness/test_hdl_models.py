"""std.hdl model tests (WO-82): `hdl.build` verilates every non-VHDL
cuprite/09 fixture cleanly, `hdl.sim_assert`/`hdl.equiv_directed` run
counter's directed vectors and catch the broken-priority mutant, VHDL
defers named, and a malformed source renders INDETERMINATE (never a
crash)."""

from __future__ import annotations

from pathlib import Path

import pytest
from regolith._schema.models import PayloadRef
from regolith.harness.errors import DomainError
from regolith.harness.model import DischargeRequest
from regolith.harness.models.hdl.fixtures import FIXTURES_BY_ID
from regolith.harness.models.hdl.models import (
    SRC_KIND,
    SRC_PORT,
    HdlBuildModel,
    HdlEquivDirectedModel,
    HdlSimAssertModel,
)
from regolith.orchestrator.payload_store import PayloadStore

_EXAMPLES_HDL = Path(__file__).resolve().parents[2] / "examples" / "hdl"
_FIXTURES_HDL = Path(__file__).resolve().parents[1] / "fixtures" / "hdl"


@pytest.fixture
def store(tmp_path: Path) -> PayloadStore:
    return PayloadStore(str(tmp_path))


def _build_request(
    store: PayloadStore, data: bytes, regime: str, origin: str
) -> DischargeRequest:
    digest = store.put(data)
    return DischargeRequest(
        claim_kind="hdl.build",
        limit=0.0,
        inputs={},
        payloads={SRC_PORT: PayloadRef(kind=SRC_KIND, digest=digest, origin=origin)},
        regimes=(regime,),
    )


@pytest.mark.parametrize("fixture_id", ["counter", "alu_generic", "fifo_cdc"])
def test_hdl_build_discharges_for_clean_fixtures(
    store: PayloadStore, fixture_id: str
) -> None:
    fx = FIXTURES_BY_ID[fixture_id]
    data = (_EXAMPLES_HDL / fx.hdl_filename).read_bytes()
    req = _build_request(store, data, fx.regime, fx.hdl_filename)
    model = HdlBuildModel(fx)
    result = model.discharge(req, registry_version="test", resolver=store.resolver())
    assert result.is_ok, result
    assert result.danger_ok.status.value == "discharged"


def test_hdl_build_assertions_map_indeterminate_named(store: PayloadStore) -> None:
    """assertions_map.sv uses deep SVA sequence algebra (`##[1:4]`,
    `throughout`, `[*..]`) verilator's front-end does not accept
    (cuprite/09 sec. 2's own PARTIAL-mapping call, verified by tool
    failure rather than assumed) -- hdl.build renders indeterminate
    with the real diagnostic cited, never a crash."""
    fx = FIXTURES_BY_ID["assertions_map"]
    data = (_EXAMPLES_HDL / fx.hdl_filename).read_bytes()
    req = _build_request(store, data, fx.regime, fx.hdl_filename)
    model = HdlBuildModel(fx)
    result = model.discharge(req, registry_version="test", resolver=store.resolver())
    assert result.is_err
    assert isinstance(result.danger_err, DomainError)


def test_hdl_build_malformed_source_indeterminate_never_crashes(
    store: PayloadStore,
) -> None:
    data = (_FIXTURES_HDL / "bad_syntax.v").read_bytes()
    fx = FIXTURES_BY_ID[
        "counter"
    ]  # any verilog2005 fixture spec works for the port shape
    req = _build_request(store, data, fx.regime, "bad_syntax.v")
    model = HdlBuildModel(
        fx.model_copy(update={"hdl_filename": "bad_syntax.v", "top_module": "broken"})
    )
    result = model.discharge(req, registry_version="test", resolver=store.resolver())
    assert result.is_err
    assert isinstance(result.danger_err, DomainError)


def test_hdl_build_vhdl_defers_named_reason(store: PayloadStore) -> None:
    fx = FIXTURES_BY_ID["fsm_traffic"]
    data = (_EXAMPLES_HDL / fx.hdl_filename).read_bytes()
    req = _build_request(store, data, fx.regime, fx.hdl_filename)
    model = HdlBuildModel(fx)
    result = model.discharge(req, registry_version="test", resolver=store.resolver())
    assert result.is_err
    assert "VHDL" in result.danger_err.message
    assert "ghdl" in result.danger_err.message


def test_hdl_build_vhdl_defer_teaches_ghdl_install_when_absent(
    store: PayloadStore, monkeypatch
) -> None:
    """The VHDL deferral message honestly checks `ghdl` (via
    `regolith.toolenv`, never assumed) and, when it is absent, cites
    install guidance -- the required-tool teaching-diagnostic posture."""
    import regolith.harness.models.hdl.models as hdl_models
    from regolith import toolenv

    def _forced_absent(name: str, **kwargs: object) -> toolenv.ToolStatus:
        kwargs.pop("which_fn", None)
        return toolenv.resolve(name, which_fn=lambda n: None, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(hdl_models, "resolve_tool", _forced_absent)
    fx = FIXTURES_BY_ID["fsm_traffic"]
    data = (_EXAMPLES_HDL / fx.hdl_filename).read_bytes()
    req = _build_request(store, data, fx.regime, fx.hdl_filename)
    model = HdlBuildModel(fx)
    result = model.discharge(req, registry_version="test", resolver=store.resolver())
    assert result.is_err
    message = result.danger_err.message
    assert "ghdl not found" in message
    assert "apt" in message or "conda-forge" in message


def test_hdl_sim_assert_counter_discharges_all_vectors(store: PayloadStore) -> None:
    fx = FIXTURES_BY_ID["counter"]
    data = (_EXAMPLES_HDL / fx.hdl_filename).read_bytes()
    req = _build_request(store, data, fx.regime, fx.hdl_filename)
    req = req.model_copy(update={"claim_kind": "hdl.sim_assert"})
    model = HdlSimAssertModel(fx)
    result = model.discharge(req, registry_version="test", resolver=store.resolver())
    assert result.is_ok, result
    assert result.danger_ok.status.value == "discharged"


def test_hdl_equiv_directed_counter_discharges(store: PayloadStore) -> None:
    fx = FIXTURES_BY_ID["counter"]
    data = (_EXAMPLES_HDL / fx.hdl_filename).read_bytes()
    req = _build_request(store, data, fx.regime, fx.hdl_filename)
    req = req.model_copy(update={"claim_kind": "hdl.equiv_directed"})
    model = HdlEquivDirectedModel(fx)
    result = model.discharge(req, registry_version="test", resolver=store.resolver())
    assert result.is_ok, result
    assert result.danger_ok.status.value == "discharged"


def test_hdl_equiv_directed_catches_broken_priority_mutant(store: PayloadStore) -> None:
    """The negative fixture (tests/fixtures/hdl/counter_broken_priority.v)
    swaps load/enable priority -- the directed `load_priority` vector
    must catch it as a violated (nonzero-excess) claim, never a pass."""
    fx = FIXTURES_BY_ID["counter"]
    data = (_FIXTURES_HDL / "counter_broken_priority.v").read_bytes()
    req = _build_request(store, data, fx.regime, "counter_broken_priority.v")
    req = req.model_copy(update={"claim_kind": "hdl.equiv_directed"})
    model = HdlEquivDirectedModel(fx)
    result = model.discharge(req, registry_version="test", resolver=store.resolver())
    assert result.is_ok, result
    assert result.danger_ok.status.value == "violated"


def test_hdl_sim_assert_catches_broken_priority_mutant(store: PayloadStore) -> None:
    fx = FIXTURES_BY_ID["counter"]
    data = (_FIXTURES_HDL / "counter_broken_priority.v").read_bytes()
    req = _build_request(store, data, fx.regime, "counter_broken_priority.v")
    req = req.model_copy(update={"claim_kind": "hdl.sim_assert"})
    model = HdlSimAssertModel(fx)
    result = model.discharge(req, registry_version="test", resolver=store.resolver())
    assert result.is_ok, result
    assert result.danger_ok.status.value == "violated"
