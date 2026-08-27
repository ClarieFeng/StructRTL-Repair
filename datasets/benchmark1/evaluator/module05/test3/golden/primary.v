module carry_skip_block_core_high #(
    parameter integer WIDTH = 4
) (
    input wire [WIDTH-1:0] A,
    input wire [WIDTH-1:0] B,
    input wire cin,
    output wire [WIDTH-1:0] S,
    output wire cout,
    output wire block_p
);
    wire [WIDTH-1:0] propagate_bits;
    wire ripple_cout;

    assign propagate_bits = A ^ B;
    assign block_p = &propagate_bits;
    assign {ripple_cout, S} = A + B + cin;
    assign cout = block_p ? cin : ripple_cout;
endmodule

module carry_skip_block4_high #(
    parameter integer WIDTH = 4
) (
    input wire [WIDTH-1:0] A,
    input wire [WIDTH-1:0] B,
    input wire cin,
    output wire [WIDTH-1:0] S,
    output wire cout,
    output wire block_p
);
    carry_skip_block_core_high #(.WIDTH(WIDTH)) block_impl (
        .A(A),
        .B(B),
        .cin(cin),
        .S(S),
        .cout(cout),
        .block_p(block_p)
    );
endmodule

module carry_skip_block3_high #(
    parameter integer WIDTH = 3
) (
    input wire [WIDTH-1:0] A,
    input wire [WIDTH-1:0] B,
    input wire cin,
    output wire [WIDTH-1:0] S,
    output wire cout,
    output wire block_p
);
    carry_skip_block_core_high #(.WIDTH(WIDTH)) block_impl (
        .A(A),
        .B(B),
        .cin(cin),
        .S(S),
        .cout(cout),
        .block_p(block_p)
    );
endmodule

module carry_skip_block8_high #(
    parameter integer WIDTH = 8
) (
    input wire [WIDTH-1:0] A,
    input wire [WIDTH-1:0] B,
    input wire cin,
    output wire [WIDTH-1:0] S,
    output wire cout,
    output wire block_p
);
    wire carry_mid;
    wire block_p_low;
    wire block_p_high;

    carry_skip_block4_high lower_block (
        .A(A[3:0]),
        .B(B[3:0]),
        .cin(cin),
        .S(S[3:0]),
        .cout(carry_mid),
        .block_p(block_p_low)
    );

    carry_skip_block4_high upper_block (
        .A(A[7:4]),
        .B(B[7:4]),
        .cin(carry_mid),
        .S(S[7:4]),
        .cout(cout),
        .block_p(block_p_high)
    );

    assign block_p = block_p_low & block_p_high;
endmodule

module carry_skip_block16_high #(
    parameter integer WIDTH = 16
) (
    input wire [WIDTH-1:0] A,
    input wire [WIDTH-1:0] B,
    input wire cin,
    output wire [WIDTH-1:0] S,
    output wire cout,
    output wire block_p
);
    wire carry_mid;
    wire block_p_low;
    wire block_p_high;

    carry_skip_block8_high lower_half (
        .A(A[7:0]),
        .B(B[7:0]),
        .cin(cin),
        .S(S[7:0]),
        .cout(carry_mid),
        .block_p(block_p_low)
    );

    carry_skip_block8_high upper_half (
        .A(A[15:8]),
        .B(B[15:8]),
        .cin(carry_mid),
        .S(S[15:8]),
        .cout(cout),
        .block_p(block_p_high)
    );

    assign block_p = block_p_low & block_p_high;
endmodule

module C_Skip_A_23bit #(
    parameter width = 23
) (
    input wire [width-1:0] A,
    input wire [width-1:0] B,
    input wire cin,
    output wire [width-1:0] S,
    output wire cout
);

    wire c16;
    wire c20;

    wire block_p16;
    wire block_p4;
    wire block_p3;

    wire [15:0] sum_low16;
    wire [3:0] sum_mid4;
    wire [2:0] sum_high3;

    carry_skip_block16_high block16 (
        .A(A[15:0]),
        .B(B[15:0]),
        .cin(cin),
        .S(sum_low16),
        .cout(c16),
        .block_p(block_p16)
    );

    carry_skip_block4_high block4 (
        .A(A[19:16]),
        .B(B[19:16]),
        .cin(c16),
        .S(sum_mid4),
        .cout(c20),
        .block_p(block_p4)
    );

    carry_skip_block3_high block3 (
        .A(A[22:20]),
        .B(B[22:20]),
        .cin(c20),
        .S(sum_high3),
        .cout(cout),
        .block_p(block_p3)
    );

    assign S[15:0] = sum_low16;
    assign S[19:16] = sum_mid4;
    assign S[22:20] = sum_high3;

endmodule
