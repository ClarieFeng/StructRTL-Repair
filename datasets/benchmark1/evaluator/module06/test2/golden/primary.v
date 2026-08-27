module C_Sel_A_19bit #(
    parameter width = 19
) (
    input  wire [width:1] A,
    input  wire [width:1] B,
    input  wire           cin,
    output wire [width:1] S,
    output wire           cout
);

    wire [16:1] sum_low;
    wire        carry_low;

    wire [3:1]  sum_high_c0;
    wire [3:1]  sum_high_c1;
    wire        carry_high_c0;
    wire        carry_high_c1;

    wire [3:1]  sum_high;
    wire        carry_high;

    assign {carry_low, sum_low} = A[16:1] + B[16:1] + cin;

    assign {carry_high_c0, sum_high_c0} = A[19:17] + B[19:17] + 1'b0;
    assign {carry_high_c1, sum_high_c1} = A[19:17] + B[19:17] + 1'b1;

    assign sum_high   = carry_low ? sum_high_c1   : sum_high_c0;
    assign carry_high = carry_low ? carry_high_c1 : carry_high_c0;

    assign S[16:1]  = sum_low;
    assign S[19:17] = sum_high;
    assign cout     = carry_high;

endmodule
