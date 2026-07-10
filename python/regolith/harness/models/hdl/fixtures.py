"""The `examples/hdl/` (cuprite/09 D120) fixture registry (WO-82).

One :class:`FixtureSpec` per calibration-corpus pair -- the SAME five
pairs cuprite/09-hdl-coverage.md sec. 5 names (counter, alu_generic,
fsm_traffic, fifo_cdc, assertions_map). Each spec names its top
module, its HDL regime tag (matches the `.cupr` fixture's own `impl
... by extern(ref, <regime>)` tag exactly), and -- ONLY where this
dispatch built one -- a hand-authored SystemVerilog testbench that
drives directed vectors through the DUT via `verilator --binary` and
prints machine-parseable result lines (`_OUTPUT_GRAMMAR` below).

Coverage is DELIBERATELY partial and named as such (never silently):
`hdl.build` (verilate/lint) is generic and works for every non-VHDL
fixture; `hdl.sim_assert`/`hdl.equiv_directed` (testbench-driven) are
built end-to-end ONLY for `counter` this dispatch -- see the WO-82
ledger for the scope cut and its reason (per-fixture testbench
authoring for combinational/CDC/SVA shapes was not budgeted).
`fsm_traffic` is VHDL; verilator has no VHDL front-end and this
environment has no `ghdl`, so EVERY hdl.* claim defers for it (named
reason: "no VHDL frontend available").

Output grammar a testbench prints on its stdout (parsed by
`models.py`, never by scraping stderr -- stderr is logs per AD-19):
    PASS <name> cycle=<c> value=<v>
    ASSERT FAIL <name> cycle=<c> expected=<e> got=<g>
    SIM_OK vectors=<n>
    SIM_FAIL vectors=<n> errors=<m>
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

# --- regime tags (must match the paired `.cupr` fixture's `by extern`
# format tag exactly, cuprite/09 sec. 3) --------------------------------

REGIME_VERILOG2005 = "verilog2005"
REGIME_SV2017 = "sv2017"
REGIME_VHDL2008 = "vhdl2008"

VHDL_REGIMES = frozenset({REGIME_VHDL2008})


class FixtureSpec(BaseModel):
    """One `examples/hdl/` pair's verilator-facing shape."""

    model_config = ConfigDict(frozen=True)

    fixture_id: str
    hdl_filename: str  # relative to examples/hdl/
    top_module: str
    regime: str
    is_sv: bool = False
    # Present only when this dispatch built an end-to-end sim harness
    # (counter only, D189/WO-82 scope cut -- see fixtures.py module doc).
    testbench_src: str | None = None
    testbench_top: str = "tb"
    vector_count: int = 0
    oracle_note: str = ""


