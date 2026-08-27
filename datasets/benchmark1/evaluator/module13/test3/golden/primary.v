module u13_partial_prod #(
    parameter W = 8,
    parameter SHIFT = 0
) (
    input wire [W-1:0] a_u,
    input wire bit_en,
    output wire [(W*2)-1:0] partial
);
    wire [(W*2)-1:0] a_ext = {{W{1'b0}}, a_u};
    wire [(W*2)-1:0] shifted = a_ext << SHIFT;
    assign partial = bit_en ? shifted : {(W*2){1'b0}};
endmodule

module u13_add_pair #(
    parameter W = 16
) (
    input wire [W-1:0] left_term,
    input wire [W-1:0] right_term,
    output wire [W-1:0] sum_term
);
    assign sum_term = left_term + right_term;
endmodule

module Multi_Booth_unsigned #(
    parameter width = 8
) (
    input wire [width:1] A,
    input wire [width:1] B,
    output wire [width*2:1] P
);
    localparam PRODUCT_W = width * 2;

    wire [width-1:0] a_u = A[width:1];
    wire [width-1:0] b_u = B[width:1];

    wire [PRODUCT_W-1:0] stage0_pp [0:7];
    wire [PRODUCT_W-1:0] stage0_pos0;
    wire [PRODUCT_W-1:0] stage0_pos1;
    wire [PRODUCT_W-1:0] stage0_pos2;
    wire [PRODUCT_W-1:0] stage0_pos3;
    wire [PRODUCT_W-1:0] stage0_pos4;
    wire [PRODUCT_W-1:0] stage0_pos5;
    wire [PRODUCT_W-1:0] stage0_pos6;
    wire [PRODUCT_W-1:0] stage0_pos7;

    wire [PRODUCT_W-1:0] stage1_sum0;
    wire [PRODUCT_W-1:0] stage1_sum1;
    wire [PRODUCT_W-1:0] stage1_sum2;
    wire [PRODUCT_W-1:0] stage1_sum3;

    wire [PRODUCT_W-1:0] stage2_sum0;
    wire [PRODUCT_W-1:0] stage2_sum1;
    wire [PRODUCT_W-1:0] stage2_alias0;
    wire [PRODUCT_W-1:0] stage2_alias1;

    wire [PRODUCT_W-1:0] stage3_sum0;
    wire [PRODUCT_W-1:0] stage3_alias0;
    wire [PRODUCT_W-1:0] final_alias;
    wire [PRODUCT_W-1:0] final_product;

    genvar i;
    generate
        for (i = 0; i < width; i = i + 1) begin : gen_partials
            u13_partial_prod #(
                .W(width),
                .SHIFT(i)
            ) u_pp (
                .a_u(a_u),
                .bit_en(b_u[i]),
                .partial(stage0_pp[i])
            );
        end
    endgenerate

    assign stage0_pos0 = stage0_pp[0];
    assign stage0_pos1 = stage0_pp[1];
    assign stage0_pos2 = stage0_pp[2];
    assign stage0_pos3 = stage0_pp[3];
    assign stage0_pos4 = stage0_pp[4];
    assign stage0_pos5 = stage0_pp[5];
    assign stage0_pos6 = stage0_pp[6];
    assign stage0_pos7 = stage0_pp[7];

    u13_add_pair #(.W(PRODUCT_W)) u_stage1_0 (.left_term(stage0_pos0), .right_term(stage0_pos1), .sum_term(stage1_sum0));
    u13_add_pair #(.W(PRODUCT_W)) u_stage1_1 (.left_term(stage0_pos2), .right_term(stage0_pos3), .sum_term(stage1_sum1));
    u13_add_pair #(.W(PRODUCT_W)) u_stage1_2 (.left_term(stage0_pos4), .right_term(stage0_pos5), .sum_term(stage1_sum2));
    u13_add_pair #(.W(PRODUCT_W)) u_stage1_3 (.left_term(stage0_pos6), .right_term(stage0_pos7), .sum_term(stage1_sum3));

    u13_add_pair #(.W(PRODUCT_W)) u_stage2_0 (.left_term(stage1_sum0), .right_term(stage1_sum1), .sum_term(stage2_sum0));
    u13_add_pair #(.W(PRODUCT_W)) u_stage2_1 (.left_term(stage1_sum2), .right_term(stage1_sum3), .sum_term(stage2_sum1));

    assign stage2_alias0 = stage2_sum0;
    assign stage2_alias1 = stage2_sum1;

    u13_add_pair #(.W(PRODUCT_W)) u_stage3_0 (.left_term(stage2_alias0), .right_term(stage2_alias1), .sum_term(stage3_sum0));

    assign stage3_alias0 = stage3_sum0;
    assign final_alias = stage3_alias0;
    assign final_product = final_alias;
    assign P = final_product;
endmodule
