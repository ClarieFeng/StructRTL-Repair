module u14_partial_prod #(
    parameter W = 10,
    parameter SHIFT = 0,
    parameter NEGATE = 0
) (
    input wire signed [W-1:0] a_s,
    input wire bit_en,
    output wire signed [(W*2)-1:0] partial
);
    wire signed [(W*2)-1:0] a_ext;
    wire signed [(W*2)-1:0] shifted;
    wire signed [(W*2)-1:0] selected;

    assign a_ext = {{W{a_s[W-1]}}, a_s};
    assign shifted = a_ext <<< SHIFT;
    assign selected = bit_en ? shifted : {(W*2){1'b0}};
    assign partial = NEGATE ? -selected : selected;
endmodule

module u14_add_pair #(
    parameter W = 20
) (
    input wire signed [W-1:0] left_term,
    input wire signed [W-1:0] right_term,
    output wire signed [W-1:0] sum_term
);
    assign sum_term = left_term + right_term;
endmodule

module Multi_signed #(
    parameter width = 10
) (
    input wire [width:1] A,
    input wire [width:1] B,
    output wire [width*2:1] P
);
    localparam PRODUCT_W = width * 2;

    wire signed [width-1:0] a_s;
    wire signed [width-1:0] b_s;

    wire signed [PRODUCT_W-1:0] stage0_pp [0:8];
    wire signed [PRODUCT_W-1:0] stage0_neg;
    wire signed [PRODUCT_W-1:0] stage0_pos0;
    wire signed [PRODUCT_W-1:0] stage0_pos1;
    wire signed [PRODUCT_W-1:0] stage0_pos2;
    wire signed [PRODUCT_W-1:0] stage0_pos3;
    wire signed [PRODUCT_W-1:0] stage0_pos4;
    wire signed [PRODUCT_W-1:0] stage0_pos5;
    wire signed [PRODUCT_W-1:0] stage0_pos6;
    wire signed [PRODUCT_W-1:0] stage0_pos7;
    wire signed [PRODUCT_W-1:0] stage0_pos8;

    wire signed [PRODUCT_W-1:0] stage1_sum0;
    wire signed [PRODUCT_W-1:0] stage1_sum1;
    wire signed [PRODUCT_W-1:0] stage1_sum2;
    wire signed [PRODUCT_W-1:0] stage1_sum3;
    wire signed [PRODUCT_W-1:0] stage1_sum4;

    wire signed [PRODUCT_W-1:0] stage2_sum0;
    wire signed [PRODUCT_W-1:0] stage2_sum1;
    wire signed [PRODUCT_W-1:0] stage2_sum2;
    wire signed [PRODUCT_W-1:0] stage2_alias0;
    wire signed [PRODUCT_W-1:0] stage2_alias1;
    wire signed [PRODUCT_W-1:0] stage2_alias2;

    wire signed [PRODUCT_W-1:0] stage3_sum0;
    wire signed [PRODUCT_W-1:0] stage3_sum1;
    wire signed [PRODUCT_W-1:0] stage3_alias0;
    wire signed [PRODUCT_W-1:0] stage3_alias1;
    wire signed [PRODUCT_W-1:0] final_product_pre;
    wire signed [PRODUCT_W-1:0] final_product;

    assign a_s = A[width:1];
    assign b_s = B[width:1];

    genvar i;
    generate
        for (i = 0; i < width - 1; i = i + 1) begin : gen_positive_partials
            u14_partial_prod #(
                .W(width),
                .SHIFT(i),
                .NEGATE(0)
            ) u_pp (
                .a_s(a_s),
                .bit_en(b_s[i]),
                .partial(stage0_pp[i])
            );
        end
    endgenerate

    u14_partial_prod #(
        .W(width),
        .SHIFT(width - 1),
        .NEGATE(1)
    ) u_neg_pp (
        .a_s(a_s),
        .bit_en(b_s[width - 1]),
        .partial(stage0_neg)
    );

    assign stage0_pos0 = stage0_pp[0];
    assign stage0_pos1 = stage0_pp[1];
    assign stage0_pos2 = stage0_pp[2];
    assign stage0_pos3 = stage0_pp[3];
    assign stage0_pos4 = stage0_pp[4];
    assign stage0_pos5 = stage0_pp[5];
    assign stage0_pos6 = stage0_pp[6];
    assign stage0_pos7 = stage0_pp[7];
    assign stage0_pos8 = stage0_pp[8];

    u14_add_pair #(.W(PRODUCT_W)) u_stage1_0 (.left_term(stage0_pos0), .right_term(stage0_pos1), .sum_term(stage1_sum0));
    u14_add_pair #(.W(PRODUCT_W)) u_stage1_1 (.left_term(stage0_pos2), .right_term(stage0_pos3), .sum_term(stage1_sum1));
    u14_add_pair #(.W(PRODUCT_W)) u_stage1_2 (.left_term(stage0_pos4), .right_term(stage0_pos5), .sum_term(stage1_sum2));
    u14_add_pair #(.W(PRODUCT_W)) u_stage1_3 (.left_term(stage0_pos6), .right_term(stage0_pos7), .sum_term(stage1_sum3));
    u14_add_pair #(.W(PRODUCT_W)) u_stage1_4 (.left_term(stage0_pos8), .right_term(stage0_neg), .sum_term(stage1_sum4));

    u14_add_pair #(.W(PRODUCT_W)) u_stage2_0 (.left_term(stage1_sum0), .right_term(stage1_sum1), .sum_term(stage2_sum0));
    u14_add_pair #(.W(PRODUCT_W)) u_stage2_1 (.left_term(stage1_sum2), .right_term(stage1_sum3), .sum_term(stage2_sum1));
    u14_add_pair #(.W(PRODUCT_W)) u_stage2_2 (.left_term(stage1_sum4), .right_term({PRODUCT_W{1'b0}}), .sum_term(stage2_sum2));

    assign stage2_alias0 = stage2_sum0;
    assign stage2_alias1 = stage2_sum1;
    assign stage2_alias2 = stage2_sum2;

    u14_add_pair #(.W(PRODUCT_W)) u_stage3_0 (.left_term(stage2_alias0), .right_term(stage2_alias1), .sum_term(stage3_sum0));
    u14_add_pair #(.W(PRODUCT_W)) u_stage3_1 (.left_term(stage2_alias2), .right_term({PRODUCT_W{1'b0}}), .sum_term(stage3_sum1));

    assign stage3_alias0 = stage3_sum0;
    assign stage3_alias1 = stage3_sum1;
    assign final_product_pre = stage3_alias0 + stage3_alias1;
    assign final_product = final_product_pre;
    assign P = final_product;
endmodule
