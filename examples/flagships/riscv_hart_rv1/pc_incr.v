// pc_incr -- WO-89 (riscv phase B): the fetch datapath's PC-increment
// leaf, the flagship's FIRST behavioral body. Pure Verilog-2001 (no SV
// constructs), embedded transparently per cuprite/09 sec. 3 and bound
// to the PcIncrement contract in uarch.cupr via
// `impl PcIncrement by extern("pc_incr.v", verilog2001)`. Verilated
// (lint-elaborated) through std.hdl's `hdl.build` tier (WO-82); its
// unique `verilog2001` regime tag keeps the pack's per-fixture
// `hdl.build` model selection unambiguous (see the WO-89 ledger note
// on the same-dialect selection gap).
//
// Next-PC selection: sequential PC+4 unless a taken branch/jump
// redirects to branch_target (RV64I: PC and instruction addresses are
// byte addresses, 4-byte aligned for the base ISA -- so +4 per step).
module pc_incr (
    input  wire [63:0] pc_in,
    input  wire        sel_branch,
    input  wire [63:0] branch_target,
    output wire [63:0] pc_next
);
    wire [63:0] seq_pc = pc_in + 64'd4;
    assign pc_next = sel_branch ? branch_target : seq_pc;
endmodule
