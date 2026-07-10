// counter_broken_priority.v -- WO-82 negative fixture (NOT one of the
// cuprite/09 D120 pairs; a deliberately mutated copy of
// examples/hdl/counter.v for hdl.sim_assert/hdl.equiv_directed's
// broken-variant coverage). Bug: `en` is checked BEFORE `load`, so
// enable wins over a simultaneous load -- the counter.cupr spec (and
// the real counter.v) give load PRIORITY over enable. This flips the
// "load_priority" directed vector's expected result, which is exactly
// what should be caught (never silently missed).

module tc_decode #(
    parameter W = 8
) (
    input  wire [W-1:0] value,
    output wire         tc
);
    assign tc = &value;
endmodule

module counter #(
    parameter W = 8
) (
    input  wire         clk,
    input  wire         rst_n,
    input  wire         en,
    input  wire         load,
    input  wire [W-1:0] d,
    output reg  [W-1:0] q,
    output wire         tc
);

    // BUG (intentional, negative fixture): en checked first -- load
    // no longer has priority, unlike the real counter.v / counter.cupr.
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            q <= {W{1'b0}};
        else if (en)
            q <= q + {{(W-1){1'b0}}, 1'b1};
        else if (load)
            q <= d;
    end

    tc_decode #(.W(W)) u_tc (
        .value (q),
        .tc    (tc)
    );

endmodule
