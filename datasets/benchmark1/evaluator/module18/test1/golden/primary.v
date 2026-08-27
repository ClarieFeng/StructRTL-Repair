module u18_low_mul_core #(
    parameter W = 7
) (
    input wire signed [W-1:0] a_s,
    input wire signed [W-1:0] b_s,
    output wire signed [(W*2)-1:0] product
);
    wire signed [(W*2)-1:0] a_ext;
    wire signed [(W*2)-1:0] b_ext;
    wire signed [(W*2)-1:0] product_int;

    assign a_ext = {{W{a_s[W-1]}}, a_s};
    assign b_ext = {{W{b_s[W-1]}}, b_s};
    assign product_int = a_ext * b_ext;
    assign product = product_int;
endmodule

module signed_parallel_multiplier_7_FA #(
    parameter width = 7
) (
    input wire [width-1:0] A,
    input wire [width-1:0] B,
    output wire [width*2-1:0] S
);
    wire signed [width-1:0] a_s;
    wire signed [width-1:0] b_s;
    wire signed [(width*2)-1:0] product_bits;

    assign a_s = A;
    assign b_s = B;

    u18_low_mul_core #(.W(width)) u_core (
        .a_s(a_s),
        .b_s(b_s),
        .product(product_bits)
    );

    assign S = product_bits;
endmodule