# --- counter: full sim_assert + equiv_directed harness ------------------
#
# The directed vectors below are TRANSCRIBED BY HAND from
# `counter.cupr`'s `spec:` block (priority load over count-enable,
# `tc = and_reduce(q)`) -- an ORACLE-TRANSCRIBED REFERENCE, explicitly
# NOT compiler-executed (WO-82 close-out ledger: cuprite's
# `ConverterGraph` has no Python-reachable evaluation FFI today,
# `regolith-lower::converter`/`regolith-sem::converter` are Rust-
# internal; building one is a cycle-33 follow-up the coordinator
# logged on ACK). Every expected value below is therefore a stand-in
# for "what the spec text says", not "what the real compiler computed"
# -- the model id/version and every evidence note say so explicitly so
# this tier is never mistaken for a compiler-verified or formal result.
_COUNTER_TB = r"""
module tb;
  logic clk = 0, rst_n = 0, en = 0, load = 0;
  logic [7:0] d = 0;
  logic [7:0] q;
  logic tc;
  int cyc = 0;
  int errors = 0;
  int vectors = 0;

  counter #(.W(8)) dut(
    .clk(clk), .rst_n(rst_n), .en(en), .load(load),
    .d(d), .q(q), .tc(tc)
  );

  always #5 clk = ~clk;

  task automatic check(string name, logic [7:0] expected_q, logic expected_tc);
    vectors++;
    if (q !== expected_q) begin
      errors++;
      $display("ASSERT FAIL %s cycle=%0d expected=%0d got=%0d",
                name, cyc, expected_q, q);
    end else if (tc !== expected_tc) begin
      errors++;
      $display("ASSERT FAIL %s_tc cycle=%0d expected=%0d got=%0d",
                name, cyc, expected_tc, tc);
    end else begin
      $display("PASS %s cycle=%0d value=%0d", name, cyc, q);
    end
  endtask

  initial begin
    // vector 1: async reset holds q at 0 (oracle: rst_n deasserted -> q=0)
    rst_n = 0; en = 0; load = 0; d = 0;
    @(negedge clk); @(negedge clk);
    rst_n = 1;
    check("reset", 8'd0, 1'b0);

    // vectors 2-4: enable counts up (oracle: q <= q + 1 when en, priority load n/a)
    en = 1;
    for (int i = 1; i <= 3; i++) begin
      @(posedge clk); cyc++; #1;
      check($sformatf("count_%0d", i), 8'(i), 1'b0);
    end

    // vector 5: load takes priority over enable (oracle: q <= d when load,
    // even though en is still asserted -- the `.cupr` spec's `on clk.rise`
    // block lists `load` before `en`, matching the Verilog's if/else if)
    load = 1; d = 8'hFE;
    @(posedge clk); cyc++; #1;
    check("load_priority", 8'hFE, 1'b0);

    // vector 6: tc asserts when q reaches all-ones (oracle: tc = and_reduce(q))
    load = 0; en = 1; d = 0;
    @(posedge clk); cyc++; #1;  // q: FE -> FF
    check("terminal_count", 8'hFF, 1'b1);

    // vector 7: wraps to 0, tc deasserts
    @(posedge clk); cyc++; #1;  // q: FF -> 00
    check("wrap", 8'd0, 1'b0);

    if (errors == 0) $display("SIM_OK vectors=%0d", vectors);
    else $display("SIM_FAIL vectors=%0d errors=%0d", vectors, errors);
    $finish;
  end
endmodule
"""

FIXTURES: tuple[FixtureSpec, ...] = (
    FixtureSpec(
        fixture_id="counter",
        hdl_filename="counter.v",
        top_module="counter",
        regime=REGIME_VERILOG2005,
        is_sv=False,
        testbench_src=_COUNTER_TB,
        vector_count=7,
        oracle_note=(
            "oracle-transcribed reference (counter.cupr spec: block), "
            "NOT compiler-executed -- see WO-82 ledger"
        ),
    ),
    FixtureSpec(
        fixture_id="alu_generic",
        hdl_filename="alu_generic.sv",
        top_module="alu_generic",
        regime=REGIME_SV2017,
        is_sv=True,
    ),
    FixtureSpec(
        fixture_id="fifo_cdc",
        hdl_filename="fifo_cdc.sv",
        top_module="fifo_cdc",
        regime=REGIME_SV2017,
        is_sv=True,
    ),
    FixtureSpec(
        fixture_id="assertions_map",
        hdl_filename="assertions_map.sv",
        top_module="req_gnt_checker",
        regime=REGIME_SV2017,
        is_sv=True,
    ),
    FixtureSpec(
        fixture_id="fsm_traffic",
        hdl_filename="fsm_traffic.vhd",
        top_module="fsm_traffic",
        regime=REGIME_VHDL2008,
        is_sv=False,
    ),
)

FIXTURES_BY_ID: dict[str, FixtureSpec] = {f.fixture_id: f for f in FIXTURES}

# Fixtures with an end-to-end testbench this dispatch built (sim_assert
# + equiv_directed); every other non-VHDL fixture gets `hdl.build` only.
SIMULATED_FIXTURE_IDS: frozenset[str] = frozenset(
    f.fixture_id for f in FIXTURES if f.testbench_src is not None
)

__all__ = [
    "FIXTURES",
    "FIXTURES_BY_ID",
    "REGIME_SV2017",
    "REGIME_VERILOG2005",
    "REGIME_VHDL2008",
    "SIMULATED_FIXTURE_IDS",
    "VHDL_REGIMES",
    "FixtureSpec",
]
