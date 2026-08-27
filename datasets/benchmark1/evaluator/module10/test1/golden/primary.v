module signed_addertree_19_8_PPA_Sklansky #(
    parameter width = 19
) (
    input wire signed [width:1] A1,
    input wire signed [width:1] A2,
    input wire signed [width:1] A3,
    input wire signed [width:1] A4,
    input wire signed [width:1] A5,
    input wire signed [width:1] A6,
    input wire signed [width:1] A7,
    input wire signed [width:1] A8,
    output wire signed [width + 3:1] S
);

    localparam integer SUM_WIDTH = width + 3;

    wire sign_a1;
    wire sign_a2;
    wire sign_a3;
    wire sign_a4;
    wire sign_a5;
    wire sign_a6;
    wire sign_a7;
    wire sign_a8;

    wire signed [SUM_WIDTH:1] ext_a1;
    wire signed [SUM_WIDTH:1] ext_a2;
    wire signed [SUM_WIDTH:1] ext_a3;
    wire signed [SUM_WIDTH:1] ext_a4;
    wire signed [SUM_WIDTH:1] ext_a5;
    wire signed [SUM_WIDTH:1] ext_a6;
    wire signed [SUM_WIDTH:1] ext_a7;
    wire signed [SUM_WIDTH:1] ext_a8;

    wire signed [SUM_WIDTH:1] lane_a0;
    wire signed [SUM_WIDTH:1] lane_a1;
    wire signed [SUM_WIDTH:1] lane_a2;
    wire signed [SUM_WIDTH:1] lane_a3;
    wire signed [SUM_WIDTH:1] lane_a4;
    wire signed [SUM_WIDTH:1] lane_a5;
    wire signed [SUM_WIDTH:1] lane_a6;
    wire signed [SUM_WIDTH:1] lane_a7;

    wire signed [SUM_WIDTH:1] flat_sum0;
    wire signed [SUM_WIDTH:1] flat_sum1;
    wire signed [SUM_WIDTH:1] flat_sum2;
    wire signed [SUM_WIDTH:1] flat_sum3;
    wire signed [SUM_WIDTH:1] flat_sum4;
    wire signed [SUM_WIDTH:1] flat_sum5;
    wire signed [SUM_WIDTH:1] flat_sum6;

    wire signed [SUM_WIDTH:1] final_path0;
    wire signed [SUM_WIDTH:1] final_path1;

    assign sign_a1 = A1[width];
    assign sign_a2 = A2[width];
    assign sign_a3 = A3[width];
    assign sign_a4 = A4[width];
    assign sign_a5 = A5[width];
    assign sign_a6 = A6[width];
    assign sign_a7 = A7[width];
    assign sign_a8 = A8[width];

    assign ext_a1[width:1] = A1;
    assign ext_a2[width:1] = A2;
    assign ext_a3[width:1] = A3;
    assign ext_a4[width:1] = A4;
    assign ext_a5[width:1] = A5;
    assign ext_a6[width:1] = A6;
    assign ext_a7[width:1] = A7;
    assign ext_a8[width:1] = A8;

    assign ext_a1[SUM_WIDTH] = sign_a1;
    assign ext_a1[SUM_WIDTH - 1] = sign_a1;
    assign ext_a1[SUM_WIDTH - 2] = sign_a1;
    assign ext_a2[SUM_WIDTH] = sign_a2;
    assign ext_a2[SUM_WIDTH - 1] = sign_a2;
    assign ext_a2[SUM_WIDTH - 2] = sign_a2;
    assign ext_a3[SUM_WIDTH] = sign_a3;
    assign ext_a3[SUM_WIDTH - 1] = sign_a3;
    assign ext_a3[SUM_WIDTH - 2] = sign_a3;
    assign ext_a4[SUM_WIDTH] = sign_a4;
    assign ext_a4[SUM_WIDTH - 1] = sign_a4;
    assign ext_a4[SUM_WIDTH - 2] = sign_a4;
    assign ext_a5[SUM_WIDTH] = sign_a5;
    assign ext_a5[SUM_WIDTH - 1] = sign_a5;
    assign ext_a5[SUM_WIDTH - 2] = sign_a5;
    assign ext_a6[SUM_WIDTH] = sign_a6;
    assign ext_a6[SUM_WIDTH - 1] = sign_a6;
    assign ext_a6[SUM_WIDTH - 2] = sign_a6;
    assign ext_a7[SUM_WIDTH] = sign_a7;
    assign ext_a7[SUM_WIDTH - 1] = sign_a7;
    assign ext_a7[SUM_WIDTH - 2] = sign_a7;
    assign ext_a8[SUM_WIDTH] = sign_a8;
    assign ext_a8[SUM_WIDTH - 1] = sign_a8;
    assign ext_a8[SUM_WIDTH - 2] = sign_a8;

    assign lane_a0 = ext_a1;
    assign lane_a1 = ext_a2;
    assign lane_a2 = ext_a3;
    assign lane_a3 = ext_a4;
    assign lane_a4 = ext_a5;
    assign lane_a5 = ext_a6;
    assign lane_a6 = ext_a7;
    assign lane_a7 = ext_a8;

    assign flat_sum0 = lane_a0 + lane_a1;
    assign flat_sum1 = flat_sum0 + lane_a2;
    assign flat_sum2 = flat_sum1 + lane_a3;
    assign flat_sum3 = flat_sum2 + lane_a4;
    assign flat_sum4 = flat_sum3 + lane_a5;
    assign flat_sum5 = flat_sum4 + lane_a6;
    assign flat_sum6 = flat_sum5 + lane_a7;

    assign final_path0 = flat_sum6;
    assign final_path1 = final_path0;

    assign S = final_path1;

endmodule
