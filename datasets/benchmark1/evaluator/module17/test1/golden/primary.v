module u17_low_mul_core #(
    parameter W = 7
) (
    input wire [W-1:0] a_u,
    input wire [W-1:0] b_u,
    output wire [(W*2)-1:0] product
);
    wire [(W*2)-1:0] a_ext;
    wire [(W*2)-1:0] b_ext;
    wire [(W*2)-1:0] product_int;

    assign a_ext = {{W{1'b0}}, a_u};
    assign b_ext = {{W{1'b0}}, b_u};
    assign product_int = a_ext * b_ext;
    assign product = product_int;
endmodule

module parallel_multiplier_7_PPA_Kogge_Stone #(
    parameter width = 7
) (
    input wire [width-1:0] A,
    input wire [width-1:0] B,
    output wire [width*2-1:0] S
);
    wire [width-1:0] a_u;
    wire [width-1:0] b_u;
    wire [(width*2)-1:0] product_bits;

    assign a_u = A;
    assign b_u = B;

    u17_low_mul_core #(.W(width)) u_core (
        .a_u(a_u),
        .b_u(b_u),
        .product(product_bits)
    );

    assign S = product_bits;
endmodule
