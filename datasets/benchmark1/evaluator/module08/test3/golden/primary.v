module signed_extend_helper #(
    parameter integer IN_WIDTH = 22,
    parameter integer OUT_WIDTH = 26
) (
    input wire [IN_WIDTH:1] din,
    output wire signed [OUT_WIDTH:1] dout
);
    wire sign_bit;
    wire signed [OUT_WIDTH:1] ext_value;

    assign sign_bit = din[IN_WIDTH];
    assign ext_value[IN_WIDTH:1] = din;
    assign ext_value[OUT_WIDTH] = sign_bit;
    assign ext_value[OUT_WIDTH - 1] = sign_bit;
    assign ext_value[OUT_WIDTH - 2] = sign_bit;
    assign ext_value[OUT_WIDTH - 3] = sign_bit;
    assign dout = ext_value;
endmodule

module csa3_signed_helper #(
    parameter integer WIDTH = 26
) (
    input wire [WIDTH:1] a,
    input wire [WIDTH:1] b,
    input wire [WIDTH:1] c,
    output wire [WIDTH:1] sum_bits,
    output wire [WIDTH:1] carry_bits
);
    wire [WIDTH:1] carry_raw;
    genvar bit_idx;

    generate
        for (bit_idx = 1; bit_idx <= WIDTH; bit_idx = bit_idx + 1) begin : gen_csa_bits
            assign sum_bits[bit_idx] = a[bit_idx] ^ b[bit_idx] ^ c[bit_idx];
            assign carry_raw[bit_idx] = (a[bit_idx] & b[bit_idx]) | (a[bit_idx] & c[bit_idx]) | (b[bit_idx] & c[bit_idx]);
            if (bit_idx == 1) begin : gen_lsb_carry
                assign carry_bits[bit_idx] = 1'b0;
            end else begin : gen_shifted_carry
                assign carry_bits[bit_idx] = carry_raw[bit_idx - 1];
            end
        end
    endgenerate
endmodule

module signed_pair_add_helper #(
    parameter integer WIDTH = 26
) (
    input wire signed [WIDTH:1] lhs,
    input wire signed [WIDTH:1] rhs,
    output wire signed [WIDTH:1] sum
);
    wire signed [WIDTH:1] local_lhs;
    wire signed [WIDTH:1] local_rhs;
    wire signed [WIDTH:1] local_sum;

    assign local_lhs = lhs;
    assign local_rhs = rhs;
    assign local_sum = local_lhs + local_rhs;
    assign sum = local_sum;
endmodule

