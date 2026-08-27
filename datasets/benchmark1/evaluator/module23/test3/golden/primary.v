module u23_high_bt_column #(
    parameter data_width = 20
) (
    input wire [data_width - 1:0] top_in,
    input wire [data_width - 1:0] mid_in,
    input wire [data_width - 1:0] low_in,
    input wire [data_width - 1:0] tail_in,
    output wire [data_width - 1:0] bt_stage0,
    output wire [data_width - 1:0] bt_stage1,
    output wire [data_width - 1:0] bt_stage2,
    output wire [data_width - 1:0] bt_stage3
);
    wire [data_width - 1:0] top_alias;
    wire [data_width - 1:0] mid_alias;
    wire [data_width - 1:0] low_alias;
    wire [data_width - 1:0] tail_alias;
    wire [data_width - 1:0] stage_sub_top_low;
    wire [data_width - 1:0] stage_add_mid_low;
    wire [data_width - 1:0] stage_sub_low_mid;
    wire [data_width - 1:0] stage_sub_mid_tail;

    assign top_alias = top_in;
    assign mid_alias = mid_in;
    assign low_alias = low_in;
    assign tail_alias = tail_in;

    assign stage_sub_top_low = top_alias - low_alias;
    assign stage_add_mid_low = mid_alias + low_alias;
    assign stage_sub_low_mid = low_alias - mid_alias;
    assign stage_sub_mid_tail = mid_alias - tail_alias;

    assign bt_stage0 = stage_sub_top_low;
    assign bt_stage1 = stage_add_mid_low;
    assign bt_stage2 = stage_sub_low_mid;
    assign bt_stage3 = stage_sub_mid_tail;
endmodule

module u23_high_output_group #(
    parameter data_width = 20
) (
    input wire [data_width - 1:0] left_in,
    input wire [data_width - 1:0] center_in,
    input wire [data_width - 1:0] right_in,
    output wire [data_width - 1:0] dout0,
    output wire [data_width - 1:0] dout1,
    output wire [data_width - 1:0] dout2
);
    wire [data_width - 1:0] stage_sum;
    wire [data_width - 1:0] stage_diff_ba;
    wire [data_width - 1:0] stage_diff_ca;
    wire [data_width - 1:0] dout0_alias;
    wire [data_width - 1:0] dout1_alias;
    wire [data_width - 1:0] dout2_alias;

    assign stage_sum = left_in + center_in;
    assign stage_diff_ba = center_in - left_in;
    assign stage_diff_ca = right_in - left_in;

    assign dout0_alias = stage_sum;
    assign dout1_alias = stage_diff_ba;
    assign dout2_alias = stage_diff_ca;

    assign dout0 = dout0_alias;
    assign dout1 = dout1_alias;
    assign dout2 = dout2_alias;
endmodule

module u23_high_lane_alias #(
    parameter data_width = 20
) (
    input wire [data_width - 1:0] lane_in,
    output wire [data_width - 1:0] lane_out
);
    wire [data_width - 1:0] lane_stage;

    assign lane_stage = lane_in;
    assign lane_out = lane_stage;
endmodule

