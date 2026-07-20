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
    STIMULUS_KIND,
    STIMULUS_PORT,
    HdlBuildModel,
    HdlEquivDirectedModel,
    HdlSimAssertGenericModel,
    HdlSimAssertModel,
)
from regolith.harness.models.hdl.verilator_adapter import ToolFailure
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
    model = HdlBuildModel()
    result = model.discharge(req, registry_version="test", resolver=store.resolver())
    assert result.is_ok, result
    assert result.danger_ok.status.value == "discharged"


def test_hdl_build_is_the_same_model_instance_for_every_dialect(
    store: PayloadStore,
) -> None:
    """D202: `hdl.build` is source-generic -- ONE model discharges
    counter (verilog2005) and alu_generic (sv2017) alike, each against
    ITS OWN request bytes/filename, never a fixture-pinned top module.
    This is the direct regression test for the WO-89 collision: two
    same-dialect (or, here, cross-dialect) requests through the SAME
    model instance must each verilate their own correct top module."""
    model = HdlBuildModel()
    fx_a = FIXTURES_BY_ID["counter"]
    fx_b = FIXTURES_BY_ID["alu_generic"]
    req_a = _build_request(
        store,
        (_EXAMPLES_HDL / fx_a.hdl_filename).read_bytes(),
        fx_a.regime,
        fx_a.hdl_filename,
    )
    req_b = _build_request(
        store,
        (_EXAMPLES_HDL / fx_b.hdl_filename).read_bytes(),
        fx_b.regime,
        fx_b.hdl_filename,
    )
    result_a = model.discharge(
        req_a, registry_version="test", resolver=store.resolver()
    )
    result_b = model.discharge(
        req_b, registry_version="test", resolver=store.resolver()
    )
    assert result_a.is_ok and result_a.danger_ok.status.value == "discharged"
    assert result_b.is_ok and result_b.danger_ok.status.value == "discharged"


def test_hdl_build_assertions_map_indeterminate_named(store: PayloadStore) -> None:
    """assertions_map.sv uses deep SVA sequence algebra (`##[1:4]`,
    `throughout`, `[*..]`) verilator's front-end does not accept
    (cuprite/09 sec. 2's own PARTIAL-mapping call, verified by tool
    failure rather than assumed) -- hdl.build renders indeterminate
    with the real diagnostic cited, never a crash."""
    fx = FIXTURES_BY_ID["assertions_map"]
    data = (_EXAMPLES_HDL / fx.hdl_filename).read_bytes()
    req = _build_request(store, data, fx.regime, fx.hdl_filename)
    model = HdlBuildModel()
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
    model = HdlBuildModel()
    result = model.discharge(req, registry_version="test", resolver=store.resolver())
    assert result.is_err
    assert isinstance(result.danger_err, DomainError)


def test_hdl_build_vhdl_defers_named_reason(store: PayloadStore) -> None:
    fx = FIXTURES_BY_ID["fsm_traffic"]
    data = (_EXAMPLES_HDL / fx.hdl_filename).read_bytes()
    req = _build_request(store, data, fx.regime, fx.hdl_filename)
    model = HdlBuildModel()
    result = model.discharge(req, registry_version="test", resolver=store.resolver())
    assert result.is_err
    assert isinstance(result.danger_err, DomainError)
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

    def _forced_absent(
        name: str, *, use_cache: bool = True, probe_version: bool = True
    ) -> toolenv.ToolStatus:
        return toolenv.resolve(
            name,
            which_fn=lambda n: None,
            use_cache=use_cache,
            probe_version=probe_version,
        )

    monkeypatch.setattr(hdl_models, "resolve_tool", _forced_absent)
    fx = FIXTURES_BY_ID["fsm_traffic"]
    data = (_EXAMPLES_HDL / fx.hdl_filename).read_bytes()
    req = _build_request(store, data, fx.regime, fx.hdl_filename)
    model = HdlBuildModel()
    result = model.discharge(req, registry_version="test", resolver=store.resolver())
    assert result.is_err
    assert isinstance(result.danger_err, DomainError)
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


# --- WO-155 (D264): the source-generic hdl.sim_assert gate ------------

_FIXTURES_HDL_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "hdl"

_MUX_STIMULUS = {
    "top_module": "mux2",
    "ports": [
        {"name": "sel", "width": 1, "direction": "in"},
        {"name": "a", "width": 8, "direction": "in"},
        {"name": "b", "width": 8, "direction": "in"},
        {"name": "y", "width": 8, "direction": "out"},
    ],
    "vectors": [
        {
            "name": "sel_low_passes_a",
            "inputs": [
                {"signal": "sel", "value": "1'b0"},
                {"signal": "a", "value": "8'h11"},
                {"signal": "b", "value": "8'h22"},
            ],
            "expect": [{"signal": "y", "expected": "8'h11"}],
        },
        {
            "name": "sel_high_passes_b",
            "inputs": [{"signal": "sel", "value": "1'b1"}],
            "expect": [{"signal": "y", "expected": "8'h22"}],
        },
    ],
    "method": "hand-typed directed vectors (WO-155 recon)",
    "trust_tier": "authored",
}


