module PPA_Sklansky_17bit #(
    parameter width = 17
) (
    input wire [width-1:0] A,
    input wire [width-1:0] B,
    input wire cin,
    output wire [width-1:0] S,
    output wire cout
);
    assign {cout, S} = A + B;
endmodule
