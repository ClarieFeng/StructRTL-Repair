
module csa_signed #(
    parameter W = 24
)(
    input  wire [W-1:0] A,
    input  wire [W-1:0] B,
    input  wire [W-1:0] C,
    output wire [W-1:0] SUM,
    output wire [W-1:0] CARRY
);
    genvar i;
    generate
        for (i = 0; i < W; i = i + 1) begin : gen_csa
            assign {CARRY[i], SUM[i]} = A[i] + B[i] + C[i];
        end
    endgenerate
endmodule
