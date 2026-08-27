module AdderTree_signed #(
    parameter width = 21
)(
    input wire [width:1] A1,
    input wire [width:1] A2,
    input wire [width:1] A3,
    input wire [width:1] A4,
    input wire [width:1] A5,
    output wire [width+3:1] S
);

    localparam integer OUT_W = width + 3;

    wire signed [OUT_W-1:0] ext_a1;
    wire signed [OUT_W-1:0] ext_a2;
    wire signed [OUT_W-1:0] ext_a3;
    wire signed [OUT_W-1:0] ext_a4;
    wire signed [OUT_W-1:0] ext_a5;

    wire signed [OUT_W-1:0] stage0_lane0;
    wire signed [OUT_W-1:0] stage0_lane1;
    wire signed [OUT_W-1:0] stage0_lane2;
    wire signed [OUT_W-1:0] stage0_lane3;
    wire signed [OUT_W-1:0] stage0_lane4;

    wire signed [OUT_W-1:0] stage1_sum0;
    wire signed [OUT_W-1:0] stage1_sum1;
    wire signed [OUT_W-1:0] stage1_tail0;

    wire signed [OUT_W-1:0] stage2_sum0;
    wire signed [OUT_W-1:0] stage2_tail0;

    wire signed [OUT_W-1:0] stage3_sum0;
    wire signed [OUT_W-1:0] stage3_sum1;

    wire signed [OUT_W-1:0] final_sum0;
    wire signed [OUT_W-1:0] final_sum1;

    assign ext_a1 = {{(OUT_W-width){A1[width]}}, A1};
    assign ext_a2 = {{(OUT_W-width){A2[width]}}, A2};
    assign ext_a3 = {{(OUT_W-width){A3[width]}}, A3};
    assign ext_a4 = {{(OUT_W-width){A4[width]}}, A4};
    assign ext_a5 = {{(OUT_W-width){A5[width]}}, A5};

    assign stage0_lane0 = ext_a1;
    assign stage0_lane1 = ext_a2;
    assign stage0_lane2 = ext_a3;
    assign stage0_lane3 = ext_a4;
    assign stage0_lane4 = ext_a5;

    assign stage1_sum0 = stage0_lane0 + stage0_lane1;
    assign stage1_sum1 = stage0_lane2 + stage0_lane3;
    assign stage1_tail0 = stage0_lane4;

    assign stage2_sum0 = stage1_sum0 + stage1_sum1;
    assign stage2_tail0 = stage1_tail0;

    assign stage3_sum0 = stage2_sum0;
    assign stage3_sum1 = stage2_tail0;

    assign final_sum0 = stage3_sum0 + stage3_sum1;
    assign final_sum1 = final_sum0;

    assign S = final_sum1;

endmodule
