module carry_skip_block4_medium #(
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

module C_Skip_A_20bit #(
    parameter width = 20
) (
    input wire [width-1:0] A,
    input wire [width-1:0] B,
    input wire cin,
    output wire [width-1:0] S,
    output wire cout
);

    wire [5:0] carry_chain;
    wire [4:0] block_propagate;

    assign carry_chain[0] = cin;

    carry_skip_block4_medium #(.WIDTH(4)) block0 (
        .A(A[3:0]),
        .B(B[3:0]),
        .cin(carry_chain[0]),
        .S(S[3:0]),
        .cout(carry_chain[1]),
        .block_p(block_propagate[0])
    );

    carry_skip_block4_medium #(.WIDTH(4)) block1 (
        .A(A[7:4]),
        .B(B[7:4]),
        .cin(carry_chain[1]),
        .S(S[7:4]),
        .cout(carry_chain[2]),
        .block_p(block_propagate[1])
    );

    carry_skip_block4_medium #(.WIDTH(4)) block2 (
        .A(A[11:8]),
        .B(B[11:8]),
        .cin(carry_chain[2]),
        .S(S[11:8]),
        .cout(carry_chain[3]),
        .block_p(block_propagate[2])
    );

    carry_skip_block4_medium #(.WIDTH(4)) block3 (
        .A(A[15:12]),
        .B(B[15:12]),
        .cin(carry_chain[3]),
        .S(S[15:12]),
        .cout(carry_chain[4]),
        .block_p(block_propagate[3])
    );

    carry_skip_block4_medium #(.WIDTH(4)) block4 (
        .A(A[19:16]),
        .B(B[19:16]),
        .cin(carry_chain[4]),
        .S(S[19:16]),
        .cout(carry_chain[5]),
        .block_p(block_propagate[4])
    );

    assign cout = carry_chain[5];

endmodule