module Wino_BTDB_22_32 #(
    parameter data_width = 20
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
    input wire [data_width - 1:0] din9,
    input wire [data_width - 1:0] din10,
    input wire [data_width - 1:0] din11,
    output wire [data_width - 1:0] dout0,
    output wire [data_width - 1:0] dout1,
    output wire [data_width - 1:0] dout2,
    output wire [data_width - 1:0] dout3,
    output wire [data_width - 1:0] dout4,
    output wire [data_width - 1:0] dout5,
    output wire [data_width - 1:0] dout6,
    output wire [data_width - 1:0] dout7,
    output wire [data_width - 1:0] dout8,
    output wire [data_width - 1:0] dout9,
    output wire [data_width - 1:0] dout10,
    output wire [data_width - 1:0] dout11
);
    wire [data_width - 1:0] bt_col0_stage0;
    wire [data_width - 1:0] bt_col1_stage0;
    wire [data_width - 1:0] bt_col2_stage0;
    wire [data_width - 1:0] bt_col0_stage1;
    wire [data_width - 1:0] bt_col1_stage1;
    wire [data_width - 1:0] bt_col2_stage1;
    wire [data_width - 1:0] bt_col0_stage2;
    wire [data_width - 1:0] bt_col1_stage2;
    wire [data_width - 1:0] bt_col2_stage2;
    wire [data_width - 1:0] bt_col0_stage3;
    wire [data_width - 1:0] bt_col1_stage3;
    wire [data_width - 1:0] bt_col2_stage3;
    wire [data_width - 1:0] raw_dout0;
    wire [data_width - 1:0] raw_dout1;
    wire [data_width - 1:0] raw_dout2;
    wire [data_width - 1:0] raw_dout3;
    wire [data_width - 1:0] raw_dout4;
    wire [data_width - 1:0] raw_dout5;
    wire [data_width - 1:0] raw_dout6;
    wire [data_width - 1:0] raw_dout7;
    wire [data_width - 1:0] raw_dout8;
    wire [data_width - 1:0] raw_dout9;
    wire [data_width - 1:0] raw_dout10;
    wire [data_width - 1:0] raw_dout11;

    u23_high_bt_column #(.data_width(data_width)) bt_col0 (
        .top_in(din0),
        .mid_in(din3),
        .low_in(din6),
        .tail_in(din9),
        .bt_stage0(bt_col0_stage0),
        .bt_stage1(bt_col0_stage1),
        .bt_stage2(bt_col0_stage2),
        .bt_stage3(bt_col0_stage3)
    );

    u23_high_bt_column #(.data_width(data_width)) bt_col1 (
        .top_in(din1),
        .mid_in(din4),
        .low_in(din7),
        .tail_in(din10),
        .bt_stage0(bt_col1_stage0),
        .bt_stage1(bt_col1_stage1),
        .bt_stage2(bt_col1_stage2),
        .bt_stage3(bt_col1_stage3)
    );

    u23_high_bt_column #(.data_width(data_width)) bt_col2 (
        .top_in(din2),
        .mid_in(din5),
        .low_in(din8),
        .tail_in(din11),
        .bt_stage0(bt_col2_stage0),
        .bt_stage1(bt_col2_stage1),
        .bt_stage2(bt_col2_stage2),
        .bt_stage3(bt_col2_stage3)
    );

    u23_high_output_group #(.data_width(data_width)) out_group0 (
        .left_in(bt_col0_stage0),
        .center_in(bt_col1_stage0),
        .right_in(bt_col2_stage0),
        .dout0(raw_dout0),
        .dout1(raw_dout1),
        .dout2(raw_dout2)
    );

    u23_high_output_group #(.data_width(data_width)) out_group1 (
        .left_in(bt_col0_stage1),
        .center_in(bt_col1_stage1),
        .right_in(bt_col2_stage1),
        .dout0(raw_dout3),
        .dout1(raw_dout4),
        .dout2(raw_dout5)
    );

    u23_high_output_group #(.data_width(data_width)) out_group2 (
        .left_in(bt_col0_stage2),
        .center_in(bt_col1_stage2),
        .right_in(bt_col2_stage2),
        .dout0(raw_dout6),
        .dout1(raw_dout7),
        .dout2(raw_dout8)
    );

    u23_high_output_group #(.data_width(data_width)) out_group3 (
        .left_in(bt_col0_stage3),
        .center_in(bt_col1_stage3),
        .right_in(bt_col2_stage3),
        .dout0(raw_dout9),
        .dout1(raw_dout10),
        .dout2(raw_dout11)
    );

    u23_high_lane_alias #(.data_width(data_width)) lane0 (.lane_in(raw_dout0), .lane_out(dout0));
    u23_high_lane_alias #(.data_width(data_width)) lane1 (.lane_in(raw_dout1), .lane_out(dout1));
    u23_high_lane_alias #(.data_width(data_width)) lane2 (.lane_in(raw_dout2), .lane_out(dout2));
    u23_high_lane_alias #(.data_width(data_width)) lane3 (.lane_in(raw_dout3), .lane_out(dout3));
    u23_high_lane_alias #(.data_width(data_width)) lane4 (.lane_in(raw_dout4), .lane_out(dout4));
    u23_high_lane_alias #(.data_width(data_width)) lane5 (.lane_in(raw_dout5), .lane_out(dout5));
    u23_high_lane_alias #(.data_width(data_width)) lane6 (.lane_in(raw_dout6), .lane_out(dout6));
    u23_high_lane_alias #(.data_width(data_width)) lane7 (.lane_in(raw_dout7), .lane_out(dout7));
    u23_high_lane_alias #(.data_width(data_width)) lane8 (.lane_in(raw_dout8), .lane_out(dout8));
    u23_high_lane_alias #(.data_width(data_width)) lane9 (.lane_in(raw_dout9), .lane_out(dout9));
    u23_high_lane_alias #(.data_width(data_width)) lane10 (.lane_in(raw_dout10), .lane_out(dout10));
    u23_high_lane_alias #(.data_width(data_width)) lane11 (.lane_in(raw_dout11), .lane_out(dout11));
endmodule
