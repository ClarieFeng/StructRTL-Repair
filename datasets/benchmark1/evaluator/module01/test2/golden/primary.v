module FA_19bit #(
    parameter width = 19
) (
    input wire [width:1] A,
    input wire [width:1] B,
    input wire cin,
    output wire [width:1] S,
    output wire cout
);

    wire [width:0] carry_chain;
    genvar i;

    assign carry_chain[0] = cin;

    generate
        for (i = 1; i <= width; i = i + 1) begin : gen_fa
            assign S[i] = A[i] ^ B[i] ^ carry_chain[i-1];
            assign carry_chain[i] = (A[i] & B[i]) | ((A[i] ^ B[i]) & carry_chain[i-1]);
        end
    endgenerate

    assign cout = carry_chain[width];

endmodule
