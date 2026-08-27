module prefix_black_cell_medium (
    input wire p_hi,
    input wire g_hi,
    input wire p_lo,
    input wire g_lo,
    output wire p_out,
    output wire g_out
);
    assign p_out = p_hi & p_lo;
    assign g_out = g_hi | (p_hi & g_lo);
endmodule

module PPA_Kogge_Stone_21bit #(
    parameter width = 21
) (
    input wire [width-1:0] A,
    input wire [width-1:0] B,
    input wire cin,
    output wire [width-1:0] S,
    output wire cout
);
    wire [width-1:0] p0;
    wire [width-1:0] g0;
    wire [width-1:0] p1;
    wire [width-1:0] g1;
    wire [width-1:0] p2;
    wire [width-1:0] g2;
    wire [width-1:0] p3;
    wire [width-1:0] g3;
    wire [width-1:0] p4;
    wire [width-1:0] g4;
    wire [width-1:0] p5;
    wire [width-1:0] g5;
    wire [width:0] carry;
    genvar i;

    generate
        for (i = 0; i < width; i = i + 1) begin: bit_gp
            assign p0[i] = A[i] ^ B[i];
            assign g0[i] = A[i] & B[i];
        end
    endgenerate

    generate
        for (i = 0; i < 1; i = i + 1) begin: stage1_copy
            assign p1[i] = p0[i];
            assign g1[i] = g0[i];
        end
        for (i = 1; i < width; i = i + 1) begin: stage1_merge
            prefix_black_cell_medium u_stage1 (
                .p_hi(p0[i]),
                .g_hi(g0[i]),
                .p_lo(p0[i-1]),
                .g_lo(g0[i-1]),
                .p_out(p1[i]),
                .g_out(g1[i])
            );
        end
    endgenerate

    generate
        for (i = 0; i < 2; i = i + 1) begin: stage2_copy
            assign p2[i] = p1[i];
            assign g2[i] = g1[i];
        end
        for (i = 2; i < width; i = i + 1) begin: stage2_merge
            prefix_black_cell_medium u_stage2 (
                .p_hi(p1[i]),
                .g_hi(g1[i]),
                .p_lo(p1[i-2]),
                .g_lo(g1[i-2]),
                .p_out(p2[i]),
                .g_out(g2[i])
            );
        end
    endgenerate

    generate
        for (i = 0; i < 4; i = i + 1) begin: stage4_copy
            assign p3[i] = p2[i];
            assign g3[i] = g2[i];
        end
        for (i = 4; i < width; i = i + 1) begin: stage4_merge
            prefix_black_cell_medium u_stage4 (
                .p_hi(p2[i]),
                .g_hi(g2[i]),
                .p_lo(p2[i-4]),
                .g_lo(g2[i-4]),
                .p_out(p3[i]),
                .g_out(g3[i])
            );
        end
    endgenerate

    generate
        for (i = 0; i < 8; i = i + 1) begin: stage8_copy
            assign p4[i] = p3[i];
            assign g4[i] = g3[i];
        end
        for (i = 8; i < width; i = i + 1) begin: stage8_merge
            prefix_black_cell_medium u_stage8 (
                .p_hi(p3[i]),
                .g_hi(g3[i]),
                .p_lo(p3[i-8]),
                .g_lo(g3[i-8]),
                .p_out(p4[i]),
                .g_out(g4[i])
            );
        end
    endgenerate

    generate
        for (i = 0; i < 16; i = i + 1) begin: stage16_copy
            assign p5[i] = p4[i];
            assign g5[i] = g4[i];
        end
        for (i = 16; i < width; i = i + 1) begin: stage16_merge
            prefix_black_cell_medium u_stage16 (
                .p_hi(p4[i]),
                .g_hi(g4[i]),
                .p_lo(p4[i-16]),
                .g_lo(g4[i-16]),
                .p_out(p5[i]),
                .g_out(g5[i])
            );
        end
    endgenerate

    assign carry[0] = cin;
    generate
        for (i = 0; i < width; i = i + 1) begin: sum_stage
            assign carry[i+1] = g5[i] | (p5[i] & cin);
            assign S[i] = p0[i] ^ carry[i];
        end
    endgenerate

    assign cout = carry[width];
endmodule
