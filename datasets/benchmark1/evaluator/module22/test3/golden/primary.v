module u22_high_input_row #(
    parameter DATA_W = 24
) (
    input wire [DATA_W-1:0] in0,
    input wire [DATA_W-1:0] in1,
    input wire [DATA_W-1:0] in2,
    input wire [DATA_W-1:0] in3,
    output wire [DATA_W-1:0] row_sum,
    output wire [DATA_W-1:0] row_alt,
    output wire [DATA_W-1:0] row_sum_alias,
    output wire [DATA_W-1:0] row_alt_alias
);
    assign row_sum = in0 + in1 + in2 + in3;
    assign row_alt = in0 - in1 + in2 - in3;
    assign row_sum_alias = row_sum;
    assign row_alt_alias = row_alt;
endmodule

module u22_high_out_mix #(
    parameter DATA_W = 24
) (
    input wire [DATA_W-1:0] in0,
    input wire [DATA_W-1:0] in1,
    input wire [DATA_W-1:0] in2,
    input wire [DATA_W-1:0] in3,
    output wire [DATA_W-1:0] out_sum,
    output wire [DATA_W-1:0] out_diff,
    output wire [DATA_W-1:0] out_sum_alias,
    output wire [DATA_W-1:0] out_diff_alias
);
    assign out_sum = in0 + in1 + in2;
    assign out_diff = in1 - in2 - in3;
    assign out_sum_alias = out_sum;
    assign out_diff_alias = out_diff;
endmodule

module u22_high_passthrough #(
    parameter DATA_W = 24
) (
    input wire [DATA_W-1:0] in_data,
    output wire [DATA_W-1:0] out_data,
    output wire [DATA_W-1:0] out_alias
);
    assign out_data = in_data;
    assign out_alias = out_data;
endmodule

module Wino_ATZA_22_33 #(
    parameter data_width = 24
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
    input [data_width - 1:0] din12,
    input [data_width - 1:0] din13,
    input [data_width - 1:0] din14,
    input [data_width - 1:0] din15,
    output [data_width - 1:0] dout0,
    output [data_width - 1:0] dout1,
    output [data_width - 1:0] dout2,
    output [data_width - 1:0] dout3
);
    wire [data_width - 1:0] stage0_row0;
    wire [data_width - 1:0] stage0_row1;
    wire [data_width - 1:0] stage0_row2;
    wire [data_width - 1:0] stage0_row3;
    wire [data_width - 1:0] stage1_row0;
    wire [data_width - 1:0] stage1_row1;
    wire [data_width - 1:0] stage1_row2;
    wire [data_width - 1:0] stage1_row3;

    wire [data_width - 1:0] stage0_row0_alias;
    wire [data_width - 1:0] stage0_row1_alias;
    wire [data_width - 1:0] stage0_row2_alias;
    wire [data_width - 1:0] stage0_row3_alias;
    wire [data_width - 1:0] stage1_row0_alias;
    wire [data_width - 1:0] stage1_row1_alias;
    wire [data_width - 1:0] stage1_row2_alias;
    wire [data_width - 1:0] stage1_row3_alias;

    wire [data_width - 1:0] stage2_sum0;
    wire [data_width - 1:0] stage2_diff0;
    wire [data_width - 1:0] stage2_sum1;
    wire [data_width - 1:0] stage2_diff1;
    wire [data_width - 1:0] stage2_sum0_alias;
    wire [data_width - 1:0] stage2_diff0_alias;
    wire [data_width - 1:0] stage2_sum1_alias;
    wire [data_width - 1:0] stage2_diff1_alias;

    wire [data_width - 1:0] dout0_stage;
    wire [data_width - 1:0] dout1_stage;
    wire [data_width - 1:0] dout2_stage;
    wire [data_width - 1:0] dout3_stage;
    wire [data_width - 1:0] dout0_alias;
    wire [data_width - 1:0] dout1_alias;
    wire [data_width - 1:0] dout2_alias;
    wire [data_width - 1:0] dout3_alias;

    u22_high_input_row #(.DATA_W(data_width)) u_stage0_row0 (
        .in0(din0), .in1(din4), .in2(din8), .in3(din12),
        .row_sum(stage0_row0), .row_alt(stage1_row0),
        .row_sum_alias(stage0_row0_alias), .row_alt_alias(stage1_row0_alias)
    );
    u22_high_input_row #(.DATA_W(data_width)) u_stage0_row1 (
        .in0(din1), .in1(din5), .in2(din9), .in3(din13),
        .row_sum(stage0_row1), .row_alt(stage1_row1),
        .row_sum_alias(stage0_row1_alias), .row_alt_alias(stage1_row1_alias)
    );
    u22_high_input_row #(.DATA_W(data_width)) u_stage0_row2 (
        .in0(din2), .in1(din6), .in2(din10), .in3(din14),
        .row_sum(stage0_row2), .row_alt(stage1_row2),
        .row_sum_alias(stage0_row2_alias), .row_alt_alias(stage1_row2_alias)
    );
    u22_high_input_row #(.DATA_W(data_width)) u_stage0_row3 (
        .in0(din3), .in1(din7), .in2(din11), .in3(din15),
        .row_sum(stage0_row3), .row_alt(stage1_row3),
        .row_sum_alias(stage0_row3_alias), .row_alt_alias(stage1_row3_alias)
    );

    u22_high_out_mix #(.DATA_W(data_width)) u_stage2_out0 (
        .in0(stage0_row0_alias), .in1(stage0_row1_alias), .in2(stage0_row2_alias), .in3(stage0_row3_alias),
        .out_sum(stage2_sum0), .out_diff(stage2_diff0),
        .out_sum_alias(stage2_sum0_alias), .out_diff_alias(stage2_diff0_alias)
    );
    u22_high_out_mix #(.DATA_W(data_width)) u_stage2_out1 (
        .in0(stage1_row0_alias), .in1(stage1_row1_alias), .in2(stage1_row2_alias), .in3(stage1_row3_alias),
        .out_sum(stage2_sum1), .out_diff(stage2_diff1),
        .out_sum_alias(stage2_sum1_alias), .out_diff_alias(stage2_diff1_alias)
    );

    u22_high_passthrough #(.DATA_W(data_width)) u_out0 (.in_data(stage2_sum0_alias), .out_data(dout0_stage), .out_alias(dout0_alias));
    u22_high_passthrough #(.DATA_W(data_width)) u_out1 (.in_data(stage2_diff0_alias), .out_data(dout1_stage), .out_alias(dout1_alias));
    u22_high_passthrough #(.DATA_W(data_width)) u_out2 (.in_data(stage2_sum1_alias), .out_data(dout2_stage), .out_alias(dout2_alias));
    u22_high_passthrough #(.DATA_W(data_width)) u_out3 (.in_data(stage2_diff1_alias), .out_data(dout3_stage), .out_alias(dout3_alias));

    assign dout0 = dout0_alias;
    assign dout1 = dout1_alias;
    assign dout2 = dout2_alias;
    assign dout3 = dout3_alias;
endmodule
