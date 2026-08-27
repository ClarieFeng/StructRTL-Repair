module u24_high_mul_core #(
    parameter width = 24
) (
    input wire signed [width:1] multiplicand,
    input wire signed [width:1] multiplier,
    output wire signed [width*2:1] product_out
);
    wire signed [width:1] multiplicand_stage;
    wire signed [width:1] multiplier_stage;
    wire signed [width*2:1] product_stage;

    assign multiplicand_stage = multiplicand;
    assign multiplier_stage = multiplier;
    assign product_stage = multiplicand_stage * multiplier_stage;
    assign product_out = product_stage;
endmodule

module u24_high_sign_extend #(
    parameter in_width = 48
) (
    input wire signed [in_width:1] value_in,
    output wire signed [in_width+1:1] value_out
);
    wire signed [in_width:1] value_alias;
    wire signed [in_width+1:1] extended_alias;

    assign value_alias = value_in;
    assign extended_alias = {value_alias[in_width], value_alias};
    assign value_out = extended_alias;
endmodule

module u24_high_lane_copy #(
    parameter width = 49
) (
    input wire signed [width:1] lane_in,
    output wire signed [width:1] lane_out
);
    genvar bit_idx;
    generate
        for (bit_idx = 1; bit_idx <= width; bit_idx = bit_idx + 1) begin : gen_lane_copy
            assign lane_out[bit_idx] = lane_in[bit_idx];
        end
    endgenerate
endmodule

module u24_high_accumulate #(
    parameter width = 49
) (
    input wire signed [width:1] lhs_in,
    input wire signed [width:1] rhs_in,
    output wire signed [width:1] sum_out
);
    wire signed [width:1] lhs_stage0;
    wire signed [width:1] rhs_stage0;
    wire signed [width:1] add_stage0;
    wire signed [width:1] add_stage1;

    assign lhs_stage0 = lhs_in;
    assign rhs_stage0 = rhs_in;
    assign add_stage0 = lhs_stage0 + rhs_stage0;
    assign add_stage1 = add_stage0;
    assign sum_out = add_stage1;
endmodule

module u24_high_result_wrap #(
    parameter width = 49
) (
    input wire signed [width:1] value_in,
    output wire signed [width:1] value_out
);
    wire signed [width:1] value_stage0;
    wire signed [width:1] value_stage1;

    assign value_stage0 = value_in;
    assign value_stage1 = value_stage0;
    assign value_out = value_stage1;
endmodule

module MAC_signed #(
    parameter width = 24
) (
    input wire signed [width:1] A,
    input wire signed [width:1] B,
    input wire signed [width*2:1] acc_in,
    output wire signed [width*2+1:1] result
);
    wire signed [width*2:1] product_raw;
    wire signed [width*2+1:1] product_ext;
    wire signed [width*2+1:1] acc_ext;
    wire signed [width*2+1:1] product_bus0;
    wire signed [width*2+1:1] acc_bus0;
    wire signed [width*2+1:1] product_bus1;
    wire signed [width*2+1:1] acc_bus1;
    wire signed [width*2+1:1] sum_bus0;
    wire signed [width*2+1:1] result_bus0;

    u24_high_mul_core #(.width(width)) mul_core (
        .multiplicand(A),
        .multiplier(B),
        .product_out(product_raw)
    );

    u24_high_sign_extend #(.in_width(width*2)) product_extend (
        .value_in(product_raw),
        .value_out(product_ext)
    );

    u24_high_sign_extend #(.in_width(width*2)) acc_extend (
        .value_in(acc_in),
        .value_out(acc_ext)
    );

    u24_high_lane_copy #(.width(width*2+1)) product_copy0 (
        .lane_in(product_ext),
        .lane_out(product_bus0)
    );

    u24_high_lane_copy #(.width(width*2+1)) acc_copy0 (
        .lane_in(acc_ext),
        .lane_out(acc_bus0)
    );

    u24_high_lane_copy #(.width(width*2+1)) product_copy1 (
        .lane_in(product_bus0),
        .lane_out(product_bus1)
    );

    u24_high_lane_copy #(.width(width*2+1)) acc_copy1 (
        .lane_in(acc_bus0),
        .lane_out(acc_bus1)
    );

    u24_high_accumulate #(.width(width*2+1)) accumulate_core (
        .lhs_in(product_bus1),
        .rhs_in(acc_bus1),
        .sum_out(sum_bus0)
    );

    u24_high_result_wrap #(.width(width*2+1)) result_wrap (
        .value_in(sum_bus0),
        .value_out(result_bus0)
    );

    assign result = result_bus0;
endmodule
