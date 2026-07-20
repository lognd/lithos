// WO-155 (D264): a NON-FIXTURE example design -- the acceptance
// criterion's "at least one NEW non-fixture example design discharges
// hdl.sim_assert for real from an ordinary build" subject. A plain
// combinational 2:1 mux, correct.
module mux2(
    input        sel,
    input  [7:0] a,
    input  [7:0] b,
    output [7:0] y
);
  assign y = sel ? b : a;
endmodule
