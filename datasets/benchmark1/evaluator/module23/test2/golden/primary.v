module u23_medium_bt_column #(
    parameter data_width = 18
) (
    input wire [data_width - 1:0] top_in,
    input wire [data_width - 1:0] mid_in,
    input wire [data_width - 1:0] bot_in,
    output wire [data_width - 1:0] bt_sum,
    output wire [data_width - 1:0] bt_mid_minus_top,
    output wire [data_width - 1:0] bt_bot_minus_top
);
    wire [data_width - 1:0] mid_alias;
    wire [data_width - 1:0] top_alias;
    wire [data_width - 1:0] bot_alias;

    assign top_alias = top_in;
    assign mid_alias = mid_in;
    assign bot_alias = bot_in;

    assign bt_sum = top_alias + mid_alias;
    assign bt_mid_minus_top = mid_alias - top_alias;
    assign bt_bot_minus_top = bot_alias - top_alias;
endmodule

module u23_medium_output_group #(
    parameter data_width = 18
) (
    input wire [data_width - 1:0] left_in,
    input wire [data_width - 1:0] center_in,
    input wire [data_width - 1:0] right_in,
    output wire [data_width - 1:0] dout_a,
    output wire [data_width - 1:0] dout_b,
    output wire [data_width - 1:0] dout_c
);
    wire [data_width - 1:0] sum_stage;
    wire [data_width - 1:0] diff_stage0;
    wire [data_width - 1:0] diff_stage1;

    assign sum_stage = left_in + center_in;
    assign diff_stage0 = center_in - left_in;
    assign diff_stage1 = right_in - left_in;

    assign dout_a = sum_stage;
    assign dout_b = diff_stage0;
    assign dout_c = diff_stage1;
endmodule

module Wino_BTDB_22_22 #(
    parameter data_width = 18
) (
    input wire [data_width - 1:0] din0,
    input wire [data_width - 1:0] din1,
    input wire [data_width - 1:0] din2,
    input wire [data_width - 1:0] din3,
    input wire [data_width - 1:0] din4,
    input wire [data_width - 1:0] din5,
    input wire [data_width - 1:0] din6,
    input wire [data_width - 1:0] din7,
    input wire [data_width - 1:0] din8,
    output wire [data_width - 1:0] dout0,
    output wire [data_width - 1:0] dout1,
    output wire [data_width - 1:0] dout2,
    output wire [data_width - 1:0] dout3,
    output wire [data_width - 1:0] dout4,
    output wire [data_width - 1:0] dout5,
    output wire [data_width - 1:0] dout6,
    output wire [data_width - 1:0] dout7,
    output wire [data_width - 1:0] dout8
);
    wire [data_width - 1:0] bt_col0_sum;
    wire [data_width - 1:0] bt_col1_sum;
    wire [data_width - 1:0] bt_col2_sum;
    wire [data_width - 1:0] bt_col0_diff0;
    wire [data_width - 1:0] bt_col1_diff0;
    wire [data_width - 1:0] bt_col2_diff0;
    wire [data_width - 1:0] bt_col0_diff1;
    wire [data_width - 1:0] bt_col1_diff1;
    wire [data_width - 1:0] bt_col2_diff1;

    u23_medium_bt_column #(.data_width(data_width)) bt_col0 (
        .top_in(din0),
        .mid_in(din3),
        .bot_in(din6),
        .bt_sum(bt_col0_sum),
        .bt_mid_minus_top(bt_col0_diff0),
        .bt_bot_minus_top(bt_col0_diff1)
    );

    u23_medium_bt_column #(.data_width(data_width)) bt_col1 (
        .top_in(din1),
        .mid_in(din4),
        .bot_in(din7),
        .bt_sum(bt_col1_sum),
        .bt_mid_minus_top(bt_col1_diff0),
        .bt_bot_minus_top(bt_col1_diff1)
    );

    u23_medium_bt_column #(.data_width(data_width)) bt_col2 (
        .top_in(din2),
        .mid_in(din5),
        .bot_in(din8),
        .bt_sum(bt_col2_sum),
        .bt_mid_minus_top(bt_col2_diff0),
        .bt_bot_minus_top(bt_col2_diff1)
    );

    u23_medium_output_group #(.data_width(data_width)) out_group0 (
        .left_in(bt_col0_sum),
        .center_in(bt_col1_sum),
        .right_in(bt_col2_sum),
        .dout_a(dout0),
        .dout_b(dout1),
        .dout_c(dout2)
    );

    u23_medium_output_group #(.data_width(data_width)) out_group1 (
        .left_in(bt_col0_diff0),
        .center_in(bt_col1_diff0),
        .right_in(bt_col2_diff0),
        .dout_a(dout3),
        .dout_b(dout4),
        .dout_c(dout5)
    );

    u23_medium_output_group #(.data_width(data_width)) out_group2 (
        .left_in(bt_col0_diff1),
        .center_in(bt_col1_diff1),
        .right_in(bt_col2_diff1),
        .dout_a(dout6),
        .dout_b(dout7),
        .dout_c(dout8)
    );
endmodule
