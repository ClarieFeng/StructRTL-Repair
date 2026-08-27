module fa_cell_high (
    input wire A,
    input wire B,
    input wire cin,
    output wire S,
    output wire cout
);
    assign S = A ^ B ^ cin;
    assign cout = (A & B) | ((A ^ B) & cin);
endmodule

module fa_lane4_high (
    input wire [4:1] A,
    input wire [4:1] B,
    input wire cin,
    output wire [4:1] S,
    output wire cout
);
    wire c1;
    wire c2;
    wire c3;

    fa_cell_high bit1 (.A(A[1]), .B(B[1]), .cin(cin), .S(S[1]), .cout(c1));
    fa_cell_high bit2 (.A(A[2]), .B(B[2]), .cin(c1), .S(S[2]), .cout(c2));
    fa_cell_high bit3 (.A(A[3]), .B(B[3]), .cin(c2), .S(S[3]), .cout(c3));
    fa_cell_high bit4 (.A(A[4]), .B(B[4]), .cin(c3), .S(S[4]), .cout(cout));
endmodule

module fa_lane8_high (
    input wire [8:1] A,
    input wire [8:1] B,
    input wire cin,
    output wire [8:1] S,
    output wire cout
);
    wire c4;

    fa_lane4_high lower_lane (
        .A(A[4:1]),
        .B(B[4:1]),
        .cin(cin),
        .S(S[4:1]),
        .cout(c4)
    );

    fa_lane4_high upper_lane (
        .A(A[8:5]),
        .B(B[8:5]),
        .cin(c4),
        .S(S[8:5]),
        .cout(cout)
    );
endmodule

module fa_lane16_high (
    input wire [16:1] A,
    input wire [16:1] B,
    input wire cin,
    output wire [16:1] S,
    output wire cout
);
    wire c8;

    fa_lane8_high lower_half (
        .A(A[8:1]),
        .B(B[8:1]),
        .cin(cin),
        .S(S[8:1]),
        .cout(c8)
    );

    fa_lane8_high upper_half (
        .A(A[16:9]),
        .B(B[16:9]),
        .cin(c8),
        .S(S[16:9]),
        .cout(cout)
    );
endmodule

module FA_21bit #(
    parameter width = 21
) (
    input wire [width:1] A,
    input wire [width:1] B,
    input wire cin,
    output wire [width:1] S,
    output wire cout
);

    wire c16;
    wire c20;

    wire [16:1] sum_low16;
    wire [4:1] sum_mid4;

    fa_lane16_high low_section (
        .A(A[16:1]),
        .B(B[16:1]),
        .cin(cin),
        .S(sum_low16),
        .cout(c16)
    );

    fa_lane4_high mid_section (
        .A(A[20:17]),
        .B(B[20:17]),
        .cin(c16),
        .S(sum_mid4),
        .cout(c20)
    );

    fa_cell_high high_bit (
        .A(A[21]),
        .B(B[21]),
        .cin(c20),
        .S(S[21]),
        .cout(cout)
    );

    assign S[16:1] = sum_low16;
    assign S[20:17] = sum_mid4;

endmodule
