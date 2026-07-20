// WO-155 (D264): the negative mutant of mux2.v -- `sel` is ignored,
// so the directed stimulus's sel=1 vector must catch it as a
// violated (nonzero-excess) claim, never a silent pass.
module mux2(
    input        sel,
    input  [7:0] a,
    input  [7:0] b,
    output [7:0] y
);
  assign y = a;
endmodule
