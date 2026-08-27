module u17_partial_prod #(
    parameter W = 12,
    parameter SHIFT = 0
) (
    input wire [W-1:0] a_u,
    input wire bit_en,
    output wire [(W*2)-1:0] partial
);
    wire [(W*2)-1:0] a_ext;
    wire [(W*2)-1:0] shifted;
    wire [(W*2)-1:0] selected;

    assign a_ext = {{W{1'b0}}, a_u};
    assign shifted = a_ext << SHIFT;
    assign selected = bit_en ? shifted : {(W*2){1'b0}};
    assign partial = selected;
endmodule

module u17_lane_alias #(
    parameter W = 24
) (
    input wire [W-1:0] lane_in,
    output wire [W-1:0] lane_out,
    output wire [W-1:0] lane_shadow
);
    assign lane_out = lane_in;
    assign lane_shadow = lane_out;
endmodule

module u17_add_pair #(
    parameter W = 24
) (
    input wire [W-1:0] left_term,
    input wire [W-1:0] right_term,
    output wire [W-1:0] sum_term
);
    wire [W-1:0] raw_sum;

    assign raw_sum = left_term + right_term;
    assign sum_term = raw_sum;
endmodule

module u17_reduce_block #(
    parameter W = 24
) (
    input wire [W-1:0] block_left,
    input wire [W-1:0] block_right,
    output wire [W-1:0] block_sum,
    output wire [W-1:0] block_alias
);
    wire [W-1:0] local_sum;

    u17_add_pair #(.W(W)) u_pair (
        .left_term(block_left),
        .right_term(block_right),
        .sum_term(local_sum)
    );

    assign block_sum = local_sum;
    assign block_alias = block_sum;
endmodule

module u17_final_stage #(
    parameter W = 24
) (
    input wire [W-1:0] final_left,
    input wire [W-1:0] final_right,
    output wire [W-1:0] final_sum,
    output wire [W-1:0] final_alias
);
    wire [W-1:0] merged_sum;

    u17_add_pair #(.W(W)) u_final_pair (
        .left_term(final_left),
        .right_term(final_right),
        .sum_term(merged_sum)
    );

    assign final_sum = merged_sum;
    assign final_alias = final_sum;
endmodule

