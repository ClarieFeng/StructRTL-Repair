module AdderTree_signed #(
    parameter width = 21
)(
    input  wire [width:1] A1,
    input  wire [width:1] A2,
    input  wire [width:1] A3,
    input  wire [width:1] A4,
    input  wire [width:1] A5,
    output wire [width+3:1] S
);

    localparam OUT_W = width + 3;

    wire signed [OUT_W-1:0] a1_ext;
    wire signed [OUT_W-1:0] a2_ext;
    wire signed [OUT_W-1:0] a3_ext;
    wire signed [OUT_W-1:0] a4_ext;
    wire signed [OUT_W-1:0] a5_ext;

    assign a1_ext = {{(OUT_W-width){A1[width]}}, A1};
    assign a2_ext = {{(OUT_W-width){A2[width]}}, A2};
    assign a3_ext = {{(OUT_W-width){A3[width]}}, A3};
    assign a4_ext = {{(OUT_W-width){A4[width]}}, A4};
    assign a5_ext = {{(OUT_W-width){A5[width]}}, A5};

    wire [OUT_W-1:0] stage1_sum_bits;
    wire [OUT_W-1:0] stage1_carry_bits;
    wire [OUT_W-1:0] stage1_carry_shifted;

    assign stage1_sum_bits   = a1_ext ^ a2_ext ^ a3_ext;
    assign stage1_carry_bits = (a1_ext & a2_ext) | (a1_ext & a3_ext) | (a2_ext & a3_ext);
    assign stage1_carry_shifted = {stage1_carry_bits[OUT_W-2:0], 1'b0};

    wire [OUT_W-1:0] stage2_sum_bits;
    wire [OUT_W-1:0] stage2_carry_bits;
    wire [OUT_W-1:0] stage2_carry_shifted;

    assign stage2_sum_bits   = stage1_sum_bits ^ stage1_carry_shifted ^ a4_ext;
    assign stage2_carry_bits = (stage1_sum_bits & stage1_carry_shifted) |
                               (stage1_sum_bits & a4_ext) |
                               (stage1_carry_shifted & a4_ext);
    assign stage2_carry_shifted = {stage2_carry_bits[OUT_W-2:0], 1'b0};

    wire [OUT_W-1:0] stage3_sum_bits;
    wire [OUT_W-1:0] stage3_carry_bits;
    wire [OUT_W-1:0] stage3_carry_shifted;

    assign stage3_sum_bits   = stage2_sum_bits ^ stage2_carry_shifted ^ a5_ext;
    assign stage3_carry_bits = (stage2_sum_bits & stage2_carry_shifted) |
                               (stage2_sum_bits & a5_ext) |
                               (stage2_carry_shifted & a5_ext);
    assign stage3_carry_shifted = {stage3_carry_bits[OUT_W-2:0], 1'b0};

    wire signed [OUT_W-1:0] final_sum_operand;
    wire signed [OUT_W-1:0] final_carry_operand;
    wire signed [OUT_W-1:0] final_sum_signed;

    assign final_sum_operand   = stage3_sum_bits;
    assign final_carry_operand = stage3_carry_shifted;
    assign final_sum_signed    = final_sum_operand + final_carry_operand;

    assign S = final_sum_signed;

endmodule
