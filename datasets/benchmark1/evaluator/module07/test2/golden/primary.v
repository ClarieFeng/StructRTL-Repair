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

module CLA_22bit #(
    parameter width = 22
) (
    input wire [width:1] A,
    input wire [width:1] B,
    input wire cin,
    output wire [width:1] S,
    output wire cout,
    output wire p_1_22,
    output wire g_1_22
);
    wire c16;
    wire c20;
    wire p_1_16, g_1_16;
    wire p_17_20, g_17_20;
    wire p_21_22, g_21_22;

    b7_cla_16bit #(.width(16)) u0 (
        .A(A[16:1]),
        .B(B[16:1]),
        .cin(cin),
        .S(S[16:1]),
        .cout(c16),
        .p_1_16(p_1_16),
        .g_1_16(g_1_16)
    );
    b7_cla_4bit #(.width(4)) u1 (
        .A(A[20:17]),
        .B(B[20:17]),
        .cin(c16),
        .S(S[20:17]),
        .cout(c20),
        .p_1_4(p_17_20),
        .g_1_4(g_17_20)
    );
    b7_cla_2bit #(.width(2)) u2 (
        .A(A[22:21]),
        .B(B[22:21]),
        .cin(c20),
        .S(S[22:21]),
        .cout(cout),
        .p_1_2(p_21_22),
        .g_1_2(g_21_22)
    );
    assign p_1_22 = p_1_16 & p_17_20 & p_21_22;
    assign g_1_22 = g_21_22 | (g_17_20 & p_21_22) | (g_1_16 & p_17_20 & p_21_22);
endmodule

