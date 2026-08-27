module FA_17bit #(
    parameter width = 17
) (
    input wire [width:1] A,
    input wire [width:1] B,
    input wire cin,
    output wire [width:1] S,
    output wire cout
);
    assign {cout, S} = A + B + cin;
endmodule
