module csa3_unsigned_stage #(
    parameter integer WIDTH = 26
) (
    input wire [WIDTH:1] a,
    input wire [WIDTH:1] b,
    input wire [WIDTH:1] c,
    output wire [WIDTH:1] sum,
    output wire [WIDTH:1] carry
);
    wire [WIDTH:1] carry_unshifted;

    assign sum = a ^ b ^ c;
    assign carry_unshifted = (a & b) | (a & c) | (b & c);
    assign carry[1] = 1'b0;
    assign carry[WIDTH:2] = carry_unshifted[WIDTH-1:1];
endmodule

module unsigned_add_pair_stage #(
    parameter integer WIDTH = 26
) (
    input wire [WIDTH:1] lhs,
    input wire [WIDTH:1] rhs,
    output wire [WIDTH:1] sum
);
    wire [WIDTH:1] local_lhs;
    wire [WIDTH:1] local_rhs;
    wire [WIDTH:1] pre_sum;

    assign local_lhs = lhs;
    assign local_rhs = rhs;
    assign pre_sum = local_lhs + local_rhs;
    assign sum = pre_sum;
endmodule

module AdderTree_unsigned #(
    parameter width = 23
) (
    input wire [width:1] A1,
    input wire [width:1] A2,
    input wire [width:1] A3,
    input wire [width:1] A4,
    input wire [width:1] A5,
    input wire [width:1] A6,
    output wire [width + 3:1] S
);

    localparam integer SUM_WIDTH = width + 3;

    wire [SUM_WIDTH:1] ext_a1;
    wire [SUM_WIDTH:1] ext_a2;
    wire [SUM_WIDTH:1] ext_a3;
    wire [SUM_WIDTH:1] ext_a4;
    wire [SUM_WIDTH:1] ext_a5;
    wire [SUM_WIDTH:1] ext_a6;

    wire [SUM_WIDTH:1] stage0_lane0;
    wire [SUM_WIDTH:1] stage0_lane1;
    wire [SUM_WIDTH:1] stage0_lane2;
    wire [SUM_WIDTH:1] stage0_lane3;
    wire [SUM_WIDTH:1] stage0_lane4;
    wire [SUM_WIDTH:1] stage0_lane5;

    wire [SUM_WIDTH:1] stage1_sum0;
    wire [SUM_WIDTH:1] stage1_carry0;
    wire [SUM_WIDTH:1] stage1_sum1;
    wire [SUM_WIDTH:1] stage1_carry1;

    wire [SUM_WIDTH:1] stage2_sum0;
    wire [SUM_WIDTH:1] stage2_sum1;

    wire [SUM_WIDTH:1] stage3_sum0;

    assign ext_a1 = {{3{1'b0}}, A1};
    assign ext_a2 = {{3{1'b0}}, A2};
    assign ext_a3 = {{3{1'b0}}, A3};
    assign ext_a4 = {{3{1'b0}}, A4};
    assign ext_a5 = {{3{1'b0}}, A5};
    assign ext_a6 = {{3{1'b0}}, A6};

    assign stage0_lane0 = ext_a1;
    assign stage0_lane1 = ext_a2;
    assign stage0_lane2 = ext_a3;
    assign stage0_lane3 = ext_a4;
    assign stage0_lane4 = ext_a5;
    assign stage0_lane5 = ext_a6;

    csa3_unsigned_stage #(.WIDTH(SUM_WIDTH)) stage1_left (
        .a(stage0_lane0),
        .b(stage0_lane1),
        .c(stage0_lane2),
        .sum(stage1_sum0),
        .carry(stage1_carry0)
    );

    csa3_unsigned_stage #(.WIDTH(SUM_WIDTH)) stage1_right (
        .a(stage0_lane3),
        .b(stage0_lane4),
        .c(stage0_lane5),
        .sum(stage1_sum1),
        .carry(stage1_carry1)
    );

    unsigned_add_pair_stage #(.WIDTH(SUM_WIDTH)) stage2_left (
        .lhs(stage1_sum0),
        .rhs(stage1_carry0),
        .sum(stage2_sum0)
    );

    unsigned_add_pair_stage #(.WIDTH(SUM_WIDTH)) stage2_right (
        .lhs(stage1_sum1),
        .rhs(stage1_carry1),
        .sum(stage2_sum1)
    );

    unsigned_add_pair_stage #(.WIDTH(SUM_WIDTH)) stage3_final (
        .lhs(stage2_sum0),
        .rhs(stage2_sum1),
        .sum(stage3_sum0)
    );

    assign S = stage3_sum0;

endmodule
