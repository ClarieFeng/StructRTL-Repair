module u15_low_mul_core #(
    parameter W = 9
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

module Multi_unsigned #(
    parameter width = 9
) (
    input wire [width:1] A,
    input wire [width:1] B,
    output wire [width*2:1] P
);
    wire [width-1:0] a_u;
    wire [width-1:0] b_u;
    wire [(width*2)-1:0] product_bits;

    assign a_u = A[width:1];
    assign b_u = B[width:1];

    u15_low_mul_core #(.W(width)) u_core (
        .a_u(a_u),
        .b_u(b_u),
        .product(product_bits)
    );

    assign P = product_bits;
endmodule