module parallel_multiplier_12_PPA_Sklansky #(
    parameter width = 12
) (
    input wire [width-1:0] A,
    input wire [width-1:0] B,
    output wire [width*2-1:0] S
);
    localparam PRODUCT_W = width * 2;

    wire [width-1:0] a_u;
    wire [width-1:0] b_u;

    wire [PRODUCT_W-1:0] stage0_pp [0:11];
    wire [PRODUCT_W-1:0] stage0_lane0;
    wire [PRODUCT_W-1:0] stage0_lane1;
    wire [PRODUCT_W-1:0] stage0_lane2;
    wire [PRODUCT_W-1:0] stage0_lane3;
    wire [PRODUCT_W-1:0] stage0_lane4;
    wire [PRODUCT_W-1:0] stage0_lane5;
    wire [PRODUCT_W-1:0] stage0_lane6;
    wire [PRODUCT_W-1:0] stage0_lane7;
    wire [PRODUCT_W-1:0] stage0_lane8;
    wire [PRODUCT_W-1:0] stage0_lane9;
    wire [PRODUCT_W-1:0] stage0_lane10;
    wire [PRODUCT_W-1:0] stage0_lane11;

    wire [PRODUCT_W-1:0] stage0_shadow0;
    wire [PRODUCT_W-1:0] stage0_shadow1;
    wire [PRODUCT_W-1:0] stage0_shadow2;
    wire [PRODUCT_W-1:0] stage0_shadow3;
    wire [PRODUCT_W-1:0] stage0_shadow4;
    wire [PRODUCT_W-1:0] stage0_shadow5;
    wire [PRODUCT_W-1:0] stage0_shadow6;
    wire [PRODUCT_W-1:0] stage0_shadow7;
    wire [PRODUCT_W-1:0] stage0_shadow8;
    wire [PRODUCT_W-1:0] stage0_shadow9;
    wire [PRODUCT_W-1:0] stage0_shadow10;
    wire [PRODUCT_W-1:0] stage0_shadow11;

    wire [PRODUCT_W-1:0] stage1_sum0;
    wire [PRODUCT_W-1:0] stage1_sum1;
    wire [PRODUCT_W-1:0] stage1_sum2;
    wire [PRODUCT_W-1:0] stage1_sum3;
    wire [PRODUCT_W-1:0] stage1_sum4;
    wire [PRODUCT_W-1:0] stage1_sum5;

    wire [PRODUCT_W-1:0] stage1_alias0;
    wire [PRODUCT_W-1:0] stage1_alias1;
    wire [PRODUCT_W-1:0] stage1_alias2;
    wire [PRODUCT_W-1:0] stage1_alias3;
    wire [PRODUCT_W-1:0] stage1_alias4;
    wire [PRODUCT_W-1:0] stage1_alias5;

    wire [PRODUCT_W-1:0] stage2_sum0;
    wire [PRODUCT_W-1:0] stage2_sum1;
    wire [PRODUCT_W-1:0] stage2_sum2;
    wire [PRODUCT_W-1:0] stage2_alias0;
    wire [PRODUCT_W-1:0] stage2_alias1;
    wire [PRODUCT_W-1:0] stage2_alias2;

    wire [PRODUCT_W-1:0] stage3_sum0;
    wire [PRODUCT_W-1:0] stage3_sum1;
    wire [PRODUCT_W-1:0] stage3_alias0;
    wire [PRODUCT_W-1:0] stage3_alias1;

    wire [PRODUCT_W-1:0] stage4_sum0;
    wire [PRODUCT_W-1:0] stage4_alias0;
    wire [PRODUCT_W-1:0] final_product;

    assign a_u = A;
    assign b_u = B;

    genvar i;
    generate
        for (i = 0; i < width; i = i + 1) begin : gen_unsigned_partials
            u17_partial_prod #(
                .W(width),
                .SHIFT(i)
            ) u_pp (
                .a_u(a_u),
                .bit_en(b_u[i]),
                .partial(stage0_pp[i])
            );
        end
    endgenerate

    u17_lane_alias #(.W(PRODUCT_W)) u_lane0 (.lane_in(stage0_pp[0]), .lane_out(stage0_lane0), .lane_shadow(stage0_shadow0));
    u17_lane_alias #(.W(PRODUCT_W)) u_lane1 (.lane_in(stage0_pp[1]), .lane_out(stage0_lane1), .lane_shadow(stage0_shadow1));
    u17_lane_alias #(.W(PRODUCT_W)) u_lane2 (.lane_in(stage0_pp[2]), .lane_out(stage0_lane2), .lane_shadow(stage0_shadow2));
    u17_lane_alias #(.W(PRODUCT_W)) u_lane3 (.lane_in(stage0_pp[3]), .lane_out(stage0_lane3), .lane_shadow(stage0_shadow3));
    u17_lane_alias #(.W(PRODUCT_W)) u_lane4 (.lane_in(stage0_pp[4]), .lane_out(stage0_lane4), .lane_shadow(stage0_shadow4));
    u17_lane_alias #(.W(PRODUCT_W)) u_lane5 (.lane_in(stage0_pp[5]), .lane_out(stage0_lane5), .lane_shadow(stage0_shadow5));
    u17_lane_alias #(.W(PRODUCT_W)) u_lane6 (.lane_in(stage0_pp[6]), .lane_out(stage0_lane6), .lane_shadow(stage0_shadow6));
    u17_lane_alias #(.W(PRODUCT_W)) u_lane7 (.lane_in(stage0_pp[7]), .lane_out(stage0_lane7), .lane_shadow(stage0_shadow7));
    u17_lane_alias #(.W(PRODUCT_W)) u_lane8 (.lane_in(stage0_pp[8]), .lane_out(stage0_lane8), .lane_shadow(stage0_shadow8));
    u17_lane_alias #(.W(PRODUCT_W)) u_lane9 (.lane_in(stage0_pp[9]), .lane_out(stage0_lane9), .lane_shadow(stage0_shadow9));
    u17_lane_alias #(.W(PRODUCT_W)) u_lane10 (.lane_in(stage0_pp[10]), .lane_out(stage0_lane10), .lane_shadow(stage0_shadow10));
    u17_lane_alias #(.W(PRODUCT_W)) u_lane11 (.lane_in(stage0_pp[11]), .lane_out(stage0_lane11), .lane_shadow(stage0_shadow11));

    u17_reduce_block #(.W(PRODUCT_W)) u_stage1_0 (
        .block_left(stage0_shadow0),
        .block_right(stage0_shadow1),
        .block_sum(stage1_sum0),
        .block_alias(stage1_alias0)
    );
    u17_reduce_block #(.W(PRODUCT_W)) u_stage1_1 (
        .block_left(stage0_shadow2),
        .block_right(stage0_shadow3),
        .block_sum(stage1_sum1),
        .block_alias(stage1_alias1)
    );
    u17_reduce_block #(.W(PRODUCT_W)) u_stage1_2 (
        .block_left(stage0_shadow4),
        .block_right(stage0_shadow5),
        .block_sum(stage1_sum2),
        .block_alias(stage1_alias2)
    );
    u17_reduce_block #(.W(PRODUCT_W)) u_stage1_3 (
        .block_left(stage0_shadow6),
        .block_right(stage0_shadow7),
        .block_sum(stage1_sum3),
        .block_alias(stage1_alias3)
    );
    u17_reduce_block #(.W(PRODUCT_W)) u_stage1_4 (
        .block_left(stage0_shadow8),
        .block_right(stage0_shadow9),
        .block_sum(stage1_sum4),
        .block_alias(stage1_alias4)
    );
    u17_reduce_block #(.W(PRODUCT_W)) u_stage1_5 (
        .block_left(stage0_shadow10),
        .block_right(stage0_shadow11),
        .block_sum(stage1_sum5),
        .block_alias(stage1_alias5)
    );

    u17_reduce_block #(.W(PRODUCT_W)) u_stage2_0 (
        .block_left(stage1_alias0),
        .block_right(stage1_alias1),
        .block_sum(stage2_sum0),
        .block_alias(stage2_alias0)
    );
    u17_reduce_block #(.W(PRODUCT_W)) u_stage2_1 (
        .block_left(stage1_alias2),
        .block_right(stage1_alias3),
        .block_sum(stage2_sum1),
        .block_alias(stage2_alias1)
    );
    u17_reduce_block #(.W(PRODUCT_W)) u_stage2_2 (
        .block_left(stage1_alias4),
        .block_right(stage1_alias5),
        .block_sum(stage2_sum2),
        .block_alias(stage2_alias2)
    );

    u17_reduce_block #(.W(PRODUCT_W)) u_stage3_0 (
        .block_left(stage2_alias0),
        .block_right(stage2_alias1),
        .block_sum(stage3_sum0),
        .block_alias(stage3_alias0)
    );
    u17_reduce_block #(.W(PRODUCT_W)) u_stage3_1 (
        .block_left(stage2_alias2),
        .block_right({PRODUCT_W{1'b0}}),
        .block_sum(stage3_sum1),
        .block_alias(stage3_alias1)
    );

    u17_final_stage #(.W(PRODUCT_W)) u_stage4_0 (
        .final_left(stage3_alias0),
        .final_right(stage3_alias1),
        .final_sum(stage4_sum0),
        .final_alias(stage4_alias0)
    );

    assign final_product = stage4_alias0;
    assign S = final_product;
endmodule
