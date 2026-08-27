module C_Skip_A_18bit #(
    parameter width = 18
) (
    input wire [width-1:0] A,
    input wire [width-1:0] B,
    input wire cin,
    output wire [width-1:0] S,
    output wire cout
);

    wire [3:0] p_block0;
    wire [3:0] p_block1;
    wire [3:0] p_block2;
    wire [3:0] p_block3;
    wire [1:0] p_block4;

    wire c4_ripple;
    wire c8_ripple;
    wire c12_ripple;
    wire c16_ripple;
    wire c18_ripple;

    wire c4;
    wire c8;
    wire c12;
    wire c16;

    assign p_block0 = A[3:0] ^ B[3:0];
    assign {c4_ripple, S[3:0]} = A[3:0] + B[3:0] + cin;
    assign c4 = (&p_block0) ? cin : c4_ripple;

    assign p_block1 = A[7:4] ^ B[7:4];
    assign {c8_ripple, S[7:4]} = A[7:4] + B[7:4] + c4;
    assign c8 = (&p_block1) ? c4 : c8_ripple;

    assign p_block2 = A[11:8] ^ B[11:8];
    assign {c12_ripple, S[11:8]} = A[11:8] + B[11:8] + c8;
    assign c12 = (&p_block2) ? c8 : c12_ripple;

    assign p_block3 = A[15:12] ^ B[15:12];
    assign {c16_ripple, S[15:12]} = A[15:12] + B[15:12] + c12;
    assign c16 = (&p_block3) ? c12 : c16_ripple;

    assign p_block4 = A[17:16] ^ B[17:16];
    assign {c18_ripple, S[17:16]} = A[17:16] + B[17:16] + c16;
    assign cout = (&p_block4) ? c16 : c18_ripple;

endmodule
