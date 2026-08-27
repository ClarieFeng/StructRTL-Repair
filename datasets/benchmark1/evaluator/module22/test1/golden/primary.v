module Wino_ATZA_22_21 #(
    parameter data_width = 20
) (
    input [data_width - 1:0] din0,
    input [data_width - 1:0] din1,
    input [data_width - 1:0] din2,
    input [data_width - 1:0] din3,
    input [data_width - 1:0] din4,
    input [data_width - 1:0] din5,
    output [data_width - 1:0] dout0,
    output [data_width - 1:0] dout1,
    output [data_width - 1:0] dout2,
    output [data_width - 1:0] dout3
);
    wire [data_width - 1:0] stage0_col0;
    wire [data_width - 1:0] stage0_col1;
    wire [data_width - 1:0] stage1_col0;
    wire [data_width - 1:0] stage1_col1;

    assign stage0_col0 = din0 + din2;
    assign stage0_col1 = din1 + din3;
    assign stage1_col0 = din0 - din2 + din4;
    assign stage1_col1 = din1 - din3 + din5;

    assign dout0 = stage0_col0;
    assign dout1 = stage0_col1;
    assign dout2 = stage1_col0;
    assign dout3 = stage1_col1;
endmodule
