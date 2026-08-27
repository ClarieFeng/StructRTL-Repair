module u16_low_mul_core #(
    parameter W = 9
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

module booth_multiplier_9_C_Skip_A #(
    parameter width = 9
) (
    input wire [width:1] A,
    input wire [width:1] B,
    output wire [width*2:1] S
);
    wire signed [width-1:0] a_s;
    wire signed [width-1:0] b_s;
    wire signed [(width*2)-1:0] product_bits;

    assign a_s = A[width:1];
    assign b_s = B[width:1];

    u16_low_mul_core #(.W(width)) u_core (
        .a_s(a_s),
        .b_s(b_s),
        .product(product_bits)
    );

    assign S = product_bits;
endmodule
