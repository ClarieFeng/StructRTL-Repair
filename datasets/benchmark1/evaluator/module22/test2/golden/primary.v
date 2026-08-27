module u22_medium_row_pair #(
    parameter DATA_W = 22
) (
    input wire [DATA_W-1:0] in_left,
    input wire [DATA_W-1:0] in_mid,
    input wire [DATA_W-1:0] in_right,
    output wire [DATA_W-1:0] stage_sum,
    output wire [DATA_W-1:0] stage_mix
);
    assign stage_sum = in_left + in_mid;
    assign stage_mix = in_left - in_mid + in_right;
endmodule

module u22_medium_out_mix #(
    parameter DATA_W = 22
) (
    input wire [DATA_W-1:0] stage_left,
    input wire [DATA_W-1:0] stage_mid,
    input wire [DATA_W-1:0] stage_right,
    input wire [DATA_W-1:0] stage_tail,
    output wire [DATA_W-1:0] out_sum,
    output wire [DATA_W-1:0] out_diff
);
    assign out_sum = stage_left + stage_mid + stage_right;
    assign out_diff = stage_mid - stage_right - stage_tail;
endmodule

module Wino_ATZA_22_23 #(
    parameter data_width = 22
) (
    input [data_width - 1:0] din0,
    input [data_width - 1:0] din1,
    input [data_width - 1:0] din2,
    input [data_width - 1:0] din3,
    input [data_width - 1:0] din4,
    input [data_width - 1:0] din5,
    input [data_width - 1:0] din6,
    input [data_width - 1:0] din7,
    input [data_width - 1:0] din8,
    input [data_width - 1:0] din9,
    input [data_width - 1:0] din10,
    input [data_width - 1:0] din11,
    output [data_width - 1:0] dout0,
    output [data_width - 1:0] dout1,
    output [data_width - 1:0] dout2,
    output [data_width - 1:0] dout3
);
    wire [data_width - 1:0] stage0_col0;
    wire [data_width - 1:0] stage0_col1;
    wire [data_width - 1:0] stage0_col2;
    wire [data_width - 1:0] stage0_col3;
    wire [data_width - 1:0] stage1_col0;
    wire [data_width - 1:0] stage1_col1;
    wire [data_width - 1:0] stage1_col2;
    wire [data_width - 1:0] stage1_col3;

    wire [data_width - 1:0] output_stage0;
    wire [data_width - 1:0] output_stage1;
    wire [data_width - 1:0] output_stage2;
    wire [data_width - 1:0] output_stage3;

    u22_medium_row_pair #(.DATA_W(data_width)) u_row0 (
        .in_left(din0),
        .in_mid(din4),
        .in_right(din8),
        .stage_sum(stage0_col0),
        .stage_mix(stage1_col0)
    );
    u22_medium_row_pair #(.DATA_W(data_width)) u_row1 (
        .in_left(din1),
        .in_mid(din5),
        .in_right(din9),
        .stage_sum(stage0_col1),
        .stage_mix(stage1_col1)
    );
    u22_medium_row_pair #(.DATA_W(data_width)) u_row2 (
        .in_left(din2),
        .in_mid(din6),
        .in_right(din10),
        .stage_sum(stage0_col2),
        .stage_mix(stage1_col2)
    );
    u22_medium_row_pair #(.DATA_W(data_width)) u_row3 (
        .in_left(din3),
        .in_mid(din7),
        .in_right(din11),
        .stage_sum(stage0_col3),
        .stage_mix(stage1_col3)
    );

    u22_medium_out_mix #(.DATA_W(data_width)) u_out0 (
        .stage_left(stage0_col0),
        .stage_mid(stage0_col1),
        .stage_right(stage0_col2),
        .stage_tail(stage0_col3),
        .out_sum(output_stage0),
        .out_diff(output_stage1)
    );
    u22_medium_out_mix #(.DATA_W(data_width)) u_out1 (
        .stage_left(stage1_col0),
        .stage_mid(stage1_col1),
        .stage_right(stage1_col2),
        .stage_tail(stage1_col3),
        .out_sum(output_stage2),
        .out_diff(output_stage3)
    );

    assign dout0 = output_stage0;
    assign dout1 = output_stage1;
    assign dout2 = output_stage2;
    assign dout3 = output_stage3;
endmodule
