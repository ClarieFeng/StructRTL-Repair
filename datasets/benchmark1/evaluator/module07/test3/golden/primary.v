module b7_cla_2bit #(
    parameter width = 2
) (
    input wire [width:1] A,
    input wire [width:1] B,
    input wire cin,
    output wire [width:1] S,
    output wire cout,
    output wire p_1_2,
    output wire g_1_2
);
    wire [width:1] p;
    wire [width:1] g;
    wire c1;

    assign p = A ^ B;
    assign g = A & B;
    assign p_1_2 = p[1] & p[2];
    assign g_1_2 = g[2] | (g[1] & p[2]);
    assign S[1] = p[1] ^ cin;
    assign c1 = g[1] | (p[1] & cin);
    assign S[2] = p[2] ^ c1;
    assign cout = g_1_2 | (p_1_2 & cin);
endmodule

module b7_cla_4bit #(
    parameter width = 4
) (
    input wire [width:1] A,
    input wire [width:1] B,
    input wire cin,
    output wire [width:1] S,
    output wire cout,
    output wire p_1_4,
    output wire g_1_4
);
    wire c2;
    wire p_1_2, g_1_2;
    wire p_3_4, g_3_4;

    b7_cla_2bit #(.width(2)) u0 (
        .A(A[2:1]),
        .B(B[2:1]),
        .cin(cin),
        .S(S[2:1]),
        .cout(c2),
        .p_1_2(p_1_2),
        .g_1_2(g_1_2)
    );
    b7_cla_2bit #(.width(2)) u1 (
        .A(A[4:3]),
        .B(B[4:3]),
        .cin(c2),
        .S(S[4:3]),
        .cout(cout),
        .p_1_2(p_3_4),
        .g_1_2(g_3_4)
    );
    assign p_1_4 = p_1_2 & p_3_4;
    assign g_1_4 = g_3_4 | (g_1_2 & p_3_4);
endmodule

module b7_cla_8bit #(
    parameter width = 8
) (
    input wire [width:1] A,
    input wire [width:1] B,
    input wire cin,
    output wire [width:1] S,
    output wire cout,
    output wire p_1_8,
    output wire g_1_8
);
    wire c4;
    wire p_1_4, g_1_4;
    wire p_5_8, g_5_8;

    b7_cla_4bit #(.width(4)) u0 (
        .A(A[4:1]),
        .B(B[4:1]),
        .cin(cin),
        .S(S[4:1]),
        .cout(c4),
        .p_1_4(p_1_4),
        .g_1_4(g_1_4)
    );
    b7_cla_4bit #(.width(4)) u1 (
        .A(A[8:5]),
        .B(B[8:5]),
        .cin(c4),
        .S(S[8:5]),
        .cout(cout),
        .p_1_4(p_5_8),
        .g_1_4(g_5_8)
    );
    assign p_1_8 = p_1_4 & p_5_8;
    assign g_1_8 = g_5_8 | (g_1_4 & p_5_8);
endmodule

module b7_cla_16bit #(
    parameter width = 16
) (
    input wire [width:1] A,
    input wire [width:1] B,
    input wire cin,
    output wire [width:1] S,
    output wire cout,
    output wire p_1_16,
    output wire g_1_16
);
    wire c8;
    wire p_1_8, g_1_8;
    wire p_9_16, g_9_16;

    b7_cla_8bit #(.width(8)) u0 (
        .A(A[8:1]),
        .B(B[8:1]),
        .cin(cin),
        .S(S[8:1]),
        .cout(c8),
        .p_1_8(p_1_8),
        .g_1_8(g_1_8)
    );
    b7_cla_8bit #(.width(8)) u1 (
        .A(A[16:9]),
        .B(B[16:9]),
        .cin(c8),
        .S(S[16:9]),
        .cout(cout),
        .p_1_8(p_9_16),
        .g_1_8(g_9_16)
    );
    assign p_1_16 = p_1_8 & p_9_16;
    assign g_1_16 = g_9_16 | (g_1_8 & p_9_16);
endmodule

module b7_cla_group_merge_24 (
    input wire p_1_16,
    input wire g_1_16,
    input wire p_17_24,
    input wire g_17_24,
    output wire p_1_24,
    output wire g_1_24
);
    assign p_1_24 = p_1_16 & p_17_24;
    assign g_1_24 = g_17_24 | (g_1_16 & p_17_24);
endmodule

module b7_cla_ripple_finalize_24 #(
    parameter width = 24
) (
    input wire [width:1] p0,
    input wire [width:1] g0,
    input wire cin,
    output wire [width:1] S,
    output wire cout
);
    wire [width:0] carry;
    genvar k;

    assign carry[0] = cin;
    generate
        for (k = 1; k <= width; k = k + 1) begin: sum_path
            assign carry[k] = g0[k] | (p0[k] & carry[k-1]);
            assign S[k] = p0[k] ^ carry[k-1];
        end
    endgenerate
    assign cout = carry[width];
endmodule

module CLA_24bit #(
    parameter width = 24
) (
    input wire [width:1] A,
    input wire [width:1] B,
    input wire cin,
    output wire [width:1] S,
    output wire cout,
    output wire p_1_24,
    output wire g_1_24
);
    wire c16;
    wire p_1_16, g_1_16;
    wire p_17_24, g_17_24;
    wire [width:1] p0;
    wire [width:1] g0;

    assign p0 = A ^ B;
    assign g0 = A & B;

    b7_cla_16bit #(.width(16)) u0 (
        .A(A[16:1]),
        .B(B[16:1]),
        .cin(cin),
        .S(S[16:1]),
        .cout(c16),
        .p_1_16(p_1_16),
        .g_1_16(g_1_16)
    );
    b7_cla_8bit #(.width(8)) u1 (
        .A(A[24:17]),
        .B(B[24:17]),
        .cin(c16),
        .S(S[24:17]),
        .cout(cout),
        .p_1_8(p_17_24),
        .g_1_8(g_17_24)
    );
    b7_cla_group_merge_24 u2 (
        .p_1_16(p_1_16),
        .g_1_16(g_1_16),
        .p_17_24(p_17_24),
        .g_17_24(g_17_24),
        .p_1_24(p_1_24),
        .g_1_24(g_1_24)
    );
    b7_cla_ripple_finalize_24 #(.width(24)) u3 (
        .p0(p0),
        .g0(g0),
        .cin(cin),
        .S(S),
        .cout(cout)
    );
endmodule
