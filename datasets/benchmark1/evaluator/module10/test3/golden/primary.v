module signed_add_pair_helper #(
    parameter integer WIDTH = 20
) (
    input wire signed [WIDTH:1] lhs,
    input wire signed [WIDTH:1] rhs,
    output wire signed [WIDTH:1] sum
);
    wire signed [WIDTH:1] local_lhs;
    wire signed [WIDTH:1] local_rhs;
    wire signed [WIDTH:1] pre_sum;
    wire signed [WIDTH:1] post_sum;

    assign local_lhs = lhs;
    assign local_rhs = rhs;
    assign pre_sum = local_lhs + local_rhs;
    assign post_sum = pre_sum;
    assign sum = post_sum;
endmodule

module signed_add_passthrough_helper #(
    parameter integer WIDTH = 20
) (
    input wire signed [WIDTH:1] din,
    output wire signed [WIDTH:1] dout
);
    wire signed [WIDTH:1] local_din;
    wire signed [WIDTH:1] local_dout;

    assign local_din = din;
    assign local_dout = local_din;
    assign dout = local_dout;
endmodule

module signed_addertree_17_7_PPA_Brent_Kung #(
    parameter width = 17
) (
    input wire signed [width:1] A1,
    input wire signed [width:1] A2,
    input wire signed [width:1] A3,
    input wire signed [width:1] A4,
    input wire signed [width:1] A5,
    input wire signed [width:1] A6,
    input wire signed [width:1] A7,
    output wire signed [width + 3:1] S
);

    localparam integer SUM_WIDTH = width + 3;

    wire signed [SUM_WIDTH:1] ext_a1;
    wire signed [SUM_WIDTH:1] ext_a2;
    wire signed [SUM_WIDTH:1] ext_a3;
    wire signed [SUM_WIDTH:1] ext_a4;
    wire signed [SUM_WIDTH:1] ext_a5;
    wire signed [SUM_WIDTH:1] ext_a6;
    wire signed [SUM_WIDTH:1] ext_a7;

    wire signed [SUM_WIDTH:1] input_bank0;
    wire signed [SUM_WIDTH:1] input_bank1;
    wire signed [SUM_WIDTH:1] input_bank2;
    wire signed [SUM_WIDTH:1] input_bank3;
    wire signed [SUM_WIDTH:1] input_bank4;
    wire signed [SUM_WIDTH:1] input_bank5;
    wire signed [SUM_WIDTH:1] input_bank6;

    wire signed [SUM_WIDTH:1] lane_sum0;
    wire signed [SUM_WIDTH:1] lane_sum1;
    wire signed [SUM_WIDTH:1] lane_sum2;
    wire signed [SUM_WIDTH:1] lane_tail0;

    wire signed [SUM_WIDTH:1] block_sum0;
    wire signed [SUM_WIDTH:1] block_sum1;
    wire signed [SUM_WIDTH:1] block_tail0;

    wire signed [SUM_WIDTH:1] tree_sum0;
    wire signed [SUM_WIDTH:1] tree_tail0;

    wire signed [SUM_WIDTH:1] final_sum0;
    wire signed [SUM_WIDTH:1] final_tail0;
    wire signed [SUM_WIDTH:1] final_sum1;
    wire signed [SUM_WIDTH:1] final_sum2;

    wire signed [SUM_WIDTH:1] stage_alias0;
    wire signed [SUM_WIDTH:1] stage_alias1;
    wire signed [SUM_WIDTH:1] stage_alias2;
    wire signed [SUM_WIDTH:1] stage_alias3;
    wire signed [SUM_WIDTH:1] stage_alias4;
    wire signed [SUM_WIDTH:1] stage_alias5;

    assign ext_a1 = {{3{A1[width]}}, A1};
    assign ext_a2 = {{3{A2[width]}}, A2};
    assign ext_a3 = {{3{A3[width]}}, A3};
    assign ext_a4 = {{3{A4[width]}}, A4};
    assign ext_a5 = {{3{A5[width]}}, A5};
    assign ext_a6 = {{3{A6[width]}}, A6};
    assign ext_a7 = {{3{A7[width]}}, A7};

    assign input_bank0 = ext_a1;
    assign input_bank1 = ext_a2;
    assign input_bank2 = ext_a3;
    assign input_bank3 = ext_a4;
    assign input_bank4 = ext_a5;
    assign input_bank5 = ext_a6;
    assign input_bank6 = ext_a7;

    signed_add_pair_helper #(.WIDTH(SUM_WIDTH)) lane_add0 (
        .lhs(input_bank0),
        .rhs(input_bank1),
        .sum(lane_sum0)
    );

    signed_add_pair_helper #(.WIDTH(SUM_WIDTH)) lane_add1 (
        .lhs(input_bank2),
        .rhs(input_bank3),
        .sum(lane_sum1)
    );

    signed_add_pair_helper #(.WIDTH(SUM_WIDTH)) lane_add2 (
        .lhs(input_bank4),
        .rhs(input_bank5),
        .sum(lane_sum2)
    );

    signed_add_passthrough_helper #(.WIDTH(SUM_WIDTH)) lane_tail_copy (
        .din(input_bank6),
        .dout(lane_tail0)
    );

    signed_add_pair_helper #(.WIDTH(SUM_WIDTH)) block_add0 (
        .lhs(lane_sum0),
        .rhs(lane_sum1),
        .sum(block_sum0)
    );

    signed_add_pair_helper #(.WIDTH(SUM_WIDTH)) block_add1 (
        .lhs(lane_sum2),
        .rhs(lane_tail0),
        .sum(block_sum1)
    );

    signed_add_passthrough_helper #(.WIDTH(SUM_WIDTH)) block_tail_copy (
        .din({SUM_WIDTH{1'b0}}),
        .dout(block_tail0)
    );

    signed_add_pair_helper #(.WIDTH(SUM_WIDTH)) tree_add0 (
        .lhs(block_sum0),
        .rhs(block_sum1),
        .sum(tree_sum0)
    );

    signed_add_passthrough_helper #(.WIDTH(SUM_WIDTH)) tree_tail_copy (
        .din(block_tail0),
        .dout(tree_tail0)
    );

    signed_add_pair_helper #(.WIDTH(SUM_WIDTH)) final_add0 (
        .lhs(tree_sum0),
        .rhs(tree_tail0),
        .sum(final_sum0)
    );

    signed_add_passthrough_helper #(.WIDTH(SUM_WIDTH)) final_tail_copy (
        .din(final_sum0),
        .dout(final_tail0)
    );

    signed_add_pair_helper #(.WIDTH(SUM_WIDTH)) final_add1 (
        .lhs(final_tail0),
        .rhs({SUM_WIDTH{1'b0}}),
        .sum(final_sum1)
    );

    signed_add_pair_helper #(.WIDTH(SUM_WIDTH)) final_add2 (
        .lhs(final_sum1),
        .rhs({SUM_WIDTH{1'b0}}),
        .sum(final_sum2)
    );

    assign stage_alias0 = lane_sum0;
    assign stage_alias1 = block_sum0;
    assign stage_alias2 = tree_sum0;
    assign stage_alias3 = final_sum0;
    assign stage_alias4 = final_sum1;
    assign stage_alias5 = final_sum2;

    assign S = stage_alias5;

endmodule
