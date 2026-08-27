module bk_prefix_tree_medium #(
    parameter width = 20
) (
    input wire [width-1:0] p_in,
    input wire [width-1:0] g_in,
    output wire [width-1:0] p_out,
    output wire [width-1:0] g_out
);
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
    genvar i;

    generate
        for (i = 0; i < 1; i = i + 1) begin: stage1_copy
            assign p1[i] = p_in[i];
            assign g1[i] = g_in[i];
        end
        for (i = 1; i < width; i = i + 1) begin: stage1_merge
            assign p1[i] = p_in[i] & p_in[i-1];
            assign g1[i] = g_in[i] | (p_in[i] & g_in[i-1]);
        end
    endgenerate

    generate
        for (i = 0; i < 2; i = i + 1) begin: stage2_copy
            assign p2[i] = p1[i];
            assign g2[i] = g1[i];
        end
        for (i = 2; i < width; i = i + 1) begin: stage2_merge
            assign p2[i] = p1[i] & p1[i-2];
            assign g2[i] = g1[i] | (p1[i] & g1[i-2]);
        end
    endgenerate

    generate
        for (i = 0; i < 4; i = i + 1) begin: stage4_copy
            assign p3[i] = p2[i];
            assign g3[i] = g2[i];
        end
        for (i = 4; i < width; i = i + 1) begin: stage4_merge
            assign p3[i] = p2[i] & p2[i-4];
            assign g3[i] = g2[i] | (p2[i] & g2[i-4]);
        end
    endgenerate

    generate
        for (i = 0; i < 8; i = i + 1) begin: stage8_copy
            assign p4[i] = p3[i];
            assign g4[i] = g3[i];
        end
        for (i = 8; i < width; i = i + 1) begin: stage8_merge
            assign p4[i] = p3[i] & p3[i-8];
            assign g4[i] = g3[i] | (p3[i] & g3[i-8]);
        end
    endgenerate

    generate
        for (i = 0; i < 16; i = i + 1) begin: stage16_copy
            assign p5[i] = p4[i];
            assign g5[i] = g4[i];
        end
        for (i = 16; i < width; i = i + 1) begin: stage16_merge
            assign p5[i] = p4[i] & p4[i-16];
            assign g5[i] = g4[i] | (p4[i] & g4[i-16]);
        end
    endgenerate

    assign p_out = p5;
    assign g_out = g5;
endmodule

module PPA_Brent_Kung_20bit #(
    parameter width = 20
) (
    input wire [width-1:0] A,
    input wire [width-1:0] B,
    input wire cin,
    output wire [width-1:0] S,
    output wire cout
);
    wire [width-1:0] p0;
    wire [width-1:0] g0;
    wire [width-1:0] p5;
    wire [width-1:0] g5;
    wire [width:0] carry;
    genvar j;

    generate
        for (j = 0; j < width; j = j + 1) begin: bit_gp
            assign p0[j] = A[j] ^ B[j];
            assign g0[j] = A[j] & B[j];
        end
    endgenerate

    bk_prefix_tree_medium #(.width(width)) u_tree (
        .p_in(p0),
        .g_in(g0),
        .p_out(p5),
        .g_out(g5)
    );

    assign carry[0] = cin;
    generate
        for (j = 0; j < width; j = j + 1) begin: sum_chain
            assign carry[j+1] = g5[j] | (p5[j] & cin);
            assign S[j] = p0[j] ^ carry[j];
        end
    endgenerate

    assign cout = carry[width];
endmodule

