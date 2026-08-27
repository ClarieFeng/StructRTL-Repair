module prefix_black_cell (
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

module prefix_stage_shift #(
    parameter width = 24,
    parameter SHIFT = 1
) (
    input wire [width-1:0] p_in,
    input wire [width-1:0] g_in,
    output wire [width-1:0] p_out,
    output wire [width-1:0] g_out
);
    genvar i;

    generate
        for (i = 0; i < SHIFT; i = i + 1) begin: copy_low
            assign p_out[i] = p_in[i];
            assign g_out[i] = g_in[i];
        end

        for (i = SHIFT; i < width; i = i + 1) begin: combine
            prefix_black_cell u_cell (
                .p_hi(p_in[i]),
                .g_hi(g_in[i]),
                .p_lo(p_in[i-SHIFT]),
                .g_lo(g_in[i-SHIFT]),
                .p_out(p_out[i]),
                .g_out(g_out[i])
            );
        end
    endgenerate
endmodule

module prefix_sum_resolver #(
    parameter width = 24
) (
    input wire [width-1:0] p0,
    input wire [width-1:0] p_final,
    input wire [width-1:0] g_final,
    input wire cin,
    output wire [width-1:0] S,
    output wire cout
);
    wire [width:0] carry;
    genvar k;

    assign carry[0] = cin;

    generate
        for (k = 0; k < width; k = k + 1) begin: sum_path
            assign carry[k+1] = g_final[k] | (p_final[k] & cin);
            assign S[k] = p0[k] ^ carry[k];
        end
    endgenerate

    assign cout = carry[width];
endmodule

module prefix_finalize_stage #(
    parameter width = 24
) (
    input wire [width-1:0] p0,
    input wire [width-1:0] p5,
    input wire [width-1:0] g5,
    input wire cin,
    output wire [width-1:0] S,
    output wire cout
);
    prefix_sum_resolver #(.width(width)) u_sum_resolver (
        .p0(p0),
        .p_final(p5),
        .g_final(g5),
        .cin(cin),
        .S(S),
        .cout(cout)
    );
endmodule

module PPA_Kogge_Stone_24bit #(
    parameter width = 24
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
    genvar j;

    generate
        for (j = 0; j < width; j = j + 1) begin: bit_gp
            assign p0[j] = A[j] ^ B[j];
            assign g0[j] = A[j] & B[j];
        end
    endgenerate

    prefix_stage_shift #(.width(width), .SHIFT(1)) stage1 (
        .p_in(p0),
        .g_in(g0),
        .p_out(p1),
        .g_out(g1)
    );

    prefix_stage_shift #(.width(width), .SHIFT(2)) stage2 (
        .p_in(p1),
        .g_in(g1),
        .p_out(p2),
        .g_out(g2)
    );

    prefix_stage_shift #(.width(width), .SHIFT(4)) stage4 (
        .p_in(p2),
        .g_in(g2),
        .p_out(p3),
        .g_out(g3)
    );

    prefix_stage_shift #(.width(width), .SHIFT(8)) stage8 (
        .p_in(p3),
        .g_in(g3),
        .p_out(p4),
        .g_out(g4)
    );

    prefix_stage_shift #(.width(width), .SHIFT(16)) stage16 (
        .p_in(p4),
        .g_in(g4),
        .p_out(p5),
        .g_out(g5)
    );

    prefix_finalize_stage #(.width(width)) u_finalize (
        .p0(p0),
        .p5(p5),
        .g5(g5),
        .cin(cin),
        .S(S),
        .cout(cout)
    );
endmodule
