module C_Sel_A_20bit #(
    parameter width = 20
) (
    input  wire [width:1] A,
    input  wire [width:1] B,
    input  wire           cin,
    output wire [width:1] S,
    output wire           cout
);

    wire [16:1] sum_low;
    wire        carry_low;

    wire [4:1]  sum_high_c0;
    wire [4:1]  sum_high_c1;
    wire        carry_high_c0;
    wire        carry_high_c1;

    assign {carry_low, sum_low} = A[16:1] + B[16:1] + cin;

    assign {carry_high_c0, sum_high_c0} = A[20:17] + B[20:17] + 1'b0;
    assign {carry_high_c1, sum_high_c1} = A[20:17] + B[20:17] + 1'b1;

    assign S[16:1]  = sum_low;
    assign S[20:17] = carry_low ? sum_high_c1 : sum_high_c0;
    assign cout     = carry_low ? carry_high_c1 : carry_high_c0;

endmodule
