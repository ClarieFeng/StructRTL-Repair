module u11_triplet_sum #(
    parameter width = 23
) (
    input wire [width:1] A,
    input wire [width:1] B,
    input wire [width:1] C,
    output wire [width+2:1] S
);
    assign S = {2'b0, A} + {2'b0, B} + {2'b0, C};
endmodule

module u11_pair_sum #(
    parameter width = 25
) (
    input wire [width:1] A,
    input wire [width:1] B,
    output wire [width+1:1] S
);
    assign S = {1'b0, A} + {1'b0, B};
endmodule

module u11_prefix_stage #(
    parameter width = 26,
    parameter SHIFT = 1
) (
    input wire [width:1] p_in,
    input wire [width:1] g_in,
    output wire [width:1] p_out,
    output wire [width:1] g_out
);
    genvar i;

    generate
        for (i = 1; i <= SHIFT; i = i + 1) begin: copy_low
            assign p_out[i] = p_in[i];
            assign g_out[i] = g_in[i];
        end
        for (i = SHIFT + 1; i <= width; i = i + 1) begin: combine
            assign p_out[i] = p_in[i] & p_in[i-SHIFT];
            assign g_out[i] = g_in[i] | (p_in[i] & g_in[i-SHIFT]);
        end
    endgenerate
endmodule

module u11_prefix_adder #(
    parameter width = 26
) (
    input wire [width:1] A,
    input wire [width:1] B,
    input wire cin,
    output wire [width:1] S,
    output wire cout
);
    wire [width:1] p0;
    wire [width:1] g0;
    wire [width:1] p1;
    wire [width:1] g1;
    wire [width:1] p2;
    wire [width:1] g2;
    wire [width:1] p3;
    wire [width:1] g3;
    wire [width:1] p4;
    wire [width:1] g4;
    wire [width:1] p5;
    wire [width:1] g5;
    wire [width:0] carry;
    genvar j;

    generate
        for (j = 1; j <= width; j = j + 1) begin: gp
            assign p0[j] = A[j] ^ B[j];
            assign g0[j] = A[j] & B[j];
        end
    endgenerate

    u11_prefix_stage #(.width(width), .SHIFT(1)) s1 (.p_in(p0), .g_in(g0), .p_out(p1), .g_out(g1));
    u11_prefix_stage #(.width(width), .SHIFT(2)) s2 (.p_in(p1), .g_in(g1), .p_out(p2), .g_out(g2));
    u11_prefix_stage #(.width(width), .SHIFT(4)) s4 (.p_in(p2), .g_in(g2), .p_out(p3), .g_out(g3));
    u11_prefix_stage #(.width(width), .SHIFT(8)) s8 (.p_in(p3), .g_in(g3), .p_out(p4), .g_out(g4));
    u11_prefix_stage #(.width(width), .SHIFT(16)) s16 (.p_in(p4), .g_in(g4), .p_out(p5), .g_out(g5));

    assign carry[0] = cin;
    generate
        for (j = 1; j <= width; j = j + 1) begin: sum
            assign carry[j] = g5[j] | (p5[j] & cin);
            assign S[j] = p0[j] ^ carry[j-1];
        end
    endgenerate

    assign cout = carry[width];
endmodule

module u11_reduce_tree_high #(
    parameter width = 23
) (
    input wire [width:1] A1,
    input wire [width:1] A2,
    input wire [width:1] A3,
    input wire [width:1] A4,
    input wire [width:1] A5,
    input wire [width:1] A6,
    input wire [width:1] A7,
    input wire [width:1] A8,
    input wire [width:1] A9,
    output wire [width+4:1] S
);
    wire [width+2:1] g0;
    wire [width+2:1] g1;
    wire [width+2:1] g2;
    wire [width+3:1] h0;
    wire [width+3:1] pref_sum;
    wire pref_cout;
    wire [width+3:1] g2_ext;

    u11_triplet_sum #(.width(width)) u0 (.A(A1), .B(A2), .C(A3), .S(g0));
    u11_triplet_sum #(.width(width)) u1 (.A(A4), .B(A5), .C(A6), .S(g1));
    u11_triplet_sum #(.width(width)) u2 (.A(A7), .B(A8), .C(A9), .S(g2));
    u11_pair_sum #(.width(width+2)) u3 (.A(g0), .B(g1), .S(h0));
    assign g2_ext = {1'b0, g2};
    u11_prefix_adder #(.width(width+3)) u4 (
        .A(h0),
        .B(g2_ext),
        .cin(1'b0),
        .S(pref_sum),
        .cout(pref_cout)
    );
    assign S[width+3:1] = pref_sum;
    assign S[width+4] = pref_cout;
endmodule

module addertree_23_9_PPA_Kogge_Stone #(
    parameter width = 23
) (
    input wire [width:1] A1,
    input wire [width:1] A2,
    input wire [width:1] A3,
    input wire [width:1] A4,
    input wire [width:1] A5,
    input wire [width:1] A6,
    input wire [width:1] A7,
    input wire [width:1] A8,
    input wire [width:1] A9,
    output wire [width + 4:1] S
);
    u11_reduce_tree_high #(.width(width)) u0 (
        .A1(A1), .A2(A2), .A3(A3),
        .A4(A4), .A5(A5), .A6(A6),
        .A7(A7), .A8(A8), .A9(A9),
        .S(S)
    );
endmodule

