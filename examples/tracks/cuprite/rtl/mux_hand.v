// Hand-written realization of the `Mux` block contract
// (mux6to64.cupr): out = onehot(sel) when en else 0.
// Verilog-2005, verilator -Wall clean; authored in WO-105's
// discharge pass (the extern previously named a missing file, which
// left hdl.build honestly unreadable).
module mux_hand (
    input  wire [5:0]  sel,
    input  wire        en,
    output wire [63:0] out
);

    assign out = en ? (64'h1 << sel) : 64'h0;

endmodule
