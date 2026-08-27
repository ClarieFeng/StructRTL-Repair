module AdderTree_signed #(
    parameter width = 22
)(
    input  wire [width:1] A1,
    input  wire [width:1] A2,
    input  wire [width:1] A3,
    input  wire [width:1] A4,
    input  wire [width:1] A5,
    input  wire [width:1] A6,
    input  wire [width:1] A7,
    input  wire [width:1] A8,
    input  wire [width:1] A9,
    input  wire [width:1] A10,
    output wire [width+4:1] S
);

    localparam OUTW = width + 4;

    wire signed [OUTW-1:0] a1_ext;
    wire signed [OUTW-1:0] a2_ext;
    wire signed [OUTW-1:0] a3_ext;
    wire signed [OUTW-1:0] a4_ext;
    wire signed [OUTW-1:0] a5_ext;
    wire signed [OUTW-1:0] a6_ext;
    wire signed [OUTW-1:0] a7_ext;
    wire signed [OUTW-1:0] a8_ext;
    wire signed [OUTW-1:0] a9_ext;
    wire signed [OUTW-1:0] a10_ext;

    assign a1_ext  = {{(OUTW-width){A1[width]}},  A1[width:1]};
    assign a2_ext  = {{(OUTW-width){A2[width]}},  A2[width:1]};
    assign a3_ext  = {{(OUTW-width){A3[width]}},  A3[width:1]};
    assign a4_ext  = {{(OUTW-width){A4[width]}},  A4[width:1]};
    assign a5_ext  = {{(OUTW-width){A5[width]}},  A5[width:1]};
    assign a6_ext  = {{(OUTW-width){A6[width]}},  A6[width:1]};
    assign a7_ext  = {{(OUTW-width){A7[width]}},  A7[width:1]};
    assign a8_ext  = {{(OUTW-width){A8[width]}},  A8[width:1]};
    assign a9_ext  = {{(OUTW-width){A9[width]}},  A9[width:1]};
    assign a10_ext = {{(OUTW-width){A10[width]}}, A10[width:1]};

    wire [OUTW-1:0] l1_s0;
    wire [OUTW-1:0] l1_c0;
    wire [OUTW-1:0] l1_s1;
    wire [OUTW-1:0] l1_c1;
    wire [OUTW-1:0] l1_s2;
    wire [OUTW-1:0] l1_c2;
    wire [OUTW-1:0] l1_p0;

    wire [OUTW-1:0] l2_s0;
    wire [OUTW-1:0] l2_c0;
    wire [OUTW-1:0] l2_s1;
    wire [OUTW-1:0] l2_c1;

    wire [OUTW-1:0] l3_s0;
    wire [OUTW-1:0] l3_c0;
    wire [OUTW-1:0] l3_p0;

    wire [OUTW-1:0] l4_s0;
    wire [OUTW-1:0] l4_c0;

    wire [OUTW-1:0] l5_sum;

    csa_signed #(.W(OUTW)) u_l1_csa0 (.A(a1_ext), .B(a2_ext), .C(a3_ext), .SUM(l1_s0), .CARRY(l1_c0));
    csa_signed #(.W(OUTW)) u_l1_csa1 (.A(a4_ext), .B(a5_ext), .C(a6_ext), .SUM(l1_s1), .CARRY(l1_c1));
    csa_signed #(.W(OUTW)) u_l1_csa2 (.A(a7_ext), .B(a8_ext), .C(a9_ext), .SUM(l1_s2), .CARRY(l1_c2));

    assign l1_p0 = a10_ext;

    csa_signed #(.W(OUTW)) u_l2_csa0 (.A(l1_s0), .B(l1_c0), .C(l1_s1), .SUM(l2_s0), .CARRY(l2_c0));
    csa_signed #(.W(OUTW)) u_l2_csa1 (.A(l1_c1), .B(l1_s2), .C(l1_c2), .SUM(l2_s1), .CARRY(l2_c1));
    csa_signed #(.W(OUTW)) u_l3_csa0 (.A(l2_s0), .B(l2_c0), .C(l2_s1), .SUM(l3_s0), .CARRY(l3_c0));

    assign l3_p0 = l2_c1 + l1_p0;

    csa_signed #(.W(OUTW)) u_l4_csa0 (.A(l3_s0), .B(l3_c0), .C(l3_p0), .SUM(l4_s0), .CARRY(l4_c0));

    assign l5_sum = l4_s0 + l4_c0;
    assign S[width+4:1] = $signed(a1_ext) + $signed(a2_ext) + $signed(a3_ext) + $signed(a4_ext) + $signed(a5_ext) +
                          $signed(a6_ext) + $signed(a7_ext) + $signed(a8_ext) + $signed(a9_ext) + $signed(a10_ext);

endmodule

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
