// bad_syntax.v -- WO-82 negative fixture for hdl.build: a deliberately
// malformed module (unterminated always block) so `verilator
// --lint-only` fails with a real diagnostic and hdl.build renders
// INDETERMINATE (never a crash, never a false pass).

module broken (
    input  wire clk,
    output reg  q
);
    always @(posedge clk) begin
        q <= ~q
    // missing `end` and missing semicolon: parse error by construction
endmodule
