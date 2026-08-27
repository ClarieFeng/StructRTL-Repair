module PPA_Sklansky_19bit #(
    parameter width = 19
) (
    input wire [width-1:0] A,
    input wire [width-1:0] B,
    input wire cin,
    output wire [width-1:0] S,
    output wire cout
);

    wire [width:0] c_temp;
    wire [width-1:0] p;
    wire [width-1:0] g;
    genvar i;

    assign c_temp[0] = cin;
    assign p = A ^ B;
    assign g = A & B;

    generate
        for (i = 1; i <= width; i = i + 1) begin : gen_ripple
            assign c_temp[i] = g[i-1] | (p[i-1] & c_temp[i-1]);
        end
    endgenerate

    assign S = c_temp[width-1:0] ^ p;
    assign cout = c_temp[width];
endmodule
