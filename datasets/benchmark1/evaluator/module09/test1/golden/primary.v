module AdderTree_unsigned #(
    parameter width = 17
) (
    input wire [width:1] A1,
    input wire [width:1] A2,
    input wire [width:1] A3,
    input wire [width:1] A4,
    output wire [width + 2:1] S
);

    localparam integer SUM_WIDTH = width + 2;

    wire [SUM_WIDTH:1] ext_a1;
    wire [SUM_WIDTH:1] ext_a2;
    wire [SUM_WIDTH:1] ext_a3;
    wire [SUM_WIDTH:1] ext_a4;

    wire [SUM_WIDTH:1] stage0_sum0;
    wire [SUM_WIDTH:1] stage0_sum1;

    wire [SUM_WIDTH:1] stage1_left;
    wire [SUM_WIDTH:1] stage1_right;
    wire [SUM_WIDTH:1] final_sum;

    assign ext_a1 = {{2{1'b0}}, A1};
    assign ext_a2 = {{2{1'b0}}, A2};
    assign ext_a3 = {{2{1'b0}}, A3};
    assign ext_a4 = {{2{1'b0}}, A4};

    assign stage0_sum0 = ext_a1 + ext_a2;
    assign stage0_sum1 = ext_a3 + ext_a4;

    assign stage1_left = stage0_sum0;
    assign stage1_right = stage0_sum1;
    assign final_sum = stage1_left + stage1_right;

    assign S = final_sum;

endmodule
