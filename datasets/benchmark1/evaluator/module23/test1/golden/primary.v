module Wino_BTDB_22_21 #(
    parameter data_width = 23
) (
    input wire [data_width - 1:0] din0,
    input wire [data_width - 1:0] din1,
    input wire [data_width - 1:0] din2,
    input wire [data_width - 1:0] din3,
    input wire [data_width - 1:0] din4,
    input wire [data_width - 1:0] din5,
    output wire [data_width - 1:0] dout0,
    output wire [data_width - 1:0] dout1,
    output wire [data_width - 1:0] dout2,
    output wire [data_width - 1:0] dout3,
    output wire [data_width - 1:0] dout4,
    output wire [data_width - 1:0] dout5
);
    wire [data_width - 1:0] bt_row0_sum;
    wire [data_width - 1:0] bt_row1_sum;
    wire [data_width - 1:0] bt_row0_diff0;
    wire [data_width - 1:0] bt_row1_diff0;
    wire [data_width - 1:0] bt_row0_diff1;
    wire [data_width - 1:0] bt_row1_diff1;

    assign bt_row0_sum = din0 + din2;
    assign bt_row1_sum = din1 + din3;
    assign bt_row0_diff0 = din2 - din0;
    assign bt_row1_diff0 = din3 - din1;
    assign bt_row0_diff1 = din4 - din0;
    assign bt_row1_diff1 = din5 - din1;

    assign dout0 = bt_row0_sum;
    assign dout1 = bt_row1_sum;
    assign dout2 = bt_row0_diff0;
    assign dout3 = bt_row1_diff0;
    assign dout4 = bt_row0_diff1;
    assign dout5 = bt_row1_diff1;
endmodule
