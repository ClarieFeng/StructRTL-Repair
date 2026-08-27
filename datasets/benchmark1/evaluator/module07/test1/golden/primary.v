module CLA_17bit #(
    parameter width = 17
) (
    input wire [width:1] A,
    input wire [width:1] B,
    input wire cin,
    output wire [width:1] S,
    output wire cout,
    output wire p_1_17,
    output wire g_1_17
);
    wire [width:0] sum0;
    assign sum0 = {1'b0, A} + {1'b0, B};
    assign {cout, S} = A + B + cin;
    assign p_1_17 = & (A ^ B);
    assign g_1_17 = sum0[width];
endmodule

