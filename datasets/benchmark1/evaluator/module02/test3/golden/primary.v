module prefix_bitcell_high (
    input wire A,
    input wire B,
    input wire cin,
    output wire S,
    output wire cout
);
    assign S = A ^ B ^ cin;
    assign cout = (A & B) | ((A ^ B) & cin);
endmodule

module prefix_lane2_high (
    input wire [2:1] A,
    input wire [2:1] B,
    input wire cin,
    output wire [2:1] S,
    output wire cout
);
    wire c1;

    prefix_bitcell_high bit1 (
        .A(A[1]),
        .B(B[1]),
        .cin(cin),
        .S(S[1]),
        .cout(c1)
    );

    prefix_bitcell_high bit2 (
        .A(A[2]),
        .B(B[2]),
        .cin(c1),
        .S(S[2]),
        .cout(cout)
    );
endmodule

module prefix_lane4_high (
    input wire [4:1] A,
    input wire [4:1] B,
    input wire cin,
    output wire [4:1] S,
    output wire cout
);
    wire c2;

    prefix_lane2_high lower_lane (
        .A(A[2:1]),
        .B(B[2:1]),
        .cin(cin),
        .S(S[2:1]),
        .cout(c2)
    );

    prefix_lane2_high upper_lane (
        .A(A[4:3]),
        .B(B[4:3]),
        .cin(c2),
        .S(S[4:3]),
        .cout(cout)
    );
endmodule

module prefix_lane8_high (
    input wire [8:1] A,
    input wire [8:1] B,
    input wire cin,
    output wire [8:1] S,
    output wire cout
);
    wire c4;

    prefix_lane4_high lower_half (
        .A(A[4:1]),
        .B(B[4:1]),
        .cin(cin),
        .S(S[4:1]),
        .cout(c4)
    );

    prefix_lane4_high upper_half (
        .A(A[8:5]),
        .B(B[8:5]),
        .cin(c4),
        .S(S[8:5]),
        .cout(cout)
    );
endmodule

module prefix_lane16_high (
    input wire [16:1] A,
    input wire [16:1] B,
    input wire cin,
    output wire [16:1] S,
    output wire cout
);
    wire c8;

    prefix_lane8_high lower_half (
        .A(A[8:1]),
        .B(B[8:1]),
        .cin(cin),
        .S(S[8:1]),
        .cout(c8)
    );

    prefix_lane8_high upper_half (
        .A(A[16:9]),
        .B(B[16:9]),
        .cin(c8),
        .S(S[16:9]),
        .cout(cout)
    );
endmodule

module PPA_Sklansky_22bit #(
    parameter width = 22
) (
    input wire [width-1:0] A,
    input wire [width-1:0] B,
    input wire cin,
    output wire [width-1:0] S,
    output wire cout
);
    wire c16;
    wire c20;
    wire [15:0] sum_low16;
    wire [3:0] sum_mid4;
    wire [1:0] sum_high2;

    prefix_lane16_high low_section (
        .A(A[15:0]),
        .B(B[15:0]),
        .cin(cin),
        .S(sum_low16),
        .cout(c16)
    );

    prefix_lane4_high mid_section (
        .A(A[19:16]),
        .B(B[19:16]),
        .cin(c16),
        .S(sum_mid4),
        .cout(c20)
    );

    prefix_lane2_high high_section (
        .A(A[21:20]),
        .B(B[21:20]),
        .cin(c20),
        .S(sum_high2),
        .cout(cout)
    );

    assign S[15:0] = sum_low16;
    assign S[19:16] = sum_mid4;
    assign S[21:20] = sum_high2;
endmodule