module AdderTree_signed #(
    parameter width = 22
)(
    input wire [width:1] A1,
    input wire [width:1] A2,
    input wire [width:1] A3,
    input wire [width:1] A4,
    input wire [width:1] A5,
    input wire [width:1] A6,
    input wire [width:1] A7,
    input wire [width:1] A8,
    input wire [width:1] A9,
    input wire [width:1] A10,
    output wire [width + 4:1] S
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
    wire signed [SUM_WIDTH:1] ext_a10;

    wire [SUM_WIDTH:1] stage1_sum0;
    wire [SUM_WIDTH:1] stage1_carry0;
    wire [SUM_WIDTH:1] stage1_sum1;
    wire [SUM_WIDTH:1] stage1_carry1;
    wire [SUM_WIDTH:1] stage1_sum2;
    wire [SUM_WIDTH:1] stage1_carry2;
    wire [SUM_WIDTH:1] stage1_tail0;

    wire [SUM_WIDTH:1] stage2_sum0;
    wire [SUM_WIDTH:1] stage2_carry0;
    wire [SUM_WIDTH:1] stage2_sum1;
    wire [SUM_WIDTH:1] stage2_carry1;
    wire [SUM_WIDTH:1] stage2_tail0;

    wire signed [SUM_WIDTH:1] stage3_sum0;
    wire signed [SUM_WIDTH:1] stage3_carry0;
    wire signed [SUM_WIDTH:1] stage3_sum1;
    wire signed [SUM_WIDTH:1] stage3_carry1;

    wire signed [SUM_WIDTH:1] final_pair0;
    wire signed [SUM_WIDTH:1] final_pair1;
    wire signed [SUM_WIDTH:1] final_sum0;

    signed_extend_helper #(.IN_WIDTH(width), .OUT_WIDTH(SUM_WIDTH)) ext0 (.din(A1), .dout(ext_a1));
    signed_extend_helper #(.IN_WIDTH(width), .OUT_WIDTH(SUM_WIDTH)) ext1 (.din(A2), .dout(ext_a2));
    signed_extend_helper #(.IN_WIDTH(width), .OUT_WIDTH(SUM_WIDTH)) ext2 (.din(A3), .dout(ext_a3));
    signed_extend_helper #(.IN_WIDTH(width), .OUT_WIDTH(SUM_WIDTH)) ext3 (.din(A4), .dout(ext_a4));
    signed_extend_helper #(.IN_WIDTH(width), .OUT_WIDTH(SUM_WIDTH)) ext4 (.din(A5), .dout(ext_a5));
    signed_extend_helper #(.IN_WIDTH(width), .OUT_WIDTH(SUM_WIDTH)) ext5 (.din(A6), .dout(ext_a6));
    signed_extend_helper #(.IN_WIDTH(width), .OUT_WIDTH(SUM_WIDTH)) ext6 (.din(A7), .dout(ext_a7));
    signed_extend_helper #(.IN_WIDTH(width), .OUT_WIDTH(SUM_WIDTH)) ext7 (.din(A8), .dout(ext_a8));
    signed_extend_helper #(.IN_WIDTH(width), .OUT_WIDTH(SUM_WIDTH)) ext8 (.din(A9), .dout(ext_a9));
    signed_extend_helper #(.IN_WIDTH(width), .OUT_WIDTH(SUM_WIDTH)) ext9 (.din(A10), .dout(ext_a10));

    csa3_signed_helper #(.WIDTH(SUM_WIDTH)) csa10 (.a(ext_a1), .b(ext_a2), .c(ext_a3), .sum_bits(stage1_sum0), .carry_bits(stage1_carry0));
    csa3_signed_helper #(.WIDTH(SUM_WIDTH)) csa11 (.a(ext_a4), .b(ext_a5), .c(ext_a6), .sum_bits(stage1_sum1), .carry_bits(stage1_carry1));
    csa3_signed_helper #(.WIDTH(SUM_WIDTH)) csa12 (.a(ext_a7), .b(ext_a8), .c(ext_a9), .sum_bits(stage1_sum2), .carry_bits(stage1_carry2));
    assign stage1_tail0 = ext_a10;

    csa3_signed_helper #(.WIDTH(SUM_WIDTH)) csa20 (.a(stage1_sum0), .b(stage1_carry0), .c(stage1_sum1), .sum_bits(stage2_sum0), .carry_bits(stage2_carry0));
    csa3_signed_helper #(.WIDTH(SUM_WIDTH)) csa21 (.a(stage1_carry1), .b(stage1_sum2), .c(stage1_carry2), .sum_bits(stage2_sum1), .carry_bits(stage2_carry1));
    assign stage2_tail0 = stage1_tail0;

    csa3_signed_helper #(.WIDTH(SUM_WIDTH)) csa30 (.a(stage2_sum0), .b(stage2_carry0), .c(stage2_sum1), .sum_bits(stage3_sum0), .carry_bits(stage3_carry0));
    csa3_signed_helper #(.WIDTH(SUM_WIDTH)) csa31 (.a(stage2_carry1), .b(stage2_tail0), .c({SUM_WIDTH{1'b0}}), .sum_bits(stage3_sum1), .carry_bits(stage3_carry1));

    signed_pair_add_helper #(.WIDTH(SUM_WIDTH)) add40 (.lhs(stage3_sum0), .rhs(stage3_carry0), .sum(final_pair0));
    signed_pair_add_helper #(.WIDTH(SUM_WIDTH)) add41 (.lhs(stage3_sum1), .rhs(stage3_carry1), .sum(final_pair1));
    signed_pair_add_helper #(.WIDTH(SUM_WIDTH)) add50 (.lhs(final_pair0), .rhs(final_pair1), .sum(final_sum0));

    assign S = final_sum0;

endmodule