# frob:ticket T-0025
def _build_sim_request(
    store: PayloadStore, src: bytes, stimulus: dict, *, regime: str = "verilog2001"
) -> DischargeRequest:
    import json

    src_digest = store.put(src)
    stim_digest = store.put(json.dumps(stimulus).encode("utf-8"))
    return DischargeRequest(
        claim_kind="hdl.sim_assert",
        limit=0.0,
        inputs={},
        payloads={
            SRC_PORT: PayloadRef(kind=SRC_KIND, digest=src_digest, origin="mux2.v"),
            STIMULUS_PORT: PayloadRef(
                kind=STIMULUS_KIND,
                digest=stim_digest,
                origin="mux_directed_vectors",
            ),
        },
        regimes=(regime,),
    )


# frob:ticket T-0025
def test_hdl_sim_assert_generic_discharges_a_non_fixture_design(
    store: PayloadStore,
) -> None:
    """The acceptance criterion: a NEW, non-fixture example design (a
    plain 2:1 mux, never registered as a `FixtureSpec`) discharges
    `hdl.sim_assert` for real through the source-generic model."""
    src = (_FIXTURES_HDL_DIR / "mux2.v").read_bytes()
    req = _build_sim_request(store, src, _MUX_STIMULUS)
    model = HdlSimAssertGenericModel()
    result = model.discharge(req, registry_version="test", resolver=store.resolver())
    assert result.is_ok, result
    assert result.danger_ok.status.value == "discharged"


# frob:ticket T-0025
def test_hdl_sim_assert_generic_catches_a_violation(store: PayloadStore) -> None:
    """The negative fixture (`mux2_broken.v`, sel ignored) must be caught
    as a violated (nonzero-excess) claim, never a silent pass."""
    src = (_FIXTURES_HDL_DIR / "mux2_broken.v").read_bytes()
    req = _build_sim_request(store, src, _MUX_STIMULUS)
    model = HdlSimAssertGenericModel()
    result = model.discharge(req, registry_version="test", resolver=store.resolver())
    assert result.is_ok, result
    assert result.danger_ok.status.value == "violated"


# frob:ticket T-0025
def test_hdl_sim_assert_generic_defers_on_tool_absence(
    store: PayloadStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A missing/broken verilator tool renders INDETERMINATE, never a
    fabricated pass (the named-deferral half of the two-tier honesty
    posture, D264 ruling 1)."""

    def _absent(*_args: object, **_kwargs: object):
        from typani.result import Err as _Err

        return _Err(
            ToolFailure(
                tool="verilator",
                version=None,
                argv=("verilator",),
                returncode=None,
                stderr_excerpt="",
                kind="not_found",
            )
        )

    monkeypatch.setattr("regolith.harness.models.hdl.models.run_verilator", _absent)
    src = (_FIXTURES_HDL_DIR / "mux2.v").read_bytes()
    req = _build_sim_request(store, src, _MUX_STIMULUS)
    model = HdlSimAssertGenericModel()
    result = model.discharge(req, registry_version="test", resolver=store.resolver())
    assert result.is_err
    assert isinstance(result.danger_err, DomainError)


# frob:ticket T-0025
def test_hdl_sim_assert_generic_refuses_a_non_authored_stimulus_tier(
    store: PayloadStore,
) -> None:
    """E1105 (STIMULUS_PROVENANCE_UNAUTHORED): a stimulus payload
    claiming a `model`/`measured` trust tier is refused before it ever
    reaches the pydantic constructor (D260 ruling 3, INV-35 leg (b))."""
    bad_stimulus = dict(_MUX_STIMULUS, trust_tier="model")
    src = (_FIXTURES_HDL_DIR / "mux2.v").read_bytes()
    req = _build_sim_request(store, src, bad_stimulus)
    model = HdlSimAssertGenericModel()
    result = model.discharge(req, registry_version="test", resolver=store.resolver())
    assert result.is_err
    assert isinstance(result.danger_err, DomainError)
    assert "E1105" in result.danger_err.message


# frob:ticket T-0025
def test_hdl_sim_assert_generic_does_not_match_a_request_with_no_stimulus() -> None:
    """A request carrying only `hdl_src` (no `sim_stimulus` payload)
    never matches the generic model's signature -- the structural
    trigger this WO requires before any sim discharge is attempted."""
    model = HdlSimAssertGenericModel()
    req = DischargeRequest(
        claim_kind="hdl.sim_assert",
        limit=0.0,
        inputs={},
        payloads={
            SRC_PORT: PayloadRef(kind=SRC_KIND, digest="blake3:x", origin="mux2.v")
        },
        regimes=("verilog2001",),
    )
    assert not model.signature.accepts_payloads(req.payload_ports())
