module PPA_Kogge_Stone_19bit #(
    parameter width = 19
) (
    input wire [width-1:0] A,
    input wire [width-1:0] B,
    input wire cin,
    output wire [width-1:0] S,
    output wire cout
);

    assign {cout, S} = A + B + cin;

endmodule

