module signed_addertree_18_9_PPA_Kogge_Stone #(
    parameter width = 18
) (
    input wire signed [width:1] A1,
    input wire signed [width:1] A2,
    input wire signed [width:1] A3,
    input wire signed [width:1] A4,
    input wire signed [width:1] A5,
    input wire signed [width:1] A6,
    input wire signed [width:1] A7,
    input wire signed [width:1] A8,
    input wire signed [width:1] A9,
    output wire signed [width + 4:1] S
);

    localparam integer SUM_WIDTH = width + 4;

    wire signed [SUM_WIDTH:1] ext_a1;
    wire signed [SUM_WIDTH:1] ext_a2;
    wire signed [SUM_WIDTH:1] ext_a3;
    wire signed [SUM_WIDTH:1] ext_a4;
    wire signed [SUM_WIDTH:1] ext_a5;
    wire signed [SUM_WIDTH:1] ext_a6;
    wire signed [SUM_WIDTH:1] ext_a7;
    wire signed [SUM_WIDTH:1] ext_a8;
    wire signed [SUM_WIDTH:1] ext_a9;

    wire signed [SUM_WIDTH:1] stage0_lane0;
    wire signed [SUM_WIDTH:1] stage0_lane1;
    wire signed [SUM_WIDTH:1] stage0_lane2;
    wire signed [SUM_WIDTH:1] stage0_lane3;
    wire signed [SUM_WIDTH:1] stage0_lane4;

    wire signed [SUM_WIDTH:1] stage1_sum0;
    wire signed [SUM_WIDTH:1] stage1_sum1;
    wire signed [SUM_WIDTH:1] stage1_sum2;
    wire signed [SUM_WIDTH:1] stage1_sum3;
    wire signed [SUM_WIDTH:1] stage1_tail0;

    wire signed [SUM_WIDTH:1] stage2_sum0;
    wire signed [SUM_WIDTH:1] stage2_sum1;
    wire signed [SUM_WIDTH:1] stage2_tail0;
    wire signed [SUM_WIDTH:1] stage2_tail1;

    wire signed [SUM_WIDTH:1] stage3_sum0;
    wire signed [SUM_WIDTH:1] stage3_sum1;
    wire signed [SUM_WIDTH:1] stage3_tail0;

    wire signed [SUM_WIDTH:1] stage4_sum0;
    wire signed [SUM_WIDTH:1] stage4_tail0;

    wire signed [SUM_WIDTH:1] merge_sum0;
    wire signed [SUM_WIDTH:1] merge_sum1;
    wire signed [SUM_WIDTH:1] merge_sum2;
    wire signed [SUM_WIDTH:1] merge_sum3;

    assign ext_a1 = {{4{A1[width]}}, A1};
    assign ext_a2 = {{4{A2[width]}}, A2};
    assign ext_a3 = {{4{A3[width]}}, A3};
    assign ext_a4 = {{4{A4[width]}}, A4};
    assign ext_a5 = {{4{A5[width]}}, A5};
    assign ext_a6 = {{4{A6[width]}}, A6};
    assign ext_a7 = {{4{A7[width]}}, A7};
    assign ext_a8 = {{4{A8[width]}}, A8};
    assign ext_a9 = {{4{A9[width]}}, A9};

    assign stage0_lane0 = ext_a1;
    assign stage0_lane1 = ext_a2;
    assign stage0_lane2 = ext_a3;
    assign stage0_lane3 = ext_a4;
    assign stage0_lane4 = ext_a5;

    assign stage1_sum0 = stage0_lane0 + stage0_lane1;
    assign stage1_sum1 = stage0_lane2 + stage0_lane3;
    assign stage1_sum2 = stage0_lane4 + ext_a6;
    assign stage1_sum3 = ext_a7 + ext_a8;
    assign stage1_tail0 = ext_a9;

    assign stage2_sum0 = stage1_sum0 + stage1_sum1;
    assign stage2_sum1 = stage1_sum2 + stage1_sum3;
    assign stage2_tail0 = stage1_tail0;
    assign stage2_tail1 = {SUM_WIDTH{1'b0}};

    assign stage3_sum0 = stage2_sum0 + stage2_sum1;
    assign stage3_sum1 = stage2_tail0 + stage2_tail1;
    assign stage3_tail0 = {SUM_WIDTH{1'b0}};

    assign stage4_sum0 = stage3_sum0 + stage3_sum1;
    assign stage4_tail0 = stage3_tail0;

    assign merge_sum0 = stage4_sum0;
    assign merge_sum1 = merge_sum0 + stage4_tail0;
    assign merge_sum2 = merge_sum1;
    assign merge_sum3 = merge_sum2;

    assign S = merge_sum3;

endmodule
