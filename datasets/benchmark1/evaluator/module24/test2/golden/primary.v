module u24_medium_mul_core #(
    parameter width = 22
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

module u24_medium_sign_extend #(
    parameter in_width = 44
) (
    input wire signed [in_width:1] value_in,
    output wire signed [in_width+1:1] value_out
);
    wire signed [in_width:1] value_stage;
    wire signed [in_width+1:1] extended_stage;

    assign value_stage = value_in;
    assign extended_stage = {value_stage[in_width], value_stage};
    assign value_out = extended_stage;
endmodule

module u24_medium_accumulate #(
    parameter width = 45
) (
    input wire signed [width:1] lhs_in,
    input wire signed [width:1] rhs_in,
    output wire signed [width:1] sum_out
);
    wire signed [width:1] lhs_stage;
    wire signed [width:1] rhs_stage;
    wire signed [width:1] sum_stage;
    wire signed [width:1] alias_stage;

    assign lhs_stage = lhs_in;
    assign rhs_stage = rhs_in;
    assign sum_stage = lhs_stage + rhs_stage;
    assign alias_stage = sum_stage;
    assign sum_out = alias_stage;
endmodule

module MAC_signed #(
    parameter width = 22
) (
    input wire signed [width:1] A,
    input wire signed [width:1] B,
    input wire signed [width*2:1] acc_in,
    output wire signed [width*2+1:1] result
);
    wire signed [width*2:1] product_raw;
    wire signed [width*2+1:1] product_ext;
    wire signed [width*2+1:1] acc_ext;
    wire signed [width*2+1:1] accumulated_value;

    u24_medium_mul_core #(.width(width)) mul_core (
        .multiplicand(A),
        .multiplier(B),
        .product_out(product_raw)
    );

    u24_medium_sign_extend #(.in_width(width*2)) product_extend (
        .value_in(product_raw),
        .value_out(product_ext)
    );

    u24_medium_sign_extend #(.in_width(width*2)) acc_extend (
        .value_in(acc_in),
        .value_out(acc_ext)
    );

    u24_medium_accumulate #(.width(width*2+1)) accumulate_stage (
        .lhs_in(product_ext),
        .rhs_in(acc_ext),
        .sum_out(accumulated_value)
    );

    assign result = accumulated_value;
endmodule
